# SDLC Template Guide

This template is used to create evaluation environments for testing AI coding agents against real software engineering tasks. Each environment packages one or more **scenarios** — self-contained bug-fix or feature tasks — into a Docker image that can be run locally or deployed to the HUD platform.

## Quick Start

```bash
# 1. Create a new repo from this GitHub template
#    Go to the template repo on GitHub and click "Use this template"
#    Then clone your new repo locally
git clone https://github.com/your-org/my-eval.git
cd my-eval/

# 2. Configure secrets
cp .env.example .env
# Edit .env — fill in LIB_GITHUB_PAT and HUD_API_KEY (see below)

# 3. Install dependencies
uv sync

# 4. Build the Docker image
uv run build

# 5. Launch a scenario locally
uv run dev sample_json_bug
```

### Getting a GitHub PAT

`hud-sdlc-lib` is a private dependency. You need a GitHub Personal Access Token (PAT) with read access to the `hud-evals/hud-sdlc-lib` repository. Either:

- **Get one from HUD** — ask the HUD team for a PAT that has access
- **Generate your own** — go to GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens, create a token scoped to the `hud-evals` organization with **Contents: Read** permission on `hud-sdlc-lib`

Set it as `LIB_GITHUB_PAT` in your `.env` file. This token is used both locally (by `uv sync` to resolve the dependency) and at Docker build time (passed as a build secret, never baked into image layers).

---

## Core Concepts

### Scenarios

A **scenario** is an async generator function decorated with `@env.scenario()`. It defines what the agent sees and how its work is graded:

```python
from env import env
from sdlc import Grade, UnitTestGrader, setup_repo

@env.scenario(name="my_bug_fix")
async def my_bug_fix():
    # --- Setup phase ---
    # Prepare the workspace (runs before the agent sees anything)
    setup_repo(
        source="/home/root/source/my_repo",
        target="/home/ubuntu/workspace/my_repo",
        branches=["main"],
        checkout="main",
    )

    # --- First yield = task prompt ---
    # This is what the agent receives as its instructions
    yield "Fix the bug in auth.py that causes login to fail for users with special characters."

    # --- Evaluate phase ---
    # Grade the agent's work (runs after the agent submits)
    grade = Grade.from_subscores([
        UnitTestGrader.grade(
            weight=1.0,
            files=["test_auth.py"],
            command="python -m pytest test_auth.py -v",
            source_repo="/home/root/source/my_repo",
            base_ref="main",
            test_ref="auth_fix_test",
            golden_ref="auth_fix_golden",  # optional, for validation
            repo_path="/home/ubuntu/workspace/my_repo",
        ),
    ])

    yield grade.score
```

The lifecycle:

1. **Setup** (before first `yield`): call `setup_repo` to prepare the workspace
2. **First `yield`**: returns the prompt string to the agent
3. **Agent works**: the agent reads code, runs commands, edits files
4. **Evaluate** (between yields): grade the agent's solution
5. **Second `yield`**: returns the reward score (0.0–1.0)


### Repos and Branches

The evaluation system uses a two-phase approach to repository management:

**Build time** — repos are cloned into the Docker image so the container never needs network access at runtime. This is configured in `repo_config.yaml`:

```yaml
repos:
  my_repo:
    repo_url: https://github.com/your-org/your-repo
    branches: [main, bug_fix_test, bug_fix_golden]
```

Each repo is cloned into `/home/root/source/<repo_name>/` with all listed branches available. The agent never sees this directory.

**Runtime** — scenarios call `setup_repo()` to copy a repo into the agent's workspace with only the branches the agent should see:

```python
setup_repo(
    source="/home/root/source/my_repo",    # where the full repo lives
    target="/home/ubuntu/workspace/my_repo", # where the agent works
    branches=["main"],                       # branches visible to agent
    checkout="main",                         # branch to check out
)
```

The graders then use the *source* repo (which still has all branches) to extract test patches at grade time. This means the agent never sees the test or golden solution branches.


### Branch Convention

For a normal coding task, you typically have three branches:

| Branch | Purpose |
|---|---|
| `<task>_baseline` | Starting point the agent sees (contains the bug) |
| `<task>_test` | Adds test files that verify the fix (hidden from agent) |
| `<task>_golden` | The correct solution (hidden, used for validation only) |

The test patch is the diff from `baseline` to `test` — it adds test files. The golden patch is the diff from `baseline` to `golden` — it contains the fix. During grading, the test patch is applied on top of the agent's work to see if their fix passes the tests.

---

## Graders

### UnitTestGrader

Extracts specific test files from a patch and runs a command. This is the most common grader.

```python
UnitTestGrader.grade(
    weight=1.0,                              # weight in Grade.from_subscores
    files=["test_auth.py"],                  # files to extract from test patch
    command="python -m pytest test_auth.py", # shell command to run
    source_repo="/home/root/source/my_repo", # repo with all branches
    base_ref="main",                         # baseline branch
    test_ref="fix_test",                     # branch with test additions
    repo_path="/home/ubuntu/workspace/my_repo",
    golden_ref="fix_golden",                 # optional: for validation mode
)
```

How it works:
1. Copies the agent's repo to a temp directory
2. Diffs `base_ref..test_ref` in the source repo to get the test patch
3. Filters the patch to only the specified `files`
4. Applies the filtered patch to the temp copy
5. Runs the command — exit code 0 = pass (1.0), anything else = fail (0.0)

---

## CLI Commands

All commands are run from the template project directory.

### `uv run build`

Builds the Docker image locally. This:
1. Updates `hud-sdlc-lib` to the latest version (`uv lock --upgrade-package`)
2. Runs `hud build .` which builds the Dockerfile

The build process clones all repos from `repo_config.yaml` into the image.

### `uv run dev <scenario>`

Opens an interactive shell inside the container for a specific scenario. The scenario's setup phase runs automatically, populating the workspace. You can then:
- Explore the repo as the agent would see it
- Make changes and test them
- Run `sdlc-test` to grade your changes (simulates the evaluate phase)

```bash
$ uv run dev my_bug_fix
Starting container for scenario 'my_bug_fix'...
Run 'sdlc-test' inside the container to grade your changes.

root@abc123:~/workspace# ls
my_repo/
root@abc123:~/workspace# cd my_repo && git log --oneline -5
# ... explore, make changes ...
root@abc123:~/workspace/my_repo# sdlc-test
PASS  score=1.00
```

`sdlc-test` backs up your workspace, re-runs setup, restores your changes, then runs grading — so your edits are preserved across test runs.

### `uv run deploy`

Builds and deploys the image to the HUD platform. Requires `HUD_API_KEY` in `.env`.

### `uv run update-sdlc`

Updates `hud-sdlc-lib` to the latest commit.

---

## Adding a New Task

### Step 1: Prepare the Source Repo

Your source repo needs the branches listed in the [Branch Convention](#branch-convention) section. For a bug-fix task:

1. Create a branch with the bug (`my_task_baseline`)
2. From that branch, create a branch that adds tests (`my_task_test`)
3. From the baseline, create a branch with the fix (`my_task_golden`)

The test branch should add test files that **fail** on the baseline and **pass** on the golden solution.

### Step 2: Add the Repo to repo_config.yaml

```yaml
repos:
  my_repo:
    repo_url: https://github.com/your-org/your-repo
    branches: [my_task_baseline, my_task_test, my_task_golden]
```

If the repo is private, make sure `LIB_GITHUB_PAT` has access to it.

### Step 3: Create the Scenario

Create a new file in `tasks/` (e.g. `tasks/my_task.py`):

```python
from env import env
from sdlc import Grade, UnitTestGrader, setup_repo


@env.scenario(name="my_task")
async def my_task():
    setup_repo(
        source="/home/root/source/my_repo",
        target="/home/ubuntu/workspace/my_repo",
        branches=["my_task_baseline"],
        checkout="my_task_baseline",
    )

    yield (
        "Fix the authentication bug in auth.py.\n\n"
        "Users with special characters in their passwords cannot log in. "
        "The server returns a 500 error instead of processing the login."
    )

    grade = Grade.from_subscores([
        UnitTestGrader.grade(
            weight=1.0,
            files=["test_auth.py"],
            command="python -m pytest test_auth.py -v",
            source_repo="/home/root/source/my_repo",
            base_ref="my_task_baseline",
            test_ref="my_task_test",
            golden_ref="my_task_golden",
            repo_path="/home/ubuntu/workspace/my_repo",
        ),
    ])

    yield grade.score
```

### Step 4: Register the Scenario

Add the import to `tasks/__init__.py`:

```python
import tasks.basic  # noqa: F401
import tasks.my_task  # noqa: F401
```

### Step 5: Rebuild and Test

```bash
uv run build
uv run dev my_task
# Inside the container:
sdlc-test  # should FAIL (baseline has the bug)
# Make the fix...
sdlc-test  # should PASS
```

### Step 6: Validate (Optional)

You can verify the grading is correct by running in validation mode:

- **baseline_fail**: confirms tests fail on the unmodified baseline (score should be 1.0, meaning "yes, the baseline correctly fails")
- **golden_pass**: confirms tests pass when the golden solution is applied

Set the `VALIDATE_MODE` environment variable before running `sdlc-test`:

```bash
VALIDATE_MODE=baseline_fail sdlc-test
# Expected: PASS (baseline correctly fails the tests)

VALIDATE_MODE=golden_pass sdlc-test
# Expected: PASS (golden solution passes the tests)
```

---

## Language-Specific Examples

The evaluation system is language-agnostic — `setup_repo` just copies a git repo, and the grader runs whatever shell command you specify. Here's how to adapt for different languages.

### Python (default)

```python
UnitTestGrader.grade(
    weight=1.0,
    files=["test_app.py"],
    command="python -m pytest test_app.py -v",
    source_repo="/home/root/source/my_repo",
    base_ref="baseline", test_ref="test_branch",
    repo_path="/home/ubuntu/workspace/my_repo",
)
```

### JavaScript / TypeScript

```python
@env.scenario(name="js_bug_fix")
async def js_bug_fix():
    setup_repo(
        source="/home/root/source/my_js_app",
        target="/home/ubuntu/workspace/my_js_app",
        branches=["main"],
    )

    yield "Fix the race condition in src/api/client.ts"

    grade = Grade.from_subscores([
        UnitTestGrader.grade(
            weight=1.0,
            files=["src/__tests__/client.test.ts"],
            command="cd /home/ubuntu/workspace/my_js_app && npm install && npm test",
            source_repo="/home/root/source/my_js_app",
            base_ref="main",
            test_ref="client_fix_test",
            repo_path="/home/ubuntu/workspace/my_js_app",
        ),
    ])

    yield grade.score
```

For JavaScript/TypeScript tasks, add Node.js to the Dockerfile:

```dockerfile
# Add to the setup stage in Dockerfile.hud
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
  && apt-get install -y nodejs
```

The only things that change between languages are:

1. **The `command`** — whatever runs tests in that language (`pytest`, `npm test`, `cargo test`, `go test`, etc.)
2. **The `files`** — test file paths matching that language's conventions
3. **The Dockerfile** — install the language runtime and build tools

Everything else (repo cloning, branch management, patch extraction, scoring) works identically regardless of language.

---

## Dockerfile Customization

The default `Dockerfile.hud` includes Python, PostgreSQL, and Node.js. Customize it for your needs:

- **Add system packages**: modify the `apt-get install` block in the `setup` stage
- **Add language runtimes**: add `RUN` commands in the `setup` stage
- **Add services** (e.g. Redis, PostgreSQL): install in the Dockerfile and start them in the scenario setup or as part of the test command
- **Pre-install project dependencies**: add a build step that runs `npm install`, `pip install -r requirements.txt`, etc. inside the cloned repo

Example — pre-installing npm dependencies at build time:

```dockerfile
# After build_repos in Dockerfile.hud
RUN cd /home/root/source/my_js_app && npm install
```

This way `npm install` doesn't need to run every time the container starts.

---

## Multiple Repos per Scenario

A scenario can set up multiple repos. Just call `setup_repo` multiple times:

```python
@env.scenario(name="fullstack_bug")
async def fullstack_bug():
    setup_repo(
        source="/home/root/source/backend",
        target="/home/ubuntu/workspace/backend",
        branches=["main"],
    )
    setup_repo(
        source="/home/root/source/frontend",
        target="/home/ubuntu/workspace/frontend",
        branches=["main"],
        chdir=False,  # don't change cwd for subsequent repos
    )

    yield "Fix the API endpoint in backend/ and update the client call in frontend/"

    grade = Grade.from_subscores([
        UnitTestGrader.grade(
            weight=0.5,
            files=["test_api.py"],
            command="python -m pytest test_api.py",
            source_repo="/home/root/source/backend",
            base_ref="main", test_ref="api_fix_test",
            repo_path="/home/ubuntu/workspace/backend",
        ),
        UnitTestGrader.grade(
            weight=0.5,
            files=["src/__tests__/client.test.ts"],
            command="npm test",
            source_repo="/home/root/source/frontend",
            base_ref="main", test_ref="client_fix_test",
            repo_path="/home/ubuntu/workspace/frontend",
        ),
    ])

    yield grade.score
```

Don't forget to list both repos in `repo_config.yaml`:

```yaml
repos:
  backend:
    repo_url: https://github.com/your-org/backend
    branches: [main, api_fix_test, api_fix_golden]
  frontend:
    repo_url: https://github.com/your-org/frontend
    branches: [main, client_fix_test, client_fix_golden]
```

---

## Adding MCP Tool Sources

Beyond bash and editor, you can give the agent access to mock versions of real developer tools. These let the agent investigate context (error logs, engineering tickets, GitHub issues) as part of solving a task.

See the `docs/` folder for step-by-step integration guides:

| Guide | What it adds |
|---|---|
| [Linear MCP](docs/linear-mcp.md) | Project management tools — issues, comments, teams, projects, documents |
| [GitHub MCP](docs/github-mcp.md) | Repository tools — issues, branches, file contents, pull requests |

Each MCP is backed by static JSON files you control — no external accounts or API keys needed.
