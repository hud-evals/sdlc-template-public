# Adding Linear MCP Tools

This guide explains how to give your agent access to mock Linear project-management tools so it can investigate issues, read comments, browse team context, and discover engineering tickets — all backed by static JSON files you control.

## What the Agent Gets

When you wire up the Linear MCP, the agent gains **26 tools** that mirror the official Linear MCP API:

| Category | Tools |
|---|---|
| **Identity** | `linear_whoami` |
| **Issues** | `linear_get_issue`, `linear_list_issues`, `linear_create_issue`, `linear_update_issue`, `linear_delete_issue` |
| **Issue Status** | `linear_get_issue_status`, `linear_list_issue_statuses` |
| **Comments** | `linear_list_comments`, `linear_create_comment` |
| **Teams** | `linear_list_teams`, `linear_get_team` |
| **Users** | `linear_list_users`, `linear_get_user` |
| **Projects** | `linear_list_projects`, `linear_get_project`, `linear_create_project`, `linear_update_project` |
| **Labels** | `linear_list_issue_labels`, `linear_create_issue_label`, `linear_list_project_labels` |
| **Cycles** | `linear_list_cycles` |
| **Documents** | `linear_list_documents`, `linear_get_document`, `linear_create_document`, `linear_update_document` |

The agent interacts with these tools exactly as it would with a real Linear workspace. All data comes from JSON files you provide — no Linear account or API key needed.

---

## Quick Start

### 1. Create a `linear_data/` directory

Copy the example data into your project as a starting point:

```bash
cp -r docs/examples/linear/ linear_data/
```

Or create the directory from scratch with your own data:

```
my-eval/
├── env.py
├── linear_data/
│   ├── issues.json              # required
│   ├── teams.json               # required
│   ├── users.json               # required
│   ├── workflow_states.json     # required
│   └── labels.json              # required
├── tasks/
└── ...
```

### 2. Wire up in `env.py`

Add these lines to your `env.py`:

```python
from pathlib import Path
from sdlc.mcp.linear import LinearService

# Initialize Linear MCP with your data directory
linear = LinearService(data_dir=str(Path(__file__).parent / "linear_data"))
env.connect_server(linear.server)
```

That's it — three lines. The `LinearService` class handles loading the JSON, creating the FastMCP server, and registering all 26 tools.

`Path(__file__).parent / "linear_data"` resolves to the right path whether you're running locally or inside the container (where `env.py` is at `/mcp_server/env.py`).

### 3. Copy data into Docker

Add this line to your `Dockerfile.hud`, after the other `COPY` directives:

```dockerfile
COPY ./linear_data /mcp_server/linear_data
```

---

## Data Files

A complete example data set is in [`docs/examples/linear/`](examples/linear/). You can copy the whole directory and modify it, or build your own from scratch.

### Required Files

| File | What it contains | Example |
|---|---|---|
| `issues.json` | Array of issue objects — the tickets the agent discovers | [issues.json](examples/linear/issues.json) |
| `teams.json` | Array of team objects — team structure and keys | [teams.json](examples/linear/teams.json) |
| `users.json` | Array of user objects — assignees, commenters, leads | [users.json](examples/linear/users.json) |
| `workflow_states.json` | Array of state objects — Backlog, In Progress, Done, etc. | [workflow_states.json](examples/linear/workflow_states.json) |
| `labels.json` | Array of label objects — Bug, Feature, P1, etc. | [labels.json](examples/linear/labels.json) |

### Optional Files

| File | What it contains | Example |
|---|---|---|
| `projects.json` | Array of project objects — groups issues with progress/health | [projects.json](examples/linear/projects.json) |
| `cycles.json` | Array of cycle objects — sprint/iteration data | [cycles.json](examples/linear/cycles.json) |
| `documents.json` | Array of document objects — architecture docs, runbooks | [documents.json](examples/linear/documents.json) |
| `viewer.json` | Single user object — the "authenticated" user for `linear_whoami` | [viewer.json](examples/linear/viewer.json) |
| `project_labels.json` | Array of project label objects — labels for categorizing projects | [project_labels.json](examples/linear/project_labels.json) |

If `viewer.json` is missing, the first user in `users.json` is used as the authenticated user. If `users.json` is also empty, a default `agent@example.com` identity is created.

---

## Field Reference

This section documents the fields for each file. Refer to the [example files](examples/linear/) for complete, copy-pasteable JSON.

### `issues.json`

This is the most important file — it defines what the agent can find when investigating.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier (UUID or any string) |
| `identifier` | string | Yes | Human-readable ID like `ENG-42`. Must follow `TEAMKEY-NUMBER` format. |
| `title` | string | Yes | Issue title |
| `description` | string | No | Markdown body with details, repro steps, etc. |
| `priority` | int | No | `0`=None, `1`=Urgent, `2`=High, `3`=Medium, `4`=Low |
| `url` | string | No | Link (can be fake, agent doesn't navigate to it) |
| `createdAt` | string | No | ISO 8601 timestamp |
| `updatedAt` | string | No | ISO 8601 timestamp |
| `completedAt` | string\|null | No | ISO 8601 timestamp or null |
| `state` | object | No | `{id, name, type, color}` — must reference a `workflow_states.json` entry |
| `assignee` | object\|null | No | `{id, name, email}` — must reference a `users.json` entry |
| `team` | object | No | `{id, name, key}` — must reference a `teams.json` entry |
| `project` | object\|null | No | `{id, name, state}` — must reference a `projects.json` entry |
| `labels` | object | No | `{nodes: [{id, name, color}]}` — must reference `labels.json` entries |
| `comments` | object | No | `{nodes: [{id, body, createdAt, user: {id, name}}]}` |

### `teams.json`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier |
| `name` | string | Yes | Display name |
| `key` | string | Yes | Short prefix used in issue identifiers (e.g., `ENG` in `ENG-42`) |
| `description` | string | No | Team description |
| `icon` | string | No | Emoji icon |
| `color` | string | No | Hex color |
| `cyclesEnabled` | bool | No | Whether cycles/sprints are enabled |
| `triageEnabled` | bool | No | Whether triage workflow is enabled |
| `private` | bool | No | Team visibility |

### `users.json`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier |
| `name` | string | Yes | Full name |
| `email` | string | No | Email address |
| `displayName` | string | No | Short display name |
| `active` | bool | No | Whether user is active |
| `admin` | bool | No | Admin flag |

### `workflow_states.json`

Defines the issue lifecycle stages for each team. The `type` field determines how the mock filters issues.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier |
| `name` | string | Yes | Display name (e.g., "In Progress") |
| `type` | string | Yes | One of: `backlog`, `unstarted`, `started`, `completed`, `canceled` |
| `color` | string | No | Hex color |
| `teamId` | string | Yes | Which team this state belongs to |

Each team should have at least one state of each `type`, especially `backlog` (used as the default for new issues).

### `labels.json`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier |
| `name` | string | Yes | Label name |
| `color` | string | No | Hex color |
| `description` | string | No | Label description |
| `teamId` | string | No | Scope label to a specific team |

### `projects.json`

See [projects.json example](examples/linear/projects.json) for all fields. Key fields: `id`, `name`, `state` (backlog/planned/started/paused/completed/canceled), `lead`, `teams.nodes[]`.

### `cycles.json`

See [cycles.json example](examples/linear/cycles.json). Key fields: `id`, `number`, `name`, `startsAt`, `endsAt`, `isActive`, `progress`, `teamId`.

### `documents.json`

See [documents.json example](examples/linear/documents.json). Key fields: `id`, `title`, `content` (Markdown), `slugId`, `creator`, `project`, `team`.

### `viewer.json`

Same shape as a user object. See [viewer.json example](examples/linear/viewer.json).

### `project_labels.json`

See [project_labels.json example](examples/linear/project_labels.json). Key fields: `id`, `name`, `color`, `description`.

---

## Designing Effective Data

The JSON schemas above are mechanical — the hard part is crafting data that creates a realistic investigation experience for the agent.

### Make issues tell a story

Your Linear issues should mirror how a real engineering team would track the bugs you've planted. Good issues contain:

- **Symptoms** the team has observed ("API returns 500 on task creation")
- **Clues** that point toward root causes without giving away the answer ("migration 003 shows as applied but column doesn't exist")
- **Cross-references** between related issues ("Related to ENG-42")

### Use comments as breadcrumbs

Issue comments are where engineers share debugging context. Plant clues here:

```json
{
  "body": "I checked the Alembic migration history — migration 003 shows as applied but the column doesn't exist. Something is off with the migration setup.",
  "user": { "id": "user-003", "name": "Jordan Kim" }
}
```

The agent reads these comments via `linear_list_comments` and uses them to narrow its investigation.

### Include noise issues

Don't only include issues for bugs the agent needs to fix. Add some unrelated issues to test the agent's ability to triage:

- A low-priority feature request in Backlog
- An infrastructure ticket on a different team
- A completed issue from a previous sprint

This forces the agent to identify which issues are actually relevant to the current problem.

### Keep identifiers realistic

Use team-prefixed identifiers that look real: `ENG-42`, `INF-12`, `BE-103`. The team key in the identifier must match the `key` field in your `teams.json`.

### Match IDs across files

All cross-references must be consistent:

- An issue's `state.id` must match an entry in `workflow_states.json`
- An issue's `team.id` must match an entry in `teams.json`
- An issue's `assignee.id` must match an entry in `users.json`
- Workflow states' `teamId` must match the team they belong to
- Labels' `teamId` must match their team (if team-scoped)

The mock doesn't enforce referential integrity, but mismatched IDs will cause confusing behavior when the agent tries to filter or look up entities.

---

## `env.py` example

Here's a complete `env.py` that wires up Linear MCP alongside the standard tools:

```python
"""Coding environment with Linear MCP tools."""

import logging
from pathlib import Path

from sdlc import CodingEnvironment
from sdlc.mcp.linear import LinearService

logger = logging.getLogger(__name__)

env = CodingEnvironment("coding")

# --- Linear MCP ---
linear = LinearService(data_dir=str(Path(__file__).parent / "linear_data"))
env.connect_server(linear.server)

# Import tasks after env is defined to avoid circular import
import tasks  # noqa: F401, E402
```

And a hud scenario that uses it:

```python
# tasks/my_task.py
from env import env
from sdlc import Grade, UnitTestGrader, setup_repo

@env.scenario(name="my_bug_fix")
async def my_bug_fix():
    setup_repo(
        source="/home/root/source/my_repo",
        target="/home/ubuntu/workspace/my_repo",
        branches=["baseline"],
        checkout="baseline",
    )

    yield (
        "You are the on-call engineer. A P1 has fired — task creation is failing.\n\n"
        "Use Linear tools to investigate the engineering tickets for context, "
        "then fix the root cause in the codebase.\n\n"
        "The repository is at /home/ubuntu/workspace/my_repo."
    )

    grade = Grade.from_subscores([
        UnitTestGrader.grade(
            weight=1.0,
            files=["test_fix.py"],
            command="python -m pytest test_fix.py -v",
            source_repo="/home/root/source/my_repo",
            base_ref="baseline",
            test_ref="test",
            repo_path="/home/ubuntu/workspace/my_repo",
        ),
    ])
    yield grade.score
```

## Dockerfile Changes

Add one `COPY` line to your `Dockerfile.hud`:

```dockerfile
# After other COPY directives
COPY ./linear_data /mcp_server/linear_data
```

If you have multiple data directories for different scenarios:

```dockerfile
COPY ./linear_data /mcp_server/linear_data
COPY ./linear_data_v2 /mcp_server/linear_data_v2
```

---

## How the Agent Uses These Tools

A typical agent investigation flow:

1. **`linear_list_teams`** — discover what teams exist
2. **`linear_list_issues`** with `state="started"` or `priority=1` — find urgent/active issues
3. **`linear_get_issue`** on a specific issue — read full description and metadata
4. **`linear_list_comments`** — read engineering discussion and debugging notes
5. **`linear_list_documents`** — find architecture docs or runbooks
6. **Use bash/editor tools** — investigate the codebase based on clues from Linear
7. **`linear_create_comment`** — (optional) agent leaves a note about what it found
8. **`linear_update_issue`** — (optional) agent moves the issue to Done

The agent can also create issues, labels, projects, and documents — all stored in-memory for the session. These mutations don't persist between runs.

---

## Troubleshooting

**Agent can't find any issues**: Check that `data_dir` resolves to the right path. Add a log line: `logger.info("Linear data_dir: %s", linear.data.data_dir)`.

**Issue filtering returns empty results**: Verify that the `state.type`, `team.id`, and `assignee.id` values in `issues.json` match exactly with the entries in `workflow_states.json`, `teams.json`, and `users.json`.

**"Team 'X' not found" errors**: The agent is trying to filter by a team name that doesn't exist in `teams.json`. Team lookup is case-insensitive for names but exact for IDs.

**Comments not showing**: Comments must be nested under the issue as `{"comments": {"nodes": [...]}}` — note the `nodes` wrapper.

**Data reloading not taking effect**: If you're using `LinearService`, access the data layer via `linear.data.reload(...)`.
