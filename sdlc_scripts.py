"""Convenience wrappers that read .env and pass build args to hud CLI."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib import error, parse, request

def _load_env() -> dict[str, str]:
    """Load variables from .env file if it exists."""
    env_file = Path(__file__).parent / ".env"
    env: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def _build_cmd(hud_command: str) -> list[str]:
    """Build the hud CLI command with build args from .env."""
    dotenv = _load_env()

    # Inject .env values into the process environment so --secret can read them
    for key, value in dotenv.items():
        os.environ.setdefault(key, value)

    cmd = ["hud", hud_command, "."]

    # Pass build secrets (not baked into image layers)
    if os.environ.get("LIB_GITHUB_PAT"):
        cmd.extend(["--secret", "id=LIB_GITHUB_PAT,env=LIB_GITHUB_PAT"])
    if os.environ.get("SOURCE_GITHUB_PAT"):
        cmd.extend(["--secret", "id=SOURCE_GITHUB_PAT,env=SOURCE_GITHUB_PAT"])

    # Pass other build args
    folder_name = os.environ.get("FOLDER_NAME", dotenv.get("FOLDER_NAME", "workspace"))
    cmd.extend(["--build-arg", f"FOLDER_NAME={folder_name}"])

    # Override environment name via ENV_NAME (.env or env var), fallback to pyproject name
    env_name = os.environ.get("ENV_NAME", dotenv.get("ENV_NAME", ""))
    if env_name:
        if hud_command == "deploy":
            cmd.extend(["--name", env_name])
        else:
            cmd.extend(["--tag", env_name])

    cmd.extend(sys.argv[1:])
    return cmd


def _update_sdlc_lib() -> int:
    """Update hud-sdlc-lib to latest commit, returns exit code."""
    pat = _setup_git_auth()
    try:
        result = subprocess.call(["uv", "lock", "--upgrade-package", "hud-sdlc-lib"])
        if result == 0:
            result = subprocess.call(["uv", "sync"])
    finally:
        if pat:
            _teardown_git_auth(pat)
    return result


def dev():
    """Run hud dev --docker with Linear, GitHub, and Sentry frontend ports forwarded."""
    dotenv = _load_env()
    for key, value in dotenv.items():
        os.environ.setdefault(key, value)

    docker_args: list[str] = []
    for env_key in ("LINEAR_FRONTEND_PORT", "GITHUB_FRONTEND_PORT", "SENTRY_FRONTEND_PORT"):
        port = os.environ.get(env_key)
        if port:
            docker_args.extend(["-p", f"{port}:{port}", "-e", f"{env_key}={port}"])

    from sdlc.cli.dev import dev as _dev

    _dev(Path(__file__).parent, docker_args=docker_args)


def build():
    """Update hud-sdlc-lib then run hud build with build args from .env."""
    result = _update_sdlc_lib()
    if result != 0:
        raise SystemExit(result)
    raise SystemExit(subprocess.call(_build_cmd("build")))


def deploy():
    """Run hud deploy with build args from .env."""
    raise SystemExit(subprocess.call(_build_cmd("deploy")))


def _setup_git_auth() -> str | None:
    """Configure git to use LIB_GITHUB_PAT for hud-evals repos. Returns the PAT if set."""
    dotenv = _load_env()
    for key, value in dotenv.items():
        os.environ.setdefault(key, value)

    pat = os.environ.get("LIB_GITHUB_PAT")
    if pat:
        subprocess.run(
            ["git", "config", "--global", "url.https://{}@github.com/hud-evals/.insteadOf".format(pat),
             "https://github.com/hud-evals/"],
            check=True,
        )
    return pat


def _teardown_git_auth(pat: str) -> None:
    """Remove the temporary git credential rewrite."""
    subprocess.run(
        ["git", "config", "--global", "--remove-section",
         "url.https://{}@github.com/hud-evals/".format(pat)],
        check=False,
    )


def update():
    """Update hud-sdlc-lib to latest commit, using LIB_GITHUB_PAT from .env."""
    raise SystemExit(_update_sdlc_lib())


def setup():
    """Run scenario setup for a task against a running hud dev --docker server."""
    from sdlc.cli.setup import setup as _setup

    tasks_by_name, _ = _collect_tasks()
    _setup(tasks_by_name)


def _collect_tasks() -> tuple[dict[str, Any], dict[str, str]]:
    """Import tasks package and return task objects + task IDs.

    Returns:
      - name -> Task object mapping
      - name -> task_id mapping from Task.slug
    """
    project_root = str(Path(__file__).parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import tasks as tasks_pkg

    raw_tasks = getattr(tasks_pkg, "tasks", {})
    tasks_by_name = raw_tasks if isinstance(raw_tasks, dict) else {}
    if not tasks_by_name:
        print("No Task objects found in tasks/ subpackages.")
    raw = getattr(tasks_pkg, "task_ids", {})
    if not isinstance(raw, dict):
        return tasks_by_name, {}
    task_ids = {
        str(folder_name): str(task_id)
        for folder_name, task_id in raw.items()
        if isinstance(folder_name, str) and isinstance(task_id, str)
    }
    return tasks_by_name, task_ids


def _api_json(
    method: str,
    *,
    api_url: str,
    api_key: str,
    path: str,
    payload: dict | list | None = None,
    params: dict[str, str | int] | None = None,
):
    """Execute an authenticated JSON request against the HUD API."""
    url = f"{api_url.rstrip('/')}{path}"
    if params:
        url = f"{url}?{parse.urlencode(params)}"

    headers = {"Authorization": f"Bearer {api_key}"}
    body: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()

    req = request.Request(url, headers=headers, data=body, method=method.upper())
    try:
        with request.urlopen(req) as resp:  # noqa: S310
            raw = resp.read()
            return json.loads(raw.decode()) if raw else None
    except error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                detail = str(parsed.get("detail") or parsed)
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"{method.upper()} {path} failed ({e.code}): {detail}") from e

def new_task():
    """Scaffold a new task directory.

    Usage: new-task <task_name>

    Creates tasks/<task_name>/ with __init__.py, task.py, and golden.patch.
    """
    import argparse
    import re

    parser = argparse.ArgumentParser(description="Scaffold a new task")
    parser.add_argument("name", help="Task name in snake_case (e.g. 'fix_auth_bug')")
    args = parser.parse_args()

    name: str = args.name
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        print(f"Invalid task name '{name}'. Use snake_case (e.g. 'fix_auth_bug').")
        raise SystemExit(1)

    task_dir = Path(__file__).parent / "tasks" / name
    if task_dir.exists():
        print(f"Task '{name}' already exists at {task_dir}")
        raise SystemExit(1)

    task_dir.mkdir(parents=True)

    (task_dir / "__init__.py").write_text(
        "from .task import task  # noqa: F401\n"
    )

    (task_dir / "task.py").write_text(
        "from pathlib import Path\n"
        "\n"
        "from hud.types import MCPToolCall\n"
        "from env import bug_fix\n"
        "\n"
        'WORKSPACE = "/home/ubuntu/workspace/repo"\n'
        "\n"
        "task = bug_fix.task(\n"
        '    prompt="TODO: detailed task prompt",\n'
        f'    source_repo="TODO",\n'
        f'    branch_prefix="{name}",\n'
        '    test_files=["test.py"],\n'
        ")\n"
        f'task.slug = "{name}"\n'
        "task.validation = [\n"
        '    MCPToolCall(name="bash", arguments={\n'
        """        "command": f"cd {WORKSPACE} && git apply <<'GOLDEN_PATCH'\\n"\n"""
        """        + (Path(__file__).parent / "golden.patch").read_text()\n"""
        """        + "GOLDEN_PATCH",\n"""
        "    }),\n"
        "]\n"
    )

    (task_dir / "golden.patch").write_text("")

    print(f"Created tasks/{name}/")
    print("  task.py       - edit prompt, source_repo, branch_prefix, test_files")
    print("  golden.patch  - add golden diff (use generate-golden)")

def sync_tasks():
    """Sync local task definitions to a platform taskset via API-key endpoints.

    Usage:
      sync-tasks --taskset TASKSET --env ENV_NAME [--task TASK_NAME]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync local tasks/ to a HUD taskset (taskset)"
    )
    parser.add_argument(
        "--taskset",
        default=None,
        help="taskset name or ID (falls back to TASKSET_NAME in .env)",
    )
    parser.add_argument(
        "--env",
        dest="env_name",
        default=None,
        help="Environment name/display name (defaults to ENV_NAME from .env)",
    )
    parser.add_argument(
        "--task",
        help="Only sync one task matching this directory name",
    )
    parser.add_argument(
        "--exclude-task",
        action="append",
        default=[],
        help="Exclude a task by directory name (can be passed multiple times)",
    )
    args = parser.parse_args()

    from hud.settings import settings as hud_settings

    api_key = hud_settings.api_key
    if not api_key:
        print("HUD_API_KEY is required for sync-tasks. Set it via `hud set HUD_API_KEY=...`.")
        raise SystemExit(1)

    api_url = hud_settings.hud_api_url
    dotenv = _load_env()
    if not args.taskset:
        args.taskset = dotenv.get("TASKSET_NAME", "")
    if not args.taskset:
        print("Taskset is required. Pass --taskset or set TASKSET_NAME in .env.")
        raise SystemExit(1)

    env_name = args.env_name or _load_env().get("ENV_NAME") or os.environ.get("ENV_NAME")
    if not env_name:
        print("Environment name is required. Pass --env or set ENV_NAME in .env.")
        raise SystemExit(1)

    tasks_by_name, task_ids = _collect_tasks()
    if not tasks_by_name:
        raise SystemExit(1)

    if args.task:
        if args.task not in tasks_by_name:
            print(f"Task '{args.task}' not found. Available: {', '.join(sorted(tasks_by_name))}")
            raise SystemExit(1)
        tasks_by_name = {args.task: tasks_by_name[args.task]}
    else:
        excluded = {name for name in args.exclude_task if name}
        if excluded:
            missing_excludes = [name for name in sorted(excluded) if name not in tasks_by_name]
            if missing_excludes:
                print(
                    "Excluded task(s) not found: "
                    + ", ".join(missing_excludes)
                    + f". Available: {', '.join(sorted(tasks_by_name))}"
                )
                raise SystemExit(1)
            tasks_by_name = {
                name: task for name, task in tasks_by_name.items() if name not in excluded
            }
            if not tasks_by_name:
                print("No tasks left to sync after exclusions.")
                raise SystemExit(1)

    try:
        local_specs: list[dict[str, Any]] = []
        missing_task_ids: list[str] = []
        for task_name, task in tasks_by_name.items():
            scenario_name = getattr(task, "scenario", None)
            if not scenario_name:
                raise RuntimeError(f"Task '{task_name}' has no scenario configured")
            args_dict = getattr(task, "args", None) or {}
            if not isinstance(args_dict, dict):
                raise RuntimeError(
                    f"Task '{task_name}' has non-dict args; found {type(args_dict).__name__}"
                )
            task_id_hint = task_ids.get(task_name)
            if not isinstance(task_id_hint, str) or not task_id_hint.strip():
                missing_task_ids.append(task_name)
                continue
            task_id = task_id_hint.strip()
            local_specs.append(
                {
                    "name": task_name,
                    "task_id": task_id,
                    "scenario_name": str(scenario_name),
                    "args": args_dict,
                    "signature": f"{scenario_name}|"
                    + json.dumps(
                        args_dict,
                        sort_keys=True,
                        default=str,
                        separators=(",", ":"),
                    ),
                }
            )

        if missing_task_ids:
            raise RuntimeError(
                "Tasks missing stable task_id (slug): "
                + ", ".join(sorted(missing_task_ids))
                + ". Set task.slug on each task."
            )

        task_id_to_names: dict[str, list[str]] = {}
        for spec in local_specs:
            task_id = str(spec["task_id"])
            task_id_to_names.setdefault(task_id, []).append(str(spec["name"]))
        duplicate_task_ids = {
            task_id: names
            for task_id, names in task_id_to_names.items()
            if len(names) > 1
        }
        if duplicate_task_ids:
            formatted = ", ".join(
                f"{task_id} -> {', '.join(sorted(names))}"
                for task_id, names in sorted(duplicate_task_ids.items())
            )
            raise RuntimeError(f"Duplicate local task IDs detected: {formatted}")

        taskset_exists = True
        taskset_id = ""
        taskset_name = args.taskset
        remote_tasks: list[dict[str, Any]] = []
        try:
            taskset_payload = _api_json(
                "GET",
                api_url=api_url,
                api_key=api_key,
                path=f"/tasks/evalset/{parse.quote(args.taskset, safe='')}",
            )
            if not isinstance(taskset_payload, dict):
                raise RuntimeError("Unexpected response from /tasks/evalset")
            tasks_payload = taskset_payload.get("tasks") or {}
            if not isinstance(tasks_payload, dict):
                raise RuntimeError("Unexpected tasks payload from /tasks/evalset")
            taskset_id = str(taskset_payload.get("taskset_id") or "")
            taskset_name = str(taskset_payload.get("taskset_name") or args.taskset)
            remote_tasks = [entry for entry in tasks_payload.values() if isinstance(entry, dict)]
        except RuntimeError as e:
            if "failed (404)" in str(e):
                taskset_exists = False
            else:
                raise

        remote_by_slug: dict[str, dict[str, Any]] = {}
        for task in remote_tasks:
            remote_slug = task.get("slug") or task.get("external_id")
            if isinstance(remote_slug, str) and remote_slug:
                remote_by_slug[remote_slug] = task

        to_create: list[dict[str, Any]] = []
        to_update: list[dict[str, Any]] = []
        unchanged = 0
        for spec in local_specs:
            task_id = str(spec["task_id"])
            existing = remote_by_slug.get(task_id)
            if existing is None:
                to_create.append(spec)
                continue

            current_signature = (
                f"{str(existing.get('scenario') or '')}|"
                + json.dumps(
                    existing.get("args") if isinstance(existing.get("args"), dict) else {},
                    sort_keys=True,
                    default=str,
                    separators=(",", ":"),
                )
            )
            if current_signature == str(spec["signature"]):
                unchanged += 1
            else:
                to_update.append(spec)

        print(
            f"\nSync plan for taskset '{taskset_name}' ({taskset_id or 'new'}) on env '{env_name}':"
        )
        if not taskset_exists:
            print("  taskset will be created")
        if to_create:
            print(f"\n  Create ({len(to_create)}):")
            for spec in sorted(to_create, key=lambda entry: str(entry["task_id"])):
                print(f"    + {spec['name']} ({spec['task_id']})")
        if to_update:
            print(f"\n  Update ({len(to_update)}):")
            for spec in sorted(to_update, key=lambda entry: str(entry["task_id"])):
                print(f"    ~ {spec['name']} ({spec['task_id']})")
        if unchanged:
            print(f"\n  Unchanged: {unchanged}")

        to_upload = sorted(
            [*to_create, *to_update],
            key=lambda entry: str(entry["task_id"]),
        )
        if not to_upload:
            print("\nNothing to sync — all tasks up to date.")
            return

        try:
            answer = input("\nProceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(1)
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

        upload_response = _api_json(
            "POST",
            api_url=api_url,
            api_key=api_key,
            path="/tasks/upload",
            payload={
                "name": taskset_name,
                "tasks": [
                    {
                        "slug": str(spec["task_id"]),
                        "env": {"name": env_name},
                        "scenario": str(spec["scenario_name"]),
                        "args": spec["args"] if isinstance(spec["args"], dict) else {},
                    }
                    for spec in to_upload
                ],
            },
        )
        if not isinstance(upload_response, dict):
            raise RuntimeError("Unexpected response from /tasks/upload")

        created = int(upload_response.get("tasks_created") or 0)
        updated = int(upload_response.get("tasks_updated") or 0)
        print("Sync complete.")
        print(f"  - created: {created}")
        print(f"  - updated: {updated}")
        print(f"  - unchanged: {unchanged}")
    except RuntimeError as e:
        print(f"sync-tasks failed: {e}")
        raise SystemExit(1) from e


def generate_golden():
    """Generate a golden.patch file from a GitHub diff between two branches.

    Usage: generate-golden <task_name> <repo_url> <base_branch> <golden_branch>

    Example:
        generate-golden basic https://github.com/hud-evals/coding-template-sample \\
            server_fix_baseline server_fix_golden
    """
    import argparse
    import urllib.request

    parser = argparse.ArgumentParser(description="Generate golden.patch from git diff")
    parser.add_argument("task_name", help="Task name (writes to tasks/<task_name>/golden.patch)")
    parser.add_argument("repo_url", help="GitHub repo URL (e.g. https://github.com/org/repo)")
    parser.add_argument("base", help="Baseline branch name")
    parser.add_argument("golden", help="Golden branch name")
    args = parser.parse_args()

    task_dir = Path(__file__).parent / "tasks" / args.task_name
    if not task_dir.exists():
        print(f"Task directory tasks/{args.task_name}/ does not exist. Run new-task first.")
        raise SystemExit(1)

    parts = args.repo_url.rstrip("/").removesuffix(".git").split("/")
    owner, repo = parts[-2], parts[-1]

    api_url = f"https://api.github.com/repos/{owner}/{repo}/compare/{args.base}...{args.golden}"
    req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github.v3.diff"})

    pat = os.environ.get("SOURCE_GITHUB_PAT") or _load_env().get("SOURCE_GITHUB_PAT")
    if pat:
        req.add_header("Authorization", f"token {pat}")

    with urllib.request.urlopen(req) as resp:  # noqa: S310
        patch = resp.read().decode()

    if not patch.strip():
        print(f"Empty diff between {args.base}..{args.golden}")
        raise SystemExit(1)

    patch_path = task_dir / "golden.patch"
    patch_path.write_text(patch)
    print(f"Wrote {patch_path}")


def validate():
    """Run baseline-fail + golden replay validation.

    Usage: validate [task_name] [--url URL]

    If task_name is given, validates only tasks whose directory name
    contains that string.  Otherwise validates all tasks.
    """
    from sdlc.cli.validate import validate as _validate

    args = sys.argv[1:]

    url = None
    if "--url" in args:
        idx = args.index("--url")
        url = args[idx + 1]
        del args[idx : idx + 2]

    task_name = next((a for a in args if not a.startswith("-")), None)

    all_tasks, _ = _collect_tasks()
    if not all_tasks:
        raise SystemExit(1)

    if task_name:
        matched = {k: v for k, v in all_tasks.items() if task_name in k}
        if not matched:
            print(f"No tasks matching '{task_name}'")
            print(f"Available: {', '.join(sorted(all_tasks))}")
            raise SystemExit(1)
        tasks = list(matched.values())
    else:
        tasks = list(all_tasks.values())

    _validate(tasks, url=url, project_dir=Path(__file__).parent)
