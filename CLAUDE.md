# CLAUDE.md — Plugin Marketplace

## Active Plugins

- **bereke-business-test-gen** (v2.7.1) — Kotlin unit test generation with coverage validation
- **crashlytics** (v4.4.0) — Multi-platform crash analysis with git blame forensics
- **obsidian-tracker** (v4.2.1) — Project tracking, task management, session logging via Obsidian
- **locale-notifications** (v2.0.0) — macOS notifications in system language
- **combined-review** (v1.3.0) — Multi-agent code review + CodeRabbit CLI
- **clip-maker** (v1.3.0) — Automated vertical clip creator (whisper + Claude + ffmpeg)
- **drawbridge** (v0.1.0) — Bridge briefs to image-gen web UIs (Gemini/ChatGPT/Grok/Midjourney), per-target prompt tuning
- **plugin-cross-port** (v0.2.0) — Bidirectional CC ↔ Codex plugin conversion

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
