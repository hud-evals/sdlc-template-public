"""Coding environment — services, MCP tools, and scenario definitions."""

import logging
import os
from typing import Any, Optional

from sdlc import (
    AgenticGrader,
    BashGrader,
    CodingEnvironment,
    GitHubLogRubricGrader,
    Grade,
    bash,
    setup_repo,
)
from sdlc.graders import LinearIssueGrader, LinearLogRubricGrader
from sdlc.mcp.coding import CodingService
from sdlc.mcp.github import MockGitHubService
from sdlc.mcp.linear import LinearService
from sdlc.mcp.sentry import SentryService


logger = logging.getLogger(__name__)
MCP_TESTING_MODE = os.environ.get("MCP_TESTING_MODE") in ["1", "true"]


env = CodingEnvironment("coding")

github_service = MockGitHubService()
env.connect_server(github_service.server)

linear_service = LinearService()
env.connect_server(linear_service.server)

sentry_service = SentryService()
env.connect_server(sentry_service.server)

if MCP_TESTING_MODE:
    coding_service = CodingService()
    env.connect_server(coding_service.server)

# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

BARE_REPO = "/srv/git/project.git"


@env.scenario(name="bug_fix")
async def bug_fix(
    prompt: str,
    source_repo: str,
    branch_prefix: str,
    test_files: list[str],
    repo_name: str | None = None,
    workspace_name: str | None = None,
    github_data_dir: str | None = None,
    linear_data_dir: str | None = None,
    sentry_data_dir: str | None = None,
    sentry_project: dict | None = None,
    pre_test_commands: list[str] | None = None,
    agentic_criteria: list[dict] | None = None,
    agentic_model: str = "claude-opus-4-6",
    agentic_max_turns: int = 10,
):
    """Generic SDLC bug-fix scenario.

    When ``repo_name`` / ``github_data_dir`` are provided the full
    GitHub + Linear mock workflow is used.  Otherwise a plain
    ``setup_repo`` is enough (e.g. for simple single-file fixes).
    """
    source = f"/home/root/source/{source_repo}"
    workspace = f"/home/ubuntu/workspace/{workspace_name or source_repo}"
    baseline = f"{branch_prefix}_baseline"
    test_branch = f"{branch_prefix}_test"

    if repo_name and github_data_dir:
        github_service.configure(
            bare_repo_path=BARE_REPO,
            data_dir=f"/mcp_server/data/{github_data_dir}",
            repo_owner="acme-corp",
            repo_name=repo_name,
            default_branch=baseline,
            repo_setup={
                repo_name: [
                    "git config --global --add safe.directory '*'",
                    "su -c \"git config --global --add safe.directory '*'\" ubuntu",
                    "mkdir -p /home/ubuntu",
                    f"rm -rf {BARE_REPO}",
                    "mkdir -p /srv/git",
                    f"git clone --bare {source} {BARE_REPO}",
                    f"git -C {BARE_REPO} branch -D {test_branch} || true",
                    f"git -C {BARE_REPO} branch -D {branch_prefix}_golden || true",
                ],
            },
        )
        github_service.setup_repos()

        bash(f"rm -rf {workspace}")
        bash(f"git clone --branch {baseline} {github_service.repo_url} {workspace}")
        bash(f"chown -R ubuntu:ubuntu {workspace}")

        if linear_data_dir:
            linear_service.configure(data_dir=f"/mcp_server/data/{linear_data_dir}")

        if sentry_data_dir:
            sentry_service.configure(
                data_dir=f"/mcp_server/data/{sentry_data_dir}",
                project=sentry_project,
            )
    else:
        setup_repo(source=source, target=workspace, checkout=baseline, branches=[baseline])

    # ---- prompt ----
    yield prompt

    # ---- grading ----
    if repo_name and github_data_dir:
        grading_dir = f"/tmp/grading/{workspace_name or source_repo}"
        bash(f"mkdir -p /tmp/grading && rm -rf {grading_dir} && git clone {BARE_REPO} {grading_dir}")
        bash(
            f"cd {grading_dir}"
            " && AGENT_REF=$(git for-each-ref --sort=-committerdate"
            " --format='%(refname:short)' refs/remotes/origin"
            " | grep -v HEAD | head -1 | sed 's|^origin/||')"
            " && git checkout \"$AGENT_REF\""
        )

        if pre_test_commands:
            for cmd in pre_test_commands:
                bash(cmd.format(grading_dir=grading_dir))

        for tf in test_files:
            bash(f"git -C {source} diff {baseline}..{test_branch} -- {tf} | git -C {grading_dir} apply")

        yield Grade.from_subscores([
            BashGrader.grade(
                weight=0.8,
                command=f"cd {grading_dir} && python -m pytest {' '.join(test_files)} -v",
                timeout=120,
            ),
            GitHubLogRubricGrader.grade(
                weight=0.2,
                mock_github_client=github_service.client,
                rubric="Did the agent create a pull request with a clear description of the bug fix?",
            ),
        ])
    elif agentic_criteria:
        grading_dir = f"/tmp/grading/{workspace_name or source_repo}"
        bash(f"mkdir -p /tmp/grading && rm -rf {grading_dir} && cp -r {workspace} {grading_dir}")
        for tf in test_files:
            bash(f"git -C {source} diff {baseline}..{test_branch} -- {tf} | git -C {grading_dir} apply")

        grade = Grade.from_subscores(AgenticGrader.grade(
            task_prompt=prompt,
            criteria=agentic_criteria,
            github_service=github_service,
            linear_service=linear_service,
            model=agentic_model,
            max_exploration_turns=agentic_max_turns,
        ))

        for criterion_name, criterion_info in (getattr(grade, "info", None) or {}).items():
            if not isinstance(criterion_info, dict):
                continue
            passed = criterion_info.get("passed")
            icon = "✅" if passed is True else ("❌" if passed is False else "📊")
            action_log = criterion_info.get("action_log", [])
            logger.info(
                "%s %s  passed=%s  turns=%d  reasoning=%s",
                icon, criterion_name, passed, len(action_log),
                (criterion_info.get("reasoning") or "")[:300],
            )
            for i, step in enumerate(action_log, 1):
                cmd = (step.get("command") or "")[:120]
                logger.info("  %d. [%s] %s", i, step.get("action", "?"), cmd)

        yield grade
    else:
        for tf in test_files:
            bash(f"git -C {source} show {test_branch}:{tf} > {workspace}/{tf}")

        yield Grade.from_subscores([
            BashGrader.grade(
                weight=1.0,
                command=f"cd {workspace} && python -m pytest {' '.join(test_files)} -v",
                timeout=120,
            ),
        ])


@env.scenario(name="bug_fix_linear")
async def bug_fix_linear(
    prompt: str,
    source_repo: str,
    branch_prefix: str,
    test_files: list[str],
    repo_name: str,
    github_data_dir: str,
    linear_data_dir: str,
    linear_issue_title_contains: str,
    linear_rubric: str,
    workspace_name: str | None = None,
    sentry_data_dir: str | None = None,
    sentry_project: dict | None = None,
    pre_test_commands: list[str] | None = None,
    linear_issue_state_type: str = "completed",
):
    """Bug-fix scenario with GitHub + Linear grading.

    Same setup as ``bug_fix`` with ``repo_name``/``github_data_dir``, but
    adds Linear graders (issue state check + rubric) for tasks where the
    agent is expected to interact with Linear tickets.
    """
    source = f"/home/root/source/{source_repo}"
    workspace = f"/home/ubuntu/workspace/{workspace_name or source_repo}"
    baseline = f"{branch_prefix}_baseline"
    test_branch = f"{branch_prefix}_test"

    github_service.configure(
        bare_repo_path=BARE_REPO,
        data_dir=f"/mcp_server/data/{github_data_dir}",
        repo_owner="acme-corp",
        repo_name=repo_name,
        default_branch=baseline,
        repo_setup={
            repo_name: [
                "git config --global --add safe.directory '*'",
                "su -c \"git config --global --add safe.directory '*'\" ubuntu",
                "mkdir -p /home/ubuntu",
                f"rm -rf {BARE_REPO}",
                "mkdir -p /srv/git",
                f"git clone --bare {source} {BARE_REPO}",
                f"git -C {BARE_REPO} branch -D {test_branch} || true",
                f"git -C {BARE_REPO} branch -D {branch_prefix}_golden || true",
            ],
        },
    )
    github_service.setup_repos()

    bash(f"rm -rf {workspace}")
    bash(f"git clone --branch {baseline} {github_service.repo_url} {workspace}")
    bash(f"chown -R ubuntu:ubuntu {workspace}")

    linear_service.configure(data_dir=f"/mcp_server/data/{linear_data_dir}")

    if sentry_data_dir:
        sentry_service.configure(
            data_dir=f"/mcp_server/data/{sentry_data_dir}",
            project=sentry_project,
        )

    # ---- prompt ----
    yield prompt

    # ---- grading ----
    grading_dir = f"/tmp/grading/{workspace_name or source_repo}"
    bash(f"mkdir -p /tmp/grading && rm -rf {grading_dir} && git clone {BARE_REPO} {grading_dir}")
    bash(
        f"cd {grading_dir}"
        " && AGENT_REF=$(git for-each-ref --sort=-committerdate"
        " --format='%(refname:short)' refs/remotes/origin"
        " | grep -v HEAD | head -1 | sed 's|^origin/||')"
        " && git checkout \"$AGENT_REF\""
    )

    if pre_test_commands:
        for cmd in pre_test_commands:
            bash(cmd.format(grading_dir=grading_dir))

    for tf in test_files:
        bash(f"git -C {source} diff {baseline}..{test_branch} -- {tf} | git -C {grading_dir} apply")

    yield Grade.from_subscores([
        BashGrader.grade(
            weight=0.6,
            command=f"cd {grading_dir} && python -m pytest {' '.join(test_files)} -v",
            timeout=120,
        ),
        GitHubLogRubricGrader.grade(
            weight=0.1,
            mock_github_client=github_service.client,
            rubric="Did the agent create a pull request with a clear description of the bug fix?",
        ),
        LinearIssueGrader.grade(
            weight=0.1,
            linear_data=linear_service.data,
            title_contains=linear_issue_title_contains,
            state_type=linear_issue_state_type,
        ),
        LinearLogRubricGrader.grade(
            weight=0.2,
            linear_data=linear_service.data,
            rubric=linear_rubric,
        ),
    ])
