from pathlib import Path

from hud.types import MCPToolCall
from env import bug_fix

WORKSPACE = "/home/ubuntu/workspace/workspace"

task = bug_fix.task(
    prompt=(
        "Fix the JSON serialization bug in server.py. "
        "The API server's responses are malformed — the response body is not valid JSON, "
        "it looks like a Python dict representation instead of proper JSON."
    ),
    source_repo="coding-template-sample",
    workspace_name="workspace",
    branch_prefix="server_fix",
    test_files=["test_server.py"],
)
task.slug = "basic"

task.validation = [
    MCPToolCall(name="bash", arguments={
        "command": f"cd {WORKSPACE} && git apply <<'GOLDEN_PATCH'\n"
        + (Path(__file__).parent / "golden.patch").read_text()
        + "GOLDEN_PATCH",
    }),
]
