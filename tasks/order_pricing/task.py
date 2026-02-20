from env import bug_fix

task = bug_fix.task(
    prompt=(
        "You have been assigned Linear issue COM-15. "
        "Use the Linear tools to read the ticket details.\n\n"
        "Then use the GitHub tools to explore the repository "
        "(owner: acme-corp, repo: order-api). "
        "The code is also available locally at /home/ubuntu/workspace/order_api.\n\n"
        "Diagnose and fix the bug(s) described in the ticket. "
        "The GitHub issues may contain useful context. Once fixed:\n"
        "1. Commit your changes to a new branch\n"
        "2. Push the branch to origin\n"
        "3. Create a pull request using the GitHub tools\n"
        "4. Leave a comment on the Linear issue summarizing your diagnosis and fix\n"
        "5. Mark the Linear issue as Done\n"
    ),
    source_repo="coding-template-sample",
    repo_name="order-api",
    workspace_name="order_api",
    branch_prefix="order_bug",
    test_files=["test_order_pricing.py"],
    github_data_dir="order_pricing_task/order_github_data",
    linear_data_dir="order_pricing_task/order_linear_data",
)
task.slug = "order_pricing"
