---
name: obsidian-tracker-track-stop
description: Stop tracking and save session to Obsidian. Use when the user invokes /track-stop.
version: 0.1.0
---

> Converted from Claude Code command `/track-stop`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.

# Track Stop Command

Останавливает трекинг и сохраняет сессию в Obsidian.

## Step 1: Check tracking

```bash
cat .claude/obsidian-tracking.json 2>/dev/null || echo "NO_TRACKING"
```

**Если NO_TRACKING:**
```
⚠️ Трекинг не активен. Нечего сохранять.
Используй /track-start чтобы начать трекинг.
```
Останови выполнение.

## Step 2: Read tracking data

Прочитай JSON из файла:
- project
- goal
- started
- actions

## Step 2.5: Semantic review

Просмотри свои действия за сессию. Добавь осмысленные 1-строчные саммари в массив actions (пропускай тривиальные — чтение файлов, ls). Если обнаружил баг — вызови addBug MCP. Если принял значимое техническое решение — вызови addDecision MCP. Запиши обновлённый tracking.json.

## Step 3: Collect final info

Спроси через AskUserQuestion:
- "Результаты сессии?" (что удалось сделать)
- "Следующие шаги?" (что осталось)

## Step 4: Save to Obsidian

Вызови MCP tool:
```
mcp__plugin_obsidian_tracker_obsidian__addSession
с параметрами:
  project = {project}
  goal = {goal}
  actions = {actions}
  results = {результаты от пользователя}
  nextSteps = {следующие шаги от пользователя}
```

## Step 5: Cleanup

Удали маркер:
```bash
rm .claude/obsidian-tracking.json
```

## Step 6: Confirm

Вычисли продолжительность: now - started

```
📝 Сессия сохранена в Obsidian
- Проект: {project}
- Цель: {goal}
- Продолжительность: {duration}
- Actions: {actions.length}

Трекинг отключён.
```
