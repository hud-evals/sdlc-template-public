from pathlib import Path

from hud.types import MCPToolCall
from env import bug_fix

WORKSPACE = "/home/ubuntu/workspace/user_service"

task = bug_fix.task(
    prompt=(
        "There are production errors showing up in Sentry for the user-service project. "
        "Use the Sentry tools to investigate the unresolved issues — check the error "
        "details, stacktraces, and affected users.\n\n"
        "The code is available locally at /home/ubuntu/workspace/user_service and via "
        "GitHub (owner: acme-corp, repo: user-service).\n\n"
        "Diagnose and fix the bug. Once fixed:\n"
        "1. Commit your changes to a new branch\n"
        "2. Push the branch to origin\n"
        "3. Create a pull request using the GitHub tools\n"
    ),
    source_repo="coding-template-sample",
    repo_name="user-service",
    workspace_name="user_service",
    branch_prefix="sentry_fix",
    test_files=["test_user_service.py"],
    github_data_dir="sentry_triage_task/github_data",
    sentry_data_dir="sentry_triage_task/sentry_data",
    sentry_project={
        "id": "2",
        "slug": "user-service",
        "name": "user-service",
        "platform": "python",
    },
)
task.slug = "sentry_triage"
task.validation = [
    MCPToolCall(name="bash", arguments={
        "command": f"cd {WORKSPACE} && git apply <<'GOLDEN_PATCH'\n"
        + (Path(__file__).parent / "golden.patch").read_text()
        + "GOLDEN_PATCH",
    }),
    MCPToolCall(name="bash", arguments={
        "command": f"cd {WORKSPACE}"
        " && git checkout -b fix/handle-missing-profile"
        " && git add -A"
        " && git commit -m 'fix: handle None/missing user profile gracefully'"
        " && git push origin fix/handle-missing-profile",
    }),
    MCPToolCall(name="create_pull_request", arguments={
        "owner": "acme-corp",
        "repo": "user-service",
        "title": "fix: handle None/missing user profile gracefully",
        "body": (
            "## Summary\n\n"
            "Fixed TypeError crash in `get_user_profile()` when a user has no profile "
            "(profile is `None` or the key is missing entirely).\n\n"
            "The function now falls back to `user['name']` when profile is unavailable.\n\n"
            "Fixes Sentry issue USER-SVC-1 (142 occurrences, 23 users affected)."
        ),
        "head": "fix/handle-missing-profile",
        "base": "sentry_fix_baseline",
    }),
]
