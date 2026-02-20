from env import bug_fix

task = bug_fix.task(
    prompt=(
        "You are an on-call engineer for the Platform team. "
        "There have been user complaints about the settings API.\n\n"
        "Check the GitHub issues on the acme-corp/settings-api repository for details. "
        "The code is available locally at /home/ubuntu/workspace/settings_api.\n\n"
        "Your job:\n"
        "1. Investigate the reported issues and the codebase to identify the root cause\n"
        "2. Fix the bug\n"
        "3. Commit your changes to a new branch and push to origin\n"
        "4. Create a pull request using the GitHub tools\n"
        "5. Create a Linear ticket (team: Platform) documenting your diagnosis and fix\n"
        "6. Mark your Linear ticket as Done\n"
    ),
    source_repo="coding-template-sample",
    repo_name="settings-api",
    workspace_name="settings_api",
    branch_prefix="settings_bug",
    test_files=["test_settings.py"],
    github_data_dir="settings_bug_task/settings_github_data",
    linear_data_dir="settings_bug_task/settings_linear_data",
)
task.slug = "settings_bug"
