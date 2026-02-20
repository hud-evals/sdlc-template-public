#!/usr/bin/env python3
"""Standalone repo cloner for Docker build-time use.

Parses repo_config.yaml and clones each repo into a target directory.
Uses only stdlib so it can run early in the Docker build (before the
Python venv / hud-sdlc-lib are installed).

Authentication: reads SOURCE_GITHUB_PAT from env or /run/secrets/ for
private repos.  Public repos need no PAT.
"""

import logging
import os
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="[clone] %(message)s")
log = logging.getLogger()

DEFAULT_CONFIG = "/tmp/repo_config.yaml"
DEFAULT_SOURCE_BASE = "/home/root/source"


def _parse_repo_config(path: str) -> dict[str, dict]:
    """Minimal YAML parser for the repo_config.yaml subset we use."""
    try:
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("repos", {})
    except ImportError:
        pass

    with open(path) as f:
        lines = f.readlines()

    repos: dict[str, dict] = {}
    current_repo: str | None = None
    collecting_branches: str | None = None

    for line in lines:
        stripped = line.split("#")[0].rstrip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        content = stripped.strip()

        if indent >= 6 and collecting_branches and content.startswith("- "):
            repos[collecting_branches]["branches"].append(content[2:].strip())
            continue
        else:
            collecting_branches = None

        if indent == 0 and content == "repos:":
            continue
        elif indent == 2 and content.endswith(":"):
            current_repo = content[:-1].strip()
            repos[current_repo] = {"repo_url": "", "branches": []}
        elif indent >= 4 and current_repo and ":" in content:
            key, _, val = content.partition(":")
            key, val = key.strip(), val.strip()
            if key == "repo_url":
                repos[current_repo]["repo_url"] = val
            elif key == "branches" and val.startswith("[") and val.endswith("]"):
                repos[current_repo]["branches"] = [
                    b.strip() for b in val[1:-1].split(",") if b.strip()
                ]
            elif key == "branches" and not val:
                collecting_branches = current_repo

    return repos


def _git(repo_dir: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", repo_dir, "-c", f"safe.directory={repo_dir}", *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _get_pat() -> str:
    pat = os.environ.get("SOURCE_GITHUB_PAT", "")
    if pat:
        return pat
    try:
        with open("/run/secrets/SOURCE_GITHUB_PAT") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def clone_repos(config_path: str, source_base: str) -> None:
    repos = _parse_repo_config(config_path)
    if not repos:
        log.warning("No repos found in %s", config_path)
        return

    pat = _get_pat()
    os.makedirs(source_base, exist_ok=True)

    for repo_name, cfg in repos.items():
        url = cfg["repo_url"]
        branches = cfg.get("branches", [])
        target = os.path.join(source_base, repo_name)

        auth_url = url
        if pat and url.startswith("https://"):
            auth_url = url.replace("https://", f"https://{pat}@", 1)

        if os.path.isdir(os.path.join(target, ".git")):
            log.info("Repo %s already exists, fetching", repo_name)
            if pat:
                _git(target, "remote", "set-url", "origin", auth_url, check=False)
            _git(target, "fetch", "--all", "--tags", check=False)
        else:
            log.info("Cloning %s -> %s", url, target)
            r = subprocess.run(["git", "clone", auth_url, target], capture_output=True, text=True)
            if r.returncode != 0:
                log.error("Clone failed for %s: %s", repo_name, r.stderr.strip())
                sys.exit(1)

        if pat:
            _git(target, "remote", "set-url", "origin", url, check=False)

        for branch in branches:
            ref = f"origin/{branch}"
            if _git(target, "rev-parse", "--verify", ref, check=False).returncode != 0:
                log.warning("Branch %s not found in %s, skipping", branch, repo_name)
                continue
            _git(target, "checkout", "-f", "-B", branch, ref)

        if branches:
            _git(target, "checkout", "-f", branches[0], check=False)

        subprocess.run(["chmod", "-R", "700", target], check=False)

    log.info("Done — cloned %d repo(s)", len(repos))


if __name__ == "__main__":
    config = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG
    base = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_SOURCE_BASE
    clone_repos(config, base)
