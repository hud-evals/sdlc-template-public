from pathlib import Path

from hud.types import MCPToolCall
from env import bug_fix_linear

WORKSPACE = "/home/ubuntu/workspace/hud_python"

task = bug_fix_linear.task(
    prompt=(
        "You have been assigned Linear issue ENG-305. "
        "Use the Linear tools to read the ticket details.\n\n"
        "Then investigate the codebase at /home/ubuntu/workspace/hud_python "
        "and use the GitHub tools to explore the repository "
        "(owner: acme-corp, repo: hud-sdk).\n\n"
        "There are multiple related bugs causing evaluation rewards to "
        "always return 0.0. The bugs span the eval CLI, the dataset runner, "
        "the environment tool execution, and the eval context. "
        "Fix all of them. Once fixed:\n"
        "1. Commit your changes to a new branch\n"
        "2. Push the branch to origin\n"
        "3. Create a pull request using the GitHub tools\n"
        "4. Leave a comment on the Linear issue summarizing your fix\n"
        "5. Mark the Linear issue as Done\n"
    ),
    source_repo="sdlc-tasks-data",
    repo_name="hud-sdk",
    workspace_name="hud_python",
    branch_prefix="eval_reward",
    test_files=["tests/test_eval_reward.py"],
    github_data_dir="eval_reward_task/hud_python_github_data",
    linear_data_dir="eval_reward_task/hud_python_linear_data",
    linear_issue_title_contains="rewards",
    linear_rubric=(
        "Did the agent leave a meaningful comment on the Linear issue summarizing "
        "the diagnosis and fix? Did the agent mark the issue as Done?"
    ),
    pre_test_commands=[
        "cd {grading_dir} && pip install --no-deps --force-reinstall -e . -q 2>/dev/null || true",
    ],
)
task.slug = "eval_reward"
task.validation = [
    MCPToolCall(name="bash", arguments={
        "command": f"cd {WORKSPACE} && git apply <<'GOLDEN_PATCH'\n"
        + (Path(__file__).parent / "golden.patch").read_text()
        + "GOLDEN_PATCH",
    }),
    MCPToolCall(name="bash", arguments={
        "command": f"cd {WORKSPACE}"
        " && git checkout -b fix/eval-reward-pipeline"
        " && git add -A"
        " && git commit -m 'fix: reward pipeline — forward structuredContent, fix propagation, CLI --full flag'"
        " && git push origin fix/eval-reward-pipeline",
    }),
    MCPToolCall(name="create_pull_request", arguments={
        "owner": "acme-corp",
        "repo": "hud-sdk",
        "title": "fix: reward pipeline — forward structuredContent, fix propagation, CLI --full flag",
        "body": (
            "## Summary\n\n"
            "Fixed 5 bugs causing evaluation rewards to always return 0.0:\n\n"
            "1. `_execute_tool` now forwards `structuredContent` for both local and remote tools\n"
            "2. Runner no longer overwrites `ctx.reward` before evaluate tools run\n"
            "3. `EvalContext.__aexit__` unconditionally propagates `_evaluate_reward`\n"
            "4. `--full` CLI flag now composes `--all`, `--auto-respond`, and `--max-steps 100`\n"
            "5. `find_reward` error logging now shows `structuredContent` instead of full object\n\n"
            "Fixes ENG-305."
        ),
        "head": "fix/eval-reward-pipeline",
        "base": "eval_reward_baseline",
    }),
    MCPToolCall(name="create_comment", arguments={
        "issueId": "issue-305",
        "body": (
            "Fixed all 5 reward pipeline bugs:\n\n"
            "1. `environment.py`: `_execute_tool` was dropping `structuredContent` — now forwarded\n"
            "2. `runner.py`: removed `ctx.reward = result.reward` that overwrote evaluate tool results\n"
            "3. `context.py`: `__aexit__` now unconditionally propagates `_evaluate_reward`\n"
            "4. `cli/eval.py`: `--full` now sets `auto_respond=True` and `max_steps=100`\n"
            "5. `agents/base.py`: improved error logging in `find_reward`\n\n"
            "PR: fix/eval-reward-pipeline"
        ),
    }),
    MCPToolCall(name="linear_update_issue", arguments={
        "id": "issue-305",
        "state": "Done",
    }),
]
