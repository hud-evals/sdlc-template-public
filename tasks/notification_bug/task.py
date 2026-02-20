from env import bug_fix

task = bug_fix.task(
    prompt=(
        "You have been assigned Linear issue PLT-42. "
        "Use the Linear tools to read the ticket details.\n\n"
        "Then use the GitHub tools to explore the repository "
        "(owner: acme-corp, repo: task-manager). "
        "The code is also available locally at /home/ubuntu/workspace/task_manager.\n\n"
        "Diagnose and fix the bug described in the ticket. "
        "The GitHub issues may contain useful context. Once fixed:\n"
        "1. Commit your changes to a new branch\n"
        "2. Push the branch to origin\n"
        "3. Create a pull request using the GitHub tools\n"
        "4. Leave a comment on the Linear issue summarizing your diagnosis and fix\n"
        "5. Mark the Linear issue as Done\n"
    ),
    source_repo="coding-template-sample",
    repo_name="task-manager",
    workspace_name="task_manager",
    branch_prefix="notif_bug",
    test_files=["test_notifications.py"],
    github_data_dir="notification_bug_task/notif_github_data",
    linear_data_dir="notification_bug_task/notif_linear_data",
)
task.slug = "notification_bug"
