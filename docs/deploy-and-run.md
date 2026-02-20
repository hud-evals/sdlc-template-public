# Deploying and Running Tasks

This guide covers building your evaluation environment locally, deploying it to the HUD platform, and running remote evaluations against it. It assumes you already have a working scenario — see the [main guide](../GUIDE.md) for authoring scenarios, graders, and repo setup.

---

## Prerequisites

### `.env` file

Copy the example and fill in the values:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `LIB_GITHUB_PAT` | Yes | GitHub PAT with read access to `hud-evals/hud-sdlc-lib`. Ask the HUD team or generate one under GitHub Settings > Developer settings > Fine-grained tokens (scope: `hud-evals` org, `Contents: Read` on `hud-sdlc-lib`). |
| `HUD_API_KEY` | Yes (for deploy/eval) | API key from [hud.ai](https://hud.ai). Go to Settings > API Keys to generate one. |
| `ENV_NAME` | No | Override the environment name used by `hud build` and `hud deploy`. Defaults to the `name` field in `pyproject.toml`. Use a unique name to avoid collisions with other environments in your account. |
| `FOLDER_NAME` | No | Name of the workspace folder inside the container (default: `"workspace"`). Passed as a Docker build arg. |

### Dependencies

```bash
uv sync
```

If `uv sync` fails resolving `hud-sdlc-lib`, your `LIB_GITHUB_PAT` is missing or doesn't have access. The template's `pyproject.toml` pulls the lib from a private GitHub repo — the PAT is required for resolution.

---

## Local Development

### Build the Docker image

```bash
uv run build
```

This does two things:
1. Updates `hud-sdlc-lib` to the latest commit (`uv lock --upgrade-package hud-sdlc-lib`)
2. Runs `hud build .` with build args and secrets from your `.env`

The build clones all repos listed in `repo_config.yaml` into the image at `/home/root/source/<repo_name>/`. These are only accessible by the MCP server (root), not the agent.

### Interactive development

```bash
uv run dev <scenario_name>
```

This starts the container, runs the scenario's setup phase, and drops you into an interactive shell. You can explore the workspace exactly as the agent would see it.

### Validation modes

Verify that your grading is correct by running in validation mode:

```bash
# Confirm tests FAIL on the unmodified baseline (score should be 1.0)
VALIDATE_MODE=baseline_fail sdlc-test

# Confirm tests PASS when the golden solution is applied
VALIDATE_MODE=golden_pass sdlc-test
```

Both should output `PASS`. If `baseline_fail` fails, your tests pass on broken code. If `golden_pass` fails, your golden solution doesn't actually fix the bug.

### Non-interactive smoke test

For CI or quick sanity checks without a TTY:

```bash
docker run --rm <image_name> python -c "
import asyncio
from env import env
prompt = asyncio.run(env.run_scenario_setup('my_scenario', {}))
print('Setup OK:', bool(prompt))
"
```

---

## Deploying to HUD

### Deploy the image

```bash
uv run deploy
```

This runs `hud deploy .` with your `.env` config. It:
1. Uploads the build context to HUD's remote build service
2. Builds the Docker image on HUD infrastructure
3. Registers it as an environment

The environment name comes from `ENV_NAME` in `.env`, or falls back to the `name` in `pyproject.toml`. Use a unique name — if another environment in your account has the same name, the deploy will update that environment instead of creating a new one.

### After deploying

Note the environment name from the deploy output. You'll use it in your task file. Each `uv run deploy` pushes a new version of the environment — remote evaluations automatically use the latest version.

### Updating the library

To pull the latest `hud-sdlc-lib` without a full rebuild:

```bash
uv run update-sdlc
```

Then rebuild and redeploy:

```bash
uv run build
uv run deploy
```

---

## Task Files

Task files tell the HUD eval runner which environment and scenario to use for each task. Create a `remote_tasks.json` in your project root:

```json
[
  {
    "id": "my-bug-fix",
    "env": {
      "name": "my-environment-name"
    },
    "scenario": "coding:my_bug_fix"
  }
]
```

| Field | Description |
|---|---|
| `id` | Unique task identifier (used in `--task-ids` filter and results) |
| `env.name` | The environment name from your deploy (matches `ENV_NAME` or `pyproject.toml` name) |
| `scenario` | Format: `"<env_prefix>:<scenario_name>"`. The prefix comes from `CodingEnvironment("coding")` in `env.py`, the scenario name comes from your `@env.scenario(name="...")` decorator. |

For multiple scenarios, add more entries to the array:

```json
[
  {
    "id": "bug-fix-basic",
    "env": { "name": "my-environment-name" },
    "scenario": "coding:my_bug_fix"
  },
  {
    "id": "bug-fix-with-mcp",
    "env": { "name": "my-environment-name" },
    "scenario": "coding:my_bug_fix_mcp"
  }
]
```

---

## Running Remote Evaluations

### Basic command

```bash
hud eval remote_tasks.json claude --remote -v -y
```

This runs all tasks in `remote_tasks.json` using the Claude agent, fully remote on HUD infrastructure.

### Key flags

| Flag | Description |
|---|---|
| `--remote` | Run both agent and environment on HUD infrastructure (recommended) |
| `--group-size N` | Repeat each task N times (for measuring variance) |
| `--max-steps N` | Maximum agent turns before timeout |
| `--task-ids id1,id2` | Only run specific tasks from the file |
| `-v` | Verbose output |
| `-y` | Auto-confirm (skip interactive prompts) |

### Example commands

```bash
# Run all tasks, 3 attempts each, max 30 steps
hud eval remote_tasks.json claude --remote --group-size 3 --max-steps 30 -v -y

# Run a single task for quick iteration
hud eval remote_tasks.json claude --remote --task-ids my-bug-fix --max-steps 20 -v -y

# Run with a different agent
hud eval remote_tasks.json openai --remote --group-size 2 --max-steps 30 -v -y
```

### `.hud_eval.toml`

You can set default flags in `.hud_eval.toml` at the project root instead of passing them every time:

```toml
[eval]
# source = "remote_tasks.json"
# agent = "claude"
# max_steps = 30
# group_size = 2
# verbose = true
# auto_respond = true

[claude]
# model = "claude-sonnet-4-5"
# max_tokens = 16384
```

Command-line arguments override these settings.

### Viewing results

After starting an eval, the CLI prints a job URL:

```
Job URL: https://hud.ai/jobs/<job-id>
```

Open it to see per-task scores, transcripts, and agent traces.

---

## End-to-End Checklist

1. **Author** your scenario in `tasks/` and register it in `tasks/__init__.py`
2. **Configure** `repo_config.yaml` with your source repo and branches
3. **Build** locally: `uv run build`
4. **Test** interactively: `uv run dev my_scenario` then `sdlc-test`
5. **Validate** grading: `VALIDATE_MODE=baseline_fail sdlc-test` and `VALIDATE_MODE=golden_pass sdlc-test`
6. **Deploy** to HUD: `uv run deploy`
7. **Create** `remote_tasks.json` with your environment name and scenario
8. **Run** remote eval: `hud eval remote_tasks.json claude --remote --group-size 3 -v -y`
9. **Review** results at the job URL

---

## Troubleshooting

**`uv sync` fails resolving `hud-sdlc-lib`**: Your `LIB_GITHUB_PAT` is missing or doesn't have read access to `hud-evals/hud-sdlc-lib`. Check your `.env` file.

**`uv run dev` fails with "input device is not a TTY"**: `uv run dev` requires an interactive terminal. For CI or non-interactive testing, use the `docker run` smoke test command instead.

**`env.name` resolves to the wrong environment**: Another environment in your account has the same name. Set a unique `ENV_NAME` in `.env` and redeploy. Verify the name in the deploy output matches what's in `remote_tasks.json`.

**Deploy succeeds but eval fails with "environment not found"**: The `env.name` in your task file must exactly match the deployed environment name (case-sensitive). Check the deploy output.

**Deploy missing data files**: `hud deploy` uses `.gitignore` to filter the upload tarball. If your data directories (`linear_data/`, `github_data/`, `sentry_data/`) are gitignored, they won't reach the remote build. Remove them from `.gitignore` or use a `.hudignore` if available.

**Grading fails with missing dependencies**: Dependencies needed by test commands (e.g., `pytest`, `psycopg2-binary`) must be installed in the container. Add them to `pyproject.toml` or install them explicitly in `Dockerfile.hud`.

**Stale results after redeployment**: Remote evals automatically use the latest deployed version. If you're seeing stale behavior, verify the deploy completed successfully and that `remote_tasks.json` points to the correct environment name.
