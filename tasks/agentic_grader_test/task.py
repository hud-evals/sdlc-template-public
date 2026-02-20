from pathlib import Path

from hud.types import MCPToolCall
from env import bug_fix

WORKSPACE = "/home/ubuntu/workspace/workspace"
GRADING_DIR = "/tmp/grading/workspace"

task = bug_fix.task(
    prompt=(
        "Fix the JSON serialization bug in server.py.\n\n"
        "The API server's responses are malformed. When you make a request to any endpoint,\n"
        "the response body is not valid JSON — it looks like a Python dict representation\n"
        "instead of proper JSON (e.g., single quotes instead of double quotes)."
    ),
    source_repo="coding-template-sample",
    workspace_name="workspace",
    branch_prefix="server_fix",
    test_files=["test_server.py"],
    agentic_criteria=[
        {
            "rubric": (
                f"Inspect the code in {WORKSPACE}/server.py. "
                "Has the agent fixed the root cause of the malformed JSON responses? "
                "The bug was that the server returned Python string representations "
                "(single quotes, Python-style True/False/None) instead of valid JSON. "
                "The fix should ensure all API responses are valid JSON. "
                "Any approach that achieves this is acceptable (json.dumps, jsonify, "
                "a serialization library, etc.)."
            ),
            "weight": 0.5,
        },
        {
            "rubric": (
                "Do all hidden unit tests pass? Run: "
                f"cd {GRADING_DIR} && python -m pytest test_server.py -v"
            ),
            "weight": 0.5,
        },
    ],
)
task.slug = "agentic_grader_test"
task.validation = [
    MCPToolCall(name="bash", arguments={
        "command": f"cd {WORKSPACE} && git apply <<'GOLDEN_PATCH'\n"
        + (Path(__file__).parent / "golden.patch").read_text()
        + "GOLDEN_PATCH",
    }),
]
