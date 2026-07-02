# CLAUDE.md — Plugin Marketplace

## Active Plugins

- **crashlytics** (v4.4.3) — Multi-platform crash analysis with git blame forensics
- **obsidian-tracker** (v4.4.0) — Project tracking, task management, session logging via Obsidian
- **locale-notifications** (v2.0.0) — macOS notifications in system language
- **combined-review** (v1.3.0) — Multi-agent code review + CodeRabbit CLI
- **clip-maker** (v1.3.0) — Automated vertical clip creator (whisper + Claude + ffmpeg)
- **drawbridge** (v0.1.0) — Bridge briefs to image-gen web UIs (Gemini/ChatGPT/Grok/Midjourney), per-target prompt tuning
- **plugin-cross-port** (v0.10.0) — Bidirectional CC ↔ Codex plugin conversion (agents → standalone Codex skills)
- **auto-theme** (v1.1.0) — Syncs Claude Code + Codex themes with macOS light/dark; bundles gruvbox-light / sunset-drive

## Plugin Structure

```
plugins/{name}/
├── .claude-plugin/plugin.json   # Manifest
├── .mcp.json                    # Optional MCP servers
├── commands/*.md                # Slash commands
├── agents/*.md                  # Agents
└── standards/*.md               # Knowledge base
```

## Command Format

```markdown
---
description: Shown in /help
argument-hint: "path/to/file"
allowed-tools: ["Read", "Write", "Bash"]
---
Instructions for Claude...
```

## Agent Format

```markdown
---
name: agent-name
description: Role description
tools: Read, Write, Bash
model: sonnet
---
System prompt...
```

## Development

```bash
# Create plugin
mkdir -p plugins/{name}/{.claude-plugin,commands,agents}

# Test locally
/plugin install ./plugins/{name}

# Publish
git add . && git commit -m "feat(name): desc" && git push
```

## Cross-Port Managed Plugins

Plugins attached through `plugin-cross-port` reconcile marketplace entries
automatically:

```bash
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace sync
python3 plugins/plugin-cross-port/scripts/cross_port.py marketplace check
```

For semantic gaps, use:

```bash
python3 plugins/plugin-cross-port/scripts/cross_port.py plugin adapt plugins/example
python3 plugins/plugin-cross-port/scripts/cross_port.py plugin adapt plugins/example --apply
```

For attached plugins, `.plugin-cross-port.marketplace.json` owns marketplace
state and each plugin `.plugin-cross-port.json` owns plugin source-of-truth.
Keep manual marketplace updates only for plugins that are not attached to
cross-port.

## Conventions

- Russian UI text for bereke/crashlytics (market-specific)
- English for technical code
- Agents load standards from `standards/*.md`

## Release Checklist

**ОБЯЗАТЕЛЬНО при каждом изменении плагина — НЕ ЗАБЫВАЙ:**

1. **Version bump** — обнови `version` в `.claude-plugin/plugin.json` (semver: patch для фиксов, minor для фич, major для breaking changes)
2. **marketplace.json** — обнови версию и описание в `.claude-plugin/marketplace.json`
3. **Plugin README** — обнови `plugins/{name}/README.md`: версию, changelog, новые команды/фичи
4. **Root README** — обнови `README.md` в корне: версию, "What's New", Quick Start если изменились команды
5. **CLAUDE.md** — обнови версию плагина в секции Active Plugins (этот файл)
6. **Commit + Push** — всё это в одном коммите, затем `git push`

Всё это делается в том же коммите что и изменения, не отдельно.
**НЕ СЧИТАЙ ЗАДАЧУ ЗАВЕРШЁННОЙ ПОКА НЕ ВЫПОЛНЕНЫ ВСЕ 6 ПУНКТОВ.**
