---
name: talk-deck-deck-rehearse
description: Rehearsal timer for a talk deck — a stopwatch button in the deck's controls panel that times every slide against a plan and records the voice; `analyze` transcribes a run and reviews the delivery slide by slide. Use when the user invokes /deck-rehearse.
version: 0.1.0
---

> Converted from Claude Code command `/deck-rehearse`.
> Review and adapt: hooks and MCP tool IDs may need manual mapping for Codex.
> Helper scripts ship in this skill's own `scripts/` directory. Replace
> `<this skill directory>` with the path Codex reported when it loaded this skill —
> a bare relative path would resolve against the repository under review instead.

# /deck-rehearse — time the run-through

`analyze` as the first argument → the section «Analyze a run» below. Otherwise parse `$ARGUMENTS`: `deck` (a slug, a path, or empty for the current folder) and `minutes`, the talk length (default: keep the deck's `data-talk-minutes`, or 20 on a deck without it). Ask for the length only if the author has not given it here or earlier in the conversation.

```bash
bash <this skill directory>/scripts/rehearse.sh <deck> [minutes]
```

It copies `rehearsal.js` into the deck, adds its `<script>` once and sets `data-talk-minutes` on `.deck`. Running it again refreshes the script to the plugin's version.

The plan: a slide with `data-plan="<seconds>"` gets exactly that; the rest of the talk length is shared by the other slides in proportion to their reveal steps. Add `data-plan` only where the author names a time for a slide.

Report `minutes=` and how to use it:
- `R` or the stopwatch button in the controls panel (`H`) starts a run; the clock in the top right shows elapsed time against where the talk should be by the end of the current slide, red when behind;
- the browser asks for the microphone on the first run; with it the run is recorded (a red dot before the clock), without it only timed;
- `R` again stops it: a table «слайд / факт / план / Δ» (over 115% of the plan in red), and in Downloads `rehearsal-<date>.json` plus `rehearsal-<date>.webm` with the voice; Chrome may ask once to allow several downloads;
- `P` shows the last table again, `Esc` or a click closes it.

The script is inert until pressed, so it can stay in the published deck. Run the static check after the edit (the hook does it inside Claude Code).

## Analyze a run

```bash
python3 <this skill directory>/scripts/rehearsal-report.py [run.json] [--lang ru] [--model name]
```

Without a path it takes the newest `rehearsal-*.json` in `~/Downloads`. It transcribes the recording locally: `mlx_whisper` with `large-v3` on Apple Silicon when installed, else the `whisper` CLI (openai-whisper, `turbo` on CPU, several times slower). The first run downloads the model, about 3 GB for `large-v3`; the transcript is kept as `<run>.whisper.json`, so a second report is instant, splits the speech by the slide log and writes `<run>.md`: time against plan, words per minute, filler words, pauses of 3 s or more and the text spoken on every slide. Neither installed → tell the author to run `uv tool install mlx-whisper` (Apple Silicon) or `uv tool install openai-whisper`; do not install it yourself.

Read the report, then the deck's `index.html` for the text on each slide, and review the delivery as a speaking coach would, in the author's language:
- timing: which slides ate the overrun and what to cut there, quoting the spoken text; the total against the plan;
- the story: a slide whose point was not said, a point said twice, a transition that is missing, the voice reading the slide aloud;
- pace: slides far above or below the average words per minute; long pauses that look like a lost thread;
- filler words: the top ones and where they cluster.

Filler counts are rough both ways: whisper drops some hesitations («э», «мм»), and words like «вот», «значит», «so» are often meaningful, so read them in the quoted text before calling them fillers. Whisper also mishears terms: do not blame the author for a word that is clearly a recognition error. Quote the transcript, do not retell it. End with three to five fixes, numbered so the author can answer by numbers. With several reports in `~/Downloads`, compare against the previous run too.
