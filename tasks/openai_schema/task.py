from env import bug_fix

task = bug_fix.task(
    prompt=(
        "You have been assigned Linear issue ENG-201. "
        "Use the Linear tools to read the ticket details.\n\n"
        "Then investigate the codebase at /home/ubuntu/workspace/hud_python "
        "and use the GitHub tools to explore the repository "
        "(owner: acme-corp, repo: hud-sdk).\n\n"
        "Fix the bug described in the ticket. Once fixed:\n"
        "1. Commit your changes to a new branch\n"
        "2. Push the branch to origin\n"
        "3. Create a pull request using the GitHub tools\n"
        "4. Leave a comment on the Linear issue summarizing your fix\n"
        "5. Mark the Linear issue as Done\n"
    ),
    source_repo="sdlc-tasks-data",
    repo_name="hud-sdk",
    workspace_name="hud_python",
    branch_prefix="openai_schema",
    test_files=["hud/environment/tests/test_openai_schema_mutation.py"],
    github_data_dir="openai_schema_task/hud_python_github_data",
    linear_data_dir="openai_schema_task/hud_python_linear_data",
    pre_test_commands=["cd {grading_dir} && pip install --no-deps -e . -q 2>/dev/null || true"],
)
task.slug = "openai_schema"
