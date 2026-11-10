#!/usr/bin/env python3
"""Rehearsal report: the run's recording transcribed and laid out per slide.

Usage: rehearsal-report.py [run.json] [--lang ru] [--model name]
Without a path takes the newest rehearsal-*.json in ~/Downloads. Transcribes
the recording named in the JSON locally (once; the transcript is kept next
to it): mlx-whisper on Apple Silicon when installed, else the openai-whisper CLI, splits the speech by the run's slide log and
writes <run>.md: time against plan, words per minute, filler words, long
pauses and the text spoken on every slide. Prints report= and the summary.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

FILLERS = {
    "ru": ["ну", "вот", "типа", "как бы", "короче", "собственно", "в общем", "значит", "это самое", "так сказать", "э", "ээ", "эээ", "м", "мм"],
    "en": ["um", "uh", "like", "you know", "basically", "actually", "so", "i mean"],
}
PAUSE = 3.0  # seconds of silence inside a slide worth a look


def fmt(sec):
    s = round(abs(sec))
    return f"{'−' if sec < 0 else ''}{s // 60}:{s % 60:02d}"


def transcribe(audio, lang, model):
    out = audio.with_suffix(".whisper.json")
    if out.exists():
        return json.loads(out.read_text())
    tmp = audio.parent / ".whisper-out"
    tmp.mkdir(exist_ok=True)
    if mlx := shutil.which("mlx_whisper"):
        # Full large-v3: on Russian it is more accurate than turbo, and MLX keeps it fast.
        cmd = [mlx, str(audio), "--model", model or "mlx-community/whisper-large-v3-mlx",
               "--output-format", "json", "--output-dir", str(tmp), "--output-name", audio.stem,
               "--word-timestamps", "True", "--condition-on-previous-text", "False"]
    elif whisper := shutil.which("whisper"):
        cmd = [whisper, str(audio), "--model", model or "turbo", "--output_format", "json",
               "--output_dir", str(tmp), "--word_timestamps", "True", "--fp16", "False",
               "--condition_on_previous_text", "False"]
    else:
        sys.exit("talk-deck: no whisper; install mlx-whisper (Apple Silicon) or openai-whisper with uv tool install")
    subprocess.run(cmd + ["--language", lang], check=True, stdout=subprocess.DEVNULL)
    produced = tmp / (audio.stem + ".json")
    produced.replace(out)
    shutil.rmtree(tmp)
    return json.loads(out.read_text())


def words_of(transcript):
    # Word timestamps when whisper gave them, else whole segments as one "word".
    for seg in transcript["segments"]:
        if seg.get("words"):
            yield from ((w["start"], w["end"], w["word"].strip()) for w in seg["words"])
        else:
            yield seg["start"], seg["end"], seg["text"].strip()


def count_fillers(text, lang):
    low = " " + re.sub(r"[^\w\s]", " ", text.lower()) + " "
    hits = {f: len(re.findall(rf"\s{re.escape(f)}(?=\s)", low)) for f in FILLERS.get(lang, [])}
    return {f: n for f, n in hits.items() if n}


def report(run, words, lang):
    by_slide = {}
    for e in run["log"]:
        by_slide.setdefault(e["slide"], []).append((e["start"], e["end"]))
    lines = [f"# Прогон {run['date'][:16].replace('T', ' ')} UTC", "",
             f"Итого {fmt(run['total'])} при плане {fmt(run['plan'])} ({fmt(run['total'] - run['plan'])})", ""]
    total_words = 0
    total_fillers = {}
    for s in run["slides"]:
        spans = by_slide.get(s["slide"], [])
        mine = [w for w in words if any(a <= (w[0] + w[1]) / 2 < b for a, b in spans)]
        text = " ".join(w[2] for w in mine)
        n = len(text.split())
        total_words += n
        wpm = round(n / s["spent"] * 60) if s["spent"] else 0
        fillers = count_fillers(text, lang)
        for f, k in fillers.items():
            total_fillers[f] = total_fillers.get(f, 0) + k
        # Silence inside each visit, its edges included: a slide's last word to the
        # slide change is the usual lost thread.
        pauses = []
        for x, y in spans:
            edges = [x] + [t for w in mine if x <= (w[0] + w[1]) / 2 < y for t in (w[0], w[1])] + [y]
            pauses += [(a, b) for a, b in zip(edges[::2], edges[1::2]) if b - a >= PAUSE]
        over = " · перебор" if s["spent"] > s["plan"] * 1.15 else ""
        lines += [f"## {s['title']} (`{s['slide']}`)", "",
                  f"Факт {fmt(s['spent'])}, план {fmt(s['plan'])}, Δ {fmt(s['spent'] - s['plan'])}{over}. "
                  f"Слов {n}, темп {wpm} сл/мин."]
        if fillers:
            lines.append("Паразиты: " + ", ".join(f"«{f}» ×{k}" for f, k in sorted(fillers.items(), key=lambda x: -x[1])) + ".")
        if pauses:
            lines.append("Паузы: " + ", ".join(f"{fmt(a)} ({b - a:.0f} с)" for a, b in pauses) + ".")
        lines += ["", "> " + (text or "(тишина)"), ""]
    speak = sum(s["spent"] for s in run["slides"]) or 1
    summary = [f"Слов {total_words}, средний темп {round(total_words / speak * 60)} сл/мин."]
    if total_fillers:
        summary.append("Паразиты за прогон: " + ", ".join(
            f"«{f}» ×{k}" for f, k in sorted(total_fillers.items(), key=lambda x: -x[1])) + ".")
    return lines[:4] + summary + [""] + lines[4:], summary


def main():
    args = sys.argv[1:]
    opt = lambda name, default: args[args.index(name) + 1] if name in args else default
    lang, model = opt("--lang", "ru"), opt("--model", None)
    paths = [a for a in args if a.endswith(".json")]
    if paths:
        path = Path(paths[0]).expanduser()
    else:
        found = sorted((Path.home() / "Downloads").glob("rehearsal-*.json"), key=lambda p: p.stat().st_mtime)
        found = [p for p in found if not p.name.endswith(".whisper.json")]
        if not found:
            sys.exit("talk-deck: no rehearsal-*.json in ~/Downloads")
        path = found[-1]
    run = json.loads(path.read_text())
    if not run.get("audio"):
        sys.exit(f"talk-deck: {path.name} has no recording; the microphone was off for that run")
    audio = path.parent / run["audio"]
    if not audio.exists():
        sys.exit(f"talk-deck: {audio} not found; the browser may still be saving it")
    words = list(words_of(transcribe(audio, lang, model)))
    lines, summary = report(run, words, lang)
    out = path.with_suffix(".md")
    out.write_text("\n".join(lines))
    print(f"report={out}")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
