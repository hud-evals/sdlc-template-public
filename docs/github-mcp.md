# Adding GitHub MCP Tools (Mock Mode)

This guide explains how to give your agent access to mock GitHub tools so it can browse repositories, read issues, inspect branches, view commit history, open pull requests, and more — all backed by static JSON files and a local bare git repo. No GitHub token or network access needed.


## What the Agent Gets

When you wire up the GitHub MCP, the agent gains **up to 27 tools** (depending on `read_only` setting) that mirror the real GitHub API:

| Category | Tools (read) |
|---|---|
| **Identity** | `whoami`, `rate_limit_status` |
| **Repos** | `list_repositories`, `get_repository`, `get_readme` |
| **Code Browsing** | `get_file_contents`, `list_branches`, `search_code`, `compare_commits` |
| **Git History** | `list_commits`, `get_commit`, `get_commit_diff` |
| **Issues** | `list_issues`, `get_issue`, `list_issue_comments`, `search_issues` |
| **Pull Requests** | `list_pull_requests`, `get_pull_request`, `get_pull_request_diff`, `list_pr_reviews`, `list_pr_review_comments` |
| **CI / Actions** | `list_workflow_runs`, `get_workflow_run`, `get_job_logs` |

With `read_only=False`, these **write tools** are also registered:

| Category | Tools (write) |
|---|---|
| **Issues** | `create_issue`, `update_issue`, `add_issue_comment` |
| **Pull Requests** | `create_pull_request`, `add_pr_comment` |
| **Branches** | `create_branch` |

The agent interacts with these tools exactly as it would with the real GitHub API.

---

## How Mock GitHub Differs from Mock Linear

Mock GitHub has **two data layers**, not one:

| Data Layer | Source | What it serves |
|---|---|---|
| **JSON files** | `github_data/` directory | Issues, repo metadata, authenticated user |
| **Bare git repo** | Created at runtime from the challenge repo | Branches, commits, file contents, diffs, code search |

The JSON layer is analogous to Linear MCP. The git layer is unique — it reads from a real local bare git repository, so `list_branches`, `get_file_contents`, `list_commits`, etc. return actual git data.

Additionally, **pull requests and new issues** created by the agent are stored **in-memory** and don't persist between runs.

---

## Quick Start

### 1. Create a `github_data/` directory

Copy the example data into your project as a starting point:

```bash
cp -r docs/examples/github/ github_data/
```

Or create the directory from scratch. You need three JSON files:

```
my-eval/
├── env.py
├── github_data/
│   ├── repo.json        # required — repository metadata
│   ├── issues.json      # required — pre-populated issues
│   └── user.json        # optional — authenticated user identity
├── tasks/
└── ...
```

### 2. Wire up in `env.py`

```python
from pathlib import Path
from sdlc.mcp.github import MockGitHubService

_BARE_REPO_PATH = "/srv/git/project.git"

github = MockGitHubService(
    data_dir=str(Path(__file__).parent / "github_data"),
    bare_repo_path=_BARE_REPO_PATH,
    repo_owner="my-org",
    repo_name="my-app",
    default_branch="baseline",
    hidden_branches=["test", "golden"],
    read_only=False,
)
env.connect_server(github.server)
```

### 3. Create the bare repo at runtime

The bare repo must be created at runtime from the agent's workspace. In your scenario's setup function:

```python
import os
import shutil
import subprocess

def create_bare_repo(project_dir: str, bare_repo_path: str) -> None:
    """Create a bare repo from the agent's workspace and point origin at it."""
    # Allow git to operate on the directory
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", "*"],
        capture_output=True, text=True,
    )

    # Create bare clone
    if os.path.exists(bare_repo_path):
        shutil.rmtree(bare_repo_path)
    subprocess.run(
        ["git", "clone", "--bare", project_dir, bare_repo_path],
        capture_output=True, text=True, check=True,
    )
    # Make writable by agent (uid 1000)
    subprocess.run(["chown", "-R", "1000:1000", bare_repo_path], capture_output=True)
    subprocess.run(["chmod", "-R", "a+rwX", bare_repo_path], capture_output=True)

    # Point agent's origin to the bare repo (for git push)
    subprocess.run(
        ["git", "remote", "remove", "origin"],
        cwd=project_dir, capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", bare_repo_path],
        cwd=project_dir, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "push.default", "current"],
        cwd=project_dir, capture_output=True,
    )
```

After creating the bare repo, reset the mock client so it picks up the new path:

```python
github.client.reload(
    data_dir=str(Path(__file__).parent / "github_data"),
    bare_repo_path=_BARE_REPO_PATH,
)
```

### 4. Dockerfile changes

Add two things to your `Dockerfile.hud`:

```dockerfile
# Copy GitHub data into the image
COPY ./github_data /mcp_server/github_data

# Create directory for the bare git repo (created at runtime)
RUN mkdir -p /srv/git && chmod 777 /srv/git
```

---

## Data Files

A complete example data set is in [`docs/examples/github/`](examples/github/). You can copy the whole directory and modify it, or build your own from scratch.

### Files

| File | Required | What it contains | Example |
|---|---|---|---|
| `repo.json` | Yes | Single object — repository metadata | [repo.json](examples/github/repo.json) |
| `issues.json` | Yes | Array of issue objects — bugs, features, discussions | [issues.json](examples/github/issues.json) |
| `user.json` | No | Single object — authenticated user identity | [user.json](examples/github/user.json) |

If `user.json` is missing, a default identity is created:

```json
{
  "login": "agent-bot",
  "name": "Agent Bot",
  "email": "agent@example.com",
  "id": 42
}
```

If `repo.json` is missing, a default repo entry is built from the `repo_owner` and `repo_name` constructor args.

---

## Field Reference

Refer to the [example files](examples/github/) for complete, copy-pasteable JSON.

### `repo.json`

Single object describing the repository.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | int | Yes | Unique identifier |
| `name` | string | Yes | Repository name (e.g., `"my-app"`) |
| `full_name` | string | Yes | `"owner/repo"` format (e.g., `"my-org/my-app"`) |
| `description` | string | No | Short description |
| `default_branch` | string | No | Default branch name (e.g., `"baseline"`) |
| `private` | bool | No | Visibility |
| `html_url` | string | No | Mock URL|
| `language` | string | No | Primary language |
| `topics` | array | No | Array of topic strings |
| `stargazers_count` | int | No | Star count |
| `forks_count` | int | No | Fork count |
| `open_issues_count` | int | No | Open issue count |
| `created_at` | string | No | ISO 8601 timestamp |
| `updated_at` | string | No | ISO 8601 timestamp |

### `issues.json`

Array of issue objects. This is the most important file — it defines what the agent finds when it runs `list_issues` or `search_issues`.

| Field | Type | Required | Description |
|---|---|---|---|
| `number` | int | Yes | Unique issue number (1, 2, 3, ...) |
| `title` | string | Yes | Issue title |
| `body` | string | No | Issue description (Markdown supported) |
| `state` | string | No | `"open"` or `"closed"` (default: `"open"`) |
| `labels` | array | No | Array of `{"name": "bug"}` objects |
| `assignees` | array | No | Array of `{"login": "username"}` objects |
| `user` | object | No | Author: `{"login": "name", "id": 1}` |
| `created_at` | string | No | ISO 8601 timestamp |
| `updated_at` | string | No | ISO 8601 timestamp |
| `comments` | int | No | Comment count |
| `html_url` | string | No | Mock URL |

### `user.json`

Single object for the authenticated user (returned by `whoami`).

| Field | Type | Required | Description |
|---|---|---|---|
| `login` | string | Yes | GitHub username |
| `name` | string | No | Display name |
| `email` | string | No | Email address |
| `id` | int | No | User ID |
| `bio` | string | No | Bio text |
| `public_repos` | int | No | Number of public repos |
| `followers` | int | No | Follower count |
| `html_url` | string | No | Profile URL |

---

## Constructor Reference

`MockGitHubService` accepts these parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `data_dir` | `str \| None` | `None` | Path to JSON data directory |
| `bare_repo_path` | `str \| None` | `None` | Path to the local bare git repo |
| `repo_owner` | `str` | `"hud-evals"` | Mock repository owner |
| `repo_name` | `str` | `"sdlc-sentry-challenge-v2"` | Mock repository name |
| `default_branch` | `str` | `"baseline"` | Default branch for git operations |
| `hidden_branches` | `list[str] \| None` | `None` | Branches to hide from `list_branches` and reject as refs |
| `read_only` | `bool` | `False` | If `True`, only register read-only tools |

### Key concepts

**`repo_owner` / `repo_name`**: Every tool requires `owner` and `repo` arguments. The mock validates these against the configured values — if the agent passes a different owner/repo, it gets a `RepoAccessDenied` error. Set these to match whatever your `repo.json` says.

**`hidden_branches`**: Security feature. Branches listed here are filtered from `list_branches` results and rejected when used as a ref in any tool. Use this to hide grading branches (e.g., `["test", "golden"]`) that the agent shouldn't see.

**`bare_repo_path`**: The path where a bare git repo will exist at runtime. Git-backed tools (`list_branches`, `get_file_contents`, `list_commits`, `search_code`, etc.) read from this repo. If not set or the path doesn't exist, those tools will return errors.

---

## Security: Hidden Branches & Repo Scoping

### Branch hiding

When `hidden_branches=["test", "golden"]`:

- `list_branches` omits these branches from results
- Using `"test"` or `"golden"` as a `ref` parameter raises `BranchHiddenError`
- The agent cannot read file contents, commits, or diffs from hidden branches

This prevents the agent from reading test/grading data.

### Repo scoping

The mock only serves data for one repository (`repo_owner/repo_name`). Any tool call with a different owner/repo raises `RepoAccessDenied`. The agent sees one repo via `list_repositories`.

---

## Designing Effective Data

### Issues should mirror your team's communication style

Your GitHub issues should read like real bug reports filed by frustrated teammates:

```json
{
  "title": "Tasks API broken — 500 errors across all task endpoints",
  "body": "Since the latest deploy, basically every endpoint under /api/v1/tasks/ is returning 500 errors.\n\nI checked the users and organizations endpoints and those seem fine, so it's specific to tasks.\n\nThis is blocking the frontend team, please prioritize."
}
```

Include symptoms, partial investigations, and cross-references between issues.

### Use labels for prioritization signals

```json
"labels": [{"name": "bug"}, {"name": "P0"}]
```

This gives the agent triage signals. Include a mix of `P0`, `P1`, and non-critical issues so the agent has to decide what's important.

### Include noise issues

Don't only include issues for the bugs the agent needs to fix. Add unrelated issues:

- Feature requests in a different area
- Closed issues from previous sprints
- Investigation issues that lead to dead ends

### The bare repo provides real context

Unlike Linear where everything comes from JSON, GitHub tools read actual git data. This means:

- `get_file_contents` shows the real code in the repo
- `list_commits` shows real commit history
- `search_code` uses `git grep` against the actual files
- `compare_commits` shows real diffs

Design your challenge repo's commit history to contain breadcrumbs. For example, a commit that introduced a bug can be found via `list_commits` with a `path` filter.

---

## Full `env.py` Example

Here's a complete `env.py` that wires up GitHub MCP alongside the standard tools:

```python
"""Coding environment with GitHub MCP tools."""

import logging
import os
import shutil
import subprocess
from pathlib import Path

from sdlc import CodingEnvironment
from sdlc.env import setup_repo, get_project_dir
from sdlc.mcp.github import MockGitHubService

logger = logging.getLogger(__name__)

env = CodingEnvironment("coding")

# --- Paths ---
_SOURCE_REPO = "/home/root/source/project"
_GITHUB_DATA_DIR = str(Path(__file__).parent / "github_data")
_BARE_REPO_PATH = "/srv/git/project.git"

# --- GitHub MCP ---
github = MockGitHubService(
    data_dir=_GITHUB_DATA_DIR,
    bare_repo_path=_BARE_REPO_PATH,
    repo_owner="my-org",
    repo_name="my-app",
    default_branch="baseline",
    hidden_branches=["test", "golden"],
    read_only=False,
)
env.connect_server(github.server)


def setup_task() -> None:
    """Set up agent workspace and bare repo for this task."""
    # Copy source repo to agent workspace (only allowed branches)
    setup_repo(
        source=_SOURCE_REPO,
        target=get_project_dir(),
        branches=["baseline"],
        checkout="baseline",
    )

    project_dir = get_project_dir()

    # Create bare repo from agent workspace
    subprocess.run(
        ["git", "config", "--global", "--add", "safe.directory", "*"],
        capture_output=True,
    )
    if os.path.exists(_BARE_REPO_PATH):
        shutil.rmtree(_BARE_REPO_PATH)
    subprocess.run(
        ["git", "clone", "--bare", project_dir, _BARE_REPO_PATH],
        capture_output=True, check=True,
    )
    subprocess.run(["chown", "-R", "1000:1000", _BARE_REPO_PATH], capture_output=True)
    subprocess.run(["chmod", "-R", "a+rwX", _BARE_REPO_PATH], capture_output=True)

    # Point agent's origin to bare repo
    subprocess.run(
        ["git", "remote", "remove", "origin"],
        cwd=project_dir, capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", _BARE_REPO_PATH],
        cwd=project_dir, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "push.default", "current"],
        cwd=project_dir, capture_output=True,
    )

    # Reset mock client for this run
    github.client.reload(
        data_dir=_GITHUB_DATA_DIR,
        bare_repo_path=_BARE_REPO_PATH,
    )

    logger.info(
        "GitHub MCP ready: %d issues, bare_repo=%s",
        len(github.client._all_issues()),
        _BARE_REPO_PATH,
    )


# Import tasks after env is defined
import tasks  # noqa: F401, E402
```

And a scenario that uses it:

```python
# tasks/my_task.py
from env import env, setup_task, github
from sdlc import Grade, UnitTestGrader
from sdlc.env import get_project_dir
from sdlc.graders import PRGrader

@env.scenario(name="fix-and-pr")
async def fix_and_pr():
    setup_task()

    yield (
        "You are the on-call engineer. Multiple P0/P1 bugs have been filed.\n\n"
        "Use GitHub tools to investigate the issues, review the codebase,\n"
        "then fix the bugs and open a pull request with your changes.\n\n"
        f"The repository is at {get_project_dir()}."
    )

    grade = Grade.from_subscores([
        PRGrader.grade(
            weight=1.0,
            source_repo="/home/root/source/project",
            base_ref="baseline",
            test_ref="test",
            golden_ref="golden",
            test_files=["tests/test_fix.py"],
            test_command="pytest {test_files} -v",
            mock_github_client=github.client,
            base_branch="baseline",
        ),
    ])
    yield grade.score
```

---

## PR Workflow

If your task requires the agent to open a pull request (not just fix code), the mock GitHub supports the full workflow:

1. Agent investigates issues via `list_issues`, `get_issue`
2. Agent browses code via `get_file_contents`, `search_code`, `list_commits`
3. Agent fixes bugs using bash/editor tools
4. Agent creates a feature branch: `git checkout -b fix/my-fix`
5. Agent commits and pushes: `git add . && git commit -m "Fix bug" && git push -u origin fix/my-fix`
6. Agent creates PR via `create_pull_request` tool
7. Grading uses `PRGrader` which finds the PR in mock data, extracts the test patch, and runs tests

The `git push` works because the agent's `origin` remote points at the bare repo. The `create_pull_request` tool validates that the head branch exists in the bare repo before creating the in-memory PR.

---

## CI / Workflow Stubs

The mock does **not** simulate GitHub Actions. CI-related tools return empty results:

- `list_workflow_runs` → empty list
- `get_workflow_run` → 404 error
- `get_job_logs` → 404 error

If your task requires CI context, consider putting that information in issue comments or documents instead.

---

## How the Agent Uses These Tools

A typical agent investigation flow:

1. **`whoami`** — confirm identity
2. **`list_repositories`** — discover available repos
3. **`list_issues`** with `state="open"` — find open bugs
4. **`get_issue`** on specific issues — read full descriptions
5. **`list_branches`** — see what branches exist
6. **`get_file_contents`** — read source files
7. **`search_code`** for keywords from the issue — find relevant code
8. **`list_commits`** with `path` filter — see recent changes to a file
9. **Use bash/editor tools** — fix the code
10. **`create_pull_request`** — open a PR with the fix

---

## Troubleshooting

**"Bare repo not configured yet" errors**: The `bare_repo_path` is `None` or the directory doesn't exist yet. Make sure `create_bare_repo()` runs before the agent tries any git-backed tool.

**Agent can't find any issues**: Check that `data_dir` resolves correctly. Add a log line: `logger.info("GitHub data_dir: %s, issues: %d", github.client.data_dir, len(github.client._all_issues()))`.

**`RepoAccessDenied` errors**: The agent is passing `owner`/`repo` that don't match your `repo_owner`/`repo_name`. Check that `repo.json`'s `full_name` matches the constructor args.

**`BranchHiddenError` errors**: The agent is trying to access a hidden branch. This is expected behavior — it prevents reading test/grading branches.

**`git push` fails for agent**: The bare repo permissions may be wrong. Ensure both `chown -R 1000:1000` and `chmod -R a+rwX` are run on the bare repo path.

**`create_pull_request` fails with "Head branch not found"**: The agent needs to `git push` the branch before creating a PR. The mock validates the branch exists in the bare repo.

**File contents return base64**: This is normal — the mock returns GitHub API-compatible responses. The `get_file_contents` tool automatically decodes and displays the text content to the agent.
