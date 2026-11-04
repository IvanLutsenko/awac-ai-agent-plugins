---
description: Roast a talk deck with every agent at once — codex, pi and claude through auto-handoff plus a Claude Design reviewer — on a PDF, screenshots and the sources the talk is about; facts checked against the sources first.
argument-hint: "[deck] [extra notes for the reviewers]"
allowed-tools: Bash(bash:*), Bash(source:*), Bash(cat:*), Read, Write, Skill, Agent, AskUserQuestion
---

# /deck-review — roast the deck

## 1. Materials

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/review-pack.sh <deck>
```

It prints `pack=` (a temp folder with `deck.pdf`, `final/`, `shots/`, `slides.txt`, `check.log`), `deck=`, `slides=`, `pages=` and `check=`. `check=failed` does not stop the review; tell the author and add the failing lines from `check.log` to the notes for the reviewers.

## 2. The prompt

Fill `${CLAUDE_PLUGIN_ROOT}/scripts/review-prompt.md` and write it to `<pack>/prompt.md`. Every placeholder gets real text; most of it is already in the conversation or the deck:

- `{{ABOUT}}` — what the talk is about, who gives it, the event;
- `{{AUDIENCE}}`, `{{GOAL}}`, `{{FORMAT}}` (length, online or on stage, screen share, aspect ratio);
- `{{THEME}}` — the visual theme in one line, from the comment at the top of `deck-theme.css`;
- `{{MOTION}}` — the animations a screenshot does not show: reveal steps, counters, decor;
- `{{DECIDED}}` — what the author settled and the reviewers must not argue with: theme and palette, Craft, the Harold slide, the page number without a total, desktop only, plus anything settled earlier in the conversation;
- `{{SOURCES}}` — absolute paths to what the talk describes: the repo, its READMEs, the code; this is what the facts are checked against;
- `{{DECK}}`, `{{PACK}}`, `{{SLIDES}}`, `{{PAGES}}` — from step 1; `{{LANG}}` — the deck's language.

Ask the author once, in one message, only for what is still unknown (usually the audience, the goal and the sources). Append the author's extra notes from `$ARGUMENTS` at the end of the prompt.

## 3. Reviewers, in parallel

1. The `auto-handoff` skill with `+claude -agy` and the task: "the prompt is ready in `<pack>/prompt.md`, use it as is; read-only". agy is left out on purpose: headless it ends with no report. Without the auto-handoff skill, run three reviewers yourself as subagents with the same prompt.
2. In the same turn, the Claude Design reviewer: a `general-purpose` subagent with the prompt and this note on top: "You are a senior presentation designer. The emphasis is on visual design and delivery: typography, composition, rhythm between slides, density, how the slides work on a shared screen, what looks templated. Look at every file in final/ and at the reveal steps in shots/ where step-by-step appearance matters. Still roast the story and the texts as the prompt asks."

## 4. Summary

When all reports are in, follow the summary rules of auto-handoff: findings shared by two or more reviewers first, then single ones with whose they are, then the ones you consider false and why. Facts go before everything else. Check every finding against the source yourself before passing it on — reviewers make up line numbers. End with what to do, briefly, numbered so the author can answer "1, 3, 5". Name the pack folder; do not delete it.
