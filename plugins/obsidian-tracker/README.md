# Obsidian Tracker

Project tracking, task management with kanban boards, bug logging, decision records (ADR), session management, and engineering traceability via Obsidian. **Auto-tracks sessions, actions, bugs, and commits via hooks.**

## Installation

**Claude Code:**
```bash
/plugin marketplace add https://github.com/IvanLutsenko/awac-ai-agent-plugins
/plugin install obsidian-tracker   # MCP server auto-builds on first run
```

**Codex CLI:**
```bash
codex plugin marketplace add IvanLutsenko/awac-ai-agent-plugins
codex plugin add obsidian-tracker@awac-ai-agent-plugins
```

> The Obsidian features run through an MCP server (`plugins/obsidian-tracker/mcp`).
> Auto-tracking hooks are Claude Code-specific and do not run under Codex.

## Features

- **Project Management**: List, create, archive, restore, and delete projects
- **Subproject Tree**: Hierarchical project view with `X.Y` numbering for nested subprojects
- **Task Management**: Kanban board with Backlog/In Progress/Review/Done columns
- **Bug Lifecycle**: Create, track, and close bug reports with priority levels
- **Decision Records (ADR)**: Lightweight Architecture Decision Records with lifecycle (Active → Closed/Superseded)
- **Entity Linking**: Link commits, PRs, tasks, bugs, and decisions to each other for traceability
- **Session Logging**: Record Claude Code sessions with structured summaries
- **Auto-Tracking**: Automatic session, file edit, and commit tracking via hooks
- **Orphan Recovery**: Detects stale tracking files from crashed/closed sessions and auto-saves them
- **Resume Context**: `/where-was-i` aggregates last session, active tasks, open bugs, and decisions
- **Project Lifecycle**: Active → Archived → Deleted
- **Search**: Find projects by tags or content

## Commands

| Command | Description |
|---------|-------------|
| `/projects` | List all projects |
| `/projects [name]` | Show project details |
| `/project-new` | Create new project |
| `/project-bug [project]` | Create bug report |
| `/bug-close [project]` | Close a bug report |
| `/project-archive [action] [project]` | Archive, restore, or delete a project |
| `/task [project] [title]` | Create a task on the kanban board |
| `/done [project] [task-id]` | Mark task as done |
| `/today [project]` | Show today's tasks and progress |
| `/pulse [project]` | Project health and activity overview |
| `/import [project]` | Import data into a project |
| `/session-log [project]` | Manual session log |
| `/track-start [project]` | Start auto-tracking |
| `/track-stop` | Stop tracking + save to Obsidian |
| `/track-status` | Show current tracking status |
| `/where-was-i` | Resume context: last session, active tasks, open bugs, decisions |
| `/decision-new` | Create a lightweight ADR |
| `/decision-close [id]` | Close an active decision |
| `/decision-supersede [id]` | Supersede a decision with a new one |
| `/decision-link [id]` | Link commits, PRs, tasks, or bugs to a decision |

## Auto-Tracking

### How it works

```
/track-start my-project
    ↓
Work normally — edit files, commit, use TodoWrite
    ↓
Actions, file edits, and commits automatically recorded
    ↓
/clear or /track-stop
    ↓
Session + structured summary saved to Obsidian
```

### Hooks

| Hook | Trigger | Type | Action |
|------|---------|------|--------|
| PreCompact | Before context compression | prompt | Preserves tracking info in summary |
| SessionStart:clear | `/clear` | command + prompt | Bash saves raw session to vault; prompt enriches with semantic summary |
| SessionStart:compact\|resume | Context compact, resume | command | Remind about active tracking |
| SessionStart:startup | Fresh session | command | Orphan recovery + auto-detect project via `findProjectByLocalPath` |
| PostToolUse:TodoWrite | TodoWrite | prompt | Records completed todos to tracking file |
| PostToolUse:Edit | Edit | command | Records edited filenames to tracking file |
| PostToolUse:Write | Write | command | Records created filenames to tracking file |
| PostToolUse:Bash | Bash (git commit) | command | Captures commit hashes to tracking file |
| Stop | Agent turn ends | prompt | Reviews turn; closes tasks, logs bugs/decisions if relevant |

> Command-type hooks are bash scripts in `hooks/` — they never error even if the MCP server is unavailable. Prompt-type hooks depend on Claude executing the instruction.

### Orphan recovery

If a session was interrupted (terminal closed, crash), the startup hook detects stale tracking files (>5 min old) and auto-saves them to Obsidian before starting a new session.

### Tracking file

Located at `.claude/obsidian-tracking.json`:
```json
{
  "project": "my-project",
  "goal": "Fix bugs",
  "startedAt": "2024-01-29T10:00:00Z",
  "actions": ["✅ Fix search", "✏️ README.md", "💾 commit a1b2c3d"],
  "linkedCommits": ["a1b2c3d"]
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `initVault` | Initialize with vault path |
| `getConfig` | Get current configuration |
| `listProjects` | List all projects with subproject tree (supports `includeArchived`) |
| `getProject` | Get project details |
| `createProject` | Create new project |
| `archiveProject` | Archive a project (move to `_archive/`) |
| `restoreProject` | Restore an archived project |
| `deleteProject` | Permanently delete a project |
| `addTask` | Create task with auto-increment ID + kanban board |
| `updateTask` | Move task between kanban columns |
| `deleteTask` | Delete task from project and board |
| `listTasks` | List tasks with board statuses |
| `updateProject` | Update description, status, or append context to README |
| `addBug` | Add bug report |
| `closeBug` | Close a bug report (exact or partial title match) |
| `addSession` | Add session log |
| `addSessionSummary` | Create structured session summary with linked entities |
| `getResumeContext` | Aggregate last session, active tasks, open bugs, decisions |
| `findProjectByLocalPath` | Find project by local filesystem path |
| `addDecision` | Create lightweight ADR with auto-increment ID |
| `getDecision` | Get decision details by ID |
| `closeDecision` | Close a decision |
| `supersedeDecision` | Supersede a decision with a new one (closes old, creates new) |
| `listDecisions` | List decisions, optionally filtered by status |
| `linkEntity` | Link commits/PRs/decisions/sessions to any entity |
| `search` | Search by tag (e.g., `tag:bug`) |

## Permissions

The plugin auto-allows non-destructive MCP tools via a `PermissionRequest` hook (`hooks/auto-allow-mcp.sh`) — no manual approval needed for the operations below. Destructive tools always fall through to the default permission flow and require explicit user approval.

### Auto-allowed (read-only)

| Tool | Description |
|------|-------------|
| `findProjectByLocalPath` | Find project by local filesystem path |
| `getConfig` | Get current configuration |
| `getDecision` | Get decision details by ID |
| `getProject` | Get project details |
| `getResumeContext` | Aggregate last session, tasks, bugs, decisions |
| `initVault` | Initialize with vault path |
| `listDecisions` | List decisions, optionally filtered by status |
| `listProjects` | List all projects |
| `listTasks` | List tasks with board statuses |
| `search` | Search by tag |

### Auto-allowed (mutating)

| Tool | Description |
|------|-------------|
| `addBug` | Add bug report |
| `addDecision` | Create lightweight ADR |
| `addSession` | Add session log |
| `addSessionSummary` | Create structured session summary |
| `addTask` | Create task with auto-increment ID + kanban board |
| `archiveProject` | Archive a project (move to `_archive/`) |
| `closeBug` | Close a bug report |
| `closeDecision` | Close a decision |
| `createProject` | Create new project |
| `linkEntity` | Link commits/PRs/decisions/sessions to entities |
| `supersedeDecision` | Supersede a decision with a new one |
| `updateProject` | Update description, status, or append README context |
| `updateTask` | Move task between kanban columns |

### Always asks (destructive)

| Tool | Description |
|------|-------------|
| `deleteProject` | Permanently delete a project |
| `deleteTask` | Delete task from project and board |
| `restoreProject` | Restore an archived project |

### Overriding the policy

The hook only **adds** an `allow` decision — it does not override `deny`/`ask` rules from your settings. To force a prompt for any auto-allowed tool, add it to `ask` (or `deny` to block) in `~/.claude/settings.json`:

```json
{
  "permissions": {
    "ask": [
      "mcp__obsidian-tracker__addTask",
      "mcp__obsidian-tracker__createProject"
    ],
    "deny": [
      "mcp__obsidian-tracker__archiveProject"
    ]
  }
}
```

To disable auto-allow entirely, disable the plugin or remove the `PermissionRequest` hook block from your local plugin copy.

## Setup

1. Install plugin:
   ```bash
   /plugin install obsidian-tracker
   ```

2. Build MCP server:
   ```bash
   cd plugins/obsidian-tracker/mcp && npm install && npm run build
   ```

3. On first command use, you'll be prompted for your Obsidian vault path.

## Obsidian Structure

```
{vault}/
├── {project-name}/
│   ├── !Project Dashboard.md    # Main dashboard (frontmatter: status, description, etc.)
│   ├── README.md                 # Project description
│   ├── Board.md                  # Kanban board (Backlog/In Progress/Review/Done)
│   ├── TASK-{id} - {title}.md   # Task files
│   ├── BUG - {title}.md         # Bug reports (Status: Open/Closed)
│   ├── Decisions/
│   │   └── DEC-{id} - {title}.md  # Decision records (ADR)
│   ├── {subproject}/             # Subproject (detected by Dashboard or README.md)
│   │   ├── !Project Dashboard.md
│   │   └── BUG - {title}.md
│   └── Sessions/
│       ├── Session - YYYY-MM-DD.md    # Session logs
│       └── Summary-{id}.md           # Structured session summaries
└── _archive/
    └── {archived-project}/       # Archived projects (same structure)
```

## Version

4.5.0

## Changelog

### 4.5.0
- **Refactor**: MCP server split — 24 tool handlers extracted from the 1900-line `index.ts` into `handlers.ts` with an injectable vault path; covered end-to-end by 40+ new vitest tests on a temp vault (83 vitest + 86 bats total)
- **Auto-build**: `.mcp.json` now launches `mcp/run-server.sh`, which builds `dist/` on first run — fresh installs work without a manual `npm install && npm run build`
- **Task ids zero-padded** to 3 digits (`TASK-007 - …`, like `DEC-007`) so files sort correctly; all lookups accept legacy unpadded names; `normalize-vault.mjs` pads existing files and rewrites board links
- **Race-safe creation**: task/decision id allocation and file writes run under a per-project lock + exclusive-create flag — concurrent calls can't collide or lose board entries
- **Session format contract**: entry rendering extracted to `renderSessionEntry()`; TS golden test + bats structure test pin the TS and bash formats together

### 4.4.0
- **Obsidian-safe filenames**: bug/task/decision titles and project names are sanitized before becoming filenames or `[[wiki-links]]` — characters Obsidian forbids (`* " \ / < > : | ?`) and link-breaking ones (`# ^ [ ]`) are replaced, trailing dots/spaces stripped, length capped. Fixes notes that mobile Obsidian / Sync refused to open.
- **Vault normalizer**: `scripts/normalize-vault.mjs [--dry-run]` renames existing files/folders with unsafe names and rewrites wiki-links that pointed to them.
- **Non-destructive board writes**: task operations no longer rebuild `Board.md` from scratch — frontmatter, custom sections with their items, and the Obsidian Kanban plugin's `%% kanban:settings %%` block are preserved.
- **Recursive search**: `search` now covers nested projects and `Sessions`/`Decisions` subfolders (was: top-level project files only); results capped at 100.
- **Fix**: frontmatter parser now reads dashed keys (`linked-tasks`, `superseded-by`) that the server itself writes.
- **Fix**: `updateTask` validates the target column instead of crashing on an unknown status.
- **Fix**: commit tracking hook now catches compound commands (`cd x && git commit`, `git -C path commit`).
- Project names can no longer escape the vault via `..`; removed unused `mcp/run-server.sh`.

### 4.3.3
- **Fix**: bundled MCP server `package.json`/`package-lock.json` version aligned with the plugin; `publish-plugin.py` now keeps them in sync automatically

### 4.3.2
- **Docs**: examples now use the renamed `awac-ai-agent-plugins` project slug

### 4.3.1
- **Fix**: tracking state is serialized as valid JSON when project names, goals, or actions contain quotes and backslashes

### 4.3.0
- **Auto-allow MCP tools via PermissionRequest hook**: `hooks/auto-allow-mcp.sh` returns `permissionDecision: allow` for 23 read-only and mutating MCP tools — no manual approval per tool call. Destructive tools (`deleteProject`, `deleteTask`, `restoreProject`) still require explicit approval. Override per-user via `ask`/`deny` rules in `~/.claude/settings.json` (see README → Permissions).

### 4.2.0
- **Reliable session save on /clear**: `session-clear.sh` now writes raw session directly to Obsidian vault via bash (no Claude dependency), then prompt hook enriches with semantic summary — guarantees data is saved even if Claude ignores the prompt
- **Prompt-based Stop hook**: Stop hook changed from `command` + `systemMessage` (unreliable) to `prompt` type — Claude actively processes task/bug/decision updates as part of its response turn
- **Backlog tasks in resume context**: `getResumeContext` now includes Backlog tasks alongside In Progress and Review — `/where-was-i` shows full picture instead of "Tasks: None"
- **Smarter suggested action**: distinguishes Continue (In Progress) / Review / Pick from backlog
- **CI removed**: GitHub Actions workflow deleted — pre-push hook runs the same tests locally
- **Pre-push test coverage check**: blocks push if changed source files lack corresponding test files

### 4.1.0
- **Silent Stop hook**: Stop hook now returns `{}` — zero noise in chat during work sessions
- Semantic review (action summaries, bug detection, decision recording) moved to `/track-stop` command and `SessionStart:clear` hook
- PostToolUse hooks continue to silently track file edits and commits as before
- Flow: `/track-start` → silent work → `/track-stop` or `/clear` adds semantics + saves

### 4.0.2
- **Fix**: shortened all hook `systemMessage` strings to 1-line prompts — verbose multi-paragraph instructions were leaking into user-visible chat
- Orphan recovery now saves data to `.claude/obsidian-orphan.json` instead of dumping JSON into the systemMessage
- Removed dead `TRACKING_DATA` variable from `session-clear.sh`

### 4.0.1
- Version bump (plugin.json only, README was not updated)

### 4.0.0
- **Decision Records (ADR)**: `addDecision`, `getDecision`, `closeDecision`, `supersedeDecision`, `listDecisions` MCP tools + `/decision-new`, `/decision-close`, `/decision-supersede`, `/decision-link` commands
- **Entity Linking**: `linkEntity` MCP tool links commits, PRs, decisions, and sessions to tasks, bugs, or decisions
- **Structured Session Summaries**: `addSessionSummary` creates machine-friendly summaries with linked entities; `/clear` now saves both session log and structured summary
- **Resume Context**: `getResumeContext` MCP tool + `/where-was-i` command — aggregates last session, active tasks, open bugs, and decisions
- **Project Lookup by Path**: `findProjectByLocalPath` MCP tool — matches projects by `localPath` frontmatter
- **Auto-track file edits**: PostToolUse:Edit/Write hooks capture edited filenames to tracking file (command-type, zero LLM overhead)
- **Auto-track commits**: PostToolUse:Bash hook captures git commit hashes to tracking file
- **Stop hook**: auto-reviews turn actions, logs bugs and decisions if significant
- **Orphan recovery**: SessionStart:startup detects stale tracking files (>5 min) from crashed/closed sessions and auto-saves them before starting a new session
- **Session-clear enhanced**: now calls `addSessionSummary` alongside `addSession` for structured data

### 3.3.1
- **Fix**: добавлен обязательный `hookEventName` в JSON-ответы всех SessionStart хуков — Claude Code v2.1.97+ валидирует схему и без этого поля показывал `hook error` на каждом запуске

### 3.3.0
- **Full MCP permissions in all commands**: every command now includes all 15 non-destructive MCP tools in `allowed-tools` — no manual approval needed for follow-up actions (e.g., `addBug` after `/projects`)
- Destructive tools (`deleteProject`, `deleteTask`) still require explicit approval

### 3.2.0
- **Smart project lookup**: `resolveProjectPath` recursively searches subprojects by short name — `addTask(project: "obsidian-tracker")` works without full path `awac-ai-agent-plugins/obsidian-tracker`
- **Subproject creation**: `createProject` now accepts `parent` parameter — `createProject(name: "Sub", parent: "Parent")` creates subproject in correct location
- **`deleteTask` tool**: Deletes task file and removes from Board.md kanban board
- **`updateProject` tool**: Update description, status, repository, localPath, or append markdown context to README
- **Task skill improvement**: `/task` now distinguishes actionable tasks from informational context — context goes to `updateProject`, tasks go to `addTask`

### 3.1.2
- Extracted inline tracking heredoc to `scripts/start-tracking.sh` — eliminates Claude Code security prompts for `$()` and brace patterns
- Updated `/projects`, `/track-start`, `/project-bug` to use external script

### 3.1.1
- Fix: explicit ban on `&nbsp;` in `/projects` table output — terminal doesn't render HTML entities

### 3.1.0
- Subproject tree: `listProjects` scans subdirectories for subprojects (detected by `!Project Dashboard.md` or `README.md`)
- `/projects` renders tree with `X.Y` numbering (e.g., `4.1`, `4.2`)
- Bug lifecycle: `closeBug` MCP tool + `/bug-close` command
- `listProjects` now counts only open bugs (reads file content to check status)
- `getProject` returns structured bug objects with `title`, `status`, `priority` instead of plain strings
- Fixed missing `allowed-tools` in commands: `project-bug`, `project-new`, `session-log`, `track-stop`
- All MCP tools now listed in `allowed-tools` of every command that uses them

### 3.0.0
- Task management: `addTask`, `updateTask`, `listTasks` with kanban board integration
- Project lifecycle: `archiveProject`, `restoreProject`, `deleteProject`
- `listProjects` now supports `includeArchived` parameter, `_archive/` folder
- New commands: `/task`, `/done`, `/today`, `/pulse`, `/import`, `/project-archive`

### 2.3.0
- SessionStart hooks converted from `prompt` to `command` type (bash scripts in `hooks/`)
- Hooks no longer error when MCP server is unavailable — graceful degradation
- Added `hooks/session-clear.sh`, `hooks/session-resume.sh`, `hooks/session-startup.sh`

### 2.2.0
- `allowed-tools` in all 7 commands — MCP tools, Bash, Read auto-approved without manual confirm
- Tracking file creation via `Bash(cat <<EOF)` instead of Write tool (Write requires prior Read for new files)
- MCP tools (`getConfig`, `listProjects`, `getProject`, `addSession`, `addBug`) in allowed-tools
- Scoped `rm` permission: only `.claude/obsidian-tracking.json`

### 2.1.1
- Fixed MCP server not loading: changed command format to use `node` with `${CLAUDE_PLUGIN_ROOT}` instead of relative shell script path

### 2.1.0
- Added hooks for auto-tracking

### 2.0.0
- Initial release with MCP server and auto-tracking hooks
