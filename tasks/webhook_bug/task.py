from pathlib import Path

from hud.types import MCPToolCall
from env import bug_fix

WORKSPACE = "/home/ubuntu/workspace/webhook_svc"

task = bug_fix.task(
    prompt=(
        "You are an on-call engineer for the Platform team. "
        "There have been reports of notification delivery issues in the webhook service.\n\n"
        "Check the GitHub issues on the acme-corp/webhook-service repository for details. "
        "The code is available locally at /home/ubuntu/workspace/webhook_svc.\n\n"
        "Your job:\n"
        "1. Investigate the reported issues and the codebase to identify the root cause\n"
        "2. Fix the bug\n"
        "3. Commit your changes to a new branch and push to origin\n"
        "4. Create a pull request using the GitHub tools\n"
        "5. Create a Linear ticket (team: Platform) documenting your diagnosis and fix\n"
        "6. Mark your Linear ticket as Done\n"
    ),
    source_repo="coding-template-sample",
    repo_name="webhook-service",
    workspace_name="webhook_svc",
    branch_prefix="webhook_bug",
    test_files=["test_notifications.py"],
    github_data_dir="webhook_bug_task/webhook_github_data",
    linear_data_dir="webhook_bug_task/webhook_linear_data",
)
task.slug = "webhook_bug"
task.validation = [
    MCPToolCall(name="bash", arguments={
        "command": f"cd {WORKSPACE} && git apply <<'GOLDEN_PATCH'\n"
        + (Path(__file__).parent / "golden.patch").read_text()
        + "GOLDEN_PATCH",
    }),
    MCPToolCall(name="bash", arguments={
        "command": f"cd {WORKSPACE}"
        " && git checkout -b fix/webhook-mutation-bug"
        " && git add -A"
        " && git commit -m 'fix: copy channels list to prevent mutation across webhook events'"
        " && git push origin fix/webhook-mutation-bug",
    }),
    MCPToolCall(name="create_pull_request", arguments={
        "owner": "acme-corp",
        "repo": "webhook-service",
        "title": "fix: copy channels list to prevent mutation across webhook events",
        "body": (
            "## Summary\n\n"
            "Fixed notification delivery bug where users received notifications on "
            "channels they hadn't opted into.\n\n"
            "The root cause was that `resolve_channels()` returned a reference to the "
            "shared channel list in `CHANNEL_REGISTRY`. When `build_notification()` "
            "appended extra channels, it mutated the registry entry, causing subsequent "
            "events to inherit channels from earlier ones.\n\n"
            "The fix copies the channel list before modification so each event gets "
            "its own independent list.\n\n"
            "Fixes #42, #45"
        ),
        "head": "fix/webhook-mutation-bug",
        "base": "webhook_bug_baseline",
    }),
]
