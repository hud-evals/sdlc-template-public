from env import bug_fix

task = bug_fix.task(
    prompt=(
        "You have been assigned Linear issue ENG-1. "
        "Use the Linear tools to read the ticket details.\n\n"
        "Then use the GitHub tools to explore the repository "
        "(owner: acme-corp, repo: server-app). "
        "The code is also available locally at /home/ubuntu/workspace/server_repo.\n\n"
        "Fix the bug described in the ticket. Once fixed:\n"
        "1. Commit your changes to a new branch\n"
        "2. Push the branch to origin\n"
        "3. Create a pull request using the GitHub tools\n"
        "4. Leave a comment on the Linear issue summarizing what you did\n"
        "5. Mark the Linear issue as Done\n"
    ),
    source_repo="coding-template-sample",
    repo_name="server-app",
    workspace_name="server_repo",
    branch_prefix="server_fix",
    test_files=["test_server.py"],
    github_data_dir="github_linear_task/github_data",
    linear_data_dir="github_linear_task/linear_data",
)
task.slug = "github_linear"
task.agent_config = {
    "system_prompt": (
        "You are a senior software engineer working in a codebase with GitHub and Linear integrations. "
        "Use the available tools to read tickets, explore the repository, fix bugs, and follow proper "
        "engineering workflow (branch, commit, PR, update tickets)."
    ),
}
