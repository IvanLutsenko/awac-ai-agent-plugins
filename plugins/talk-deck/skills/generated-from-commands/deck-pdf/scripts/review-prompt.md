Task: ROAST a finished talk deck. Read it, look at it, and take apart everything weak: content, story, wording, facts and visuals. Work silently and on your own, ask nothing; print the final report to stdout (in your answer, not in a separate file or artifact). Read-only: change nothing on disk, no git commit / git push / glab / gh. Write the report in {{LANG}}.

## What it is

{{ABOUT}}

Audience: {{AUDIENCE}}
Goal of the talk: {{GOAL}}
Format: {{FORMAT}}
Theme: {{THEME}}

Materials (absolute paths):
- {{DECK}}/index.html — all slide texts (`<section class="slide" data-key=...>`; elements with class `frag` appear step by step);
- {{DECK}}/deck-theme.css — the deck's theme, the only CSS the author edits;
- slides.css, base.css, tokens.css, deck.js in the same folder — the Craft framework core; do not propose edits to them;
- {{SOURCES}} — what the talk is about: check the slides' claims against it;
- PDF, one page per slide in its final frame: {{PACK}}/deck.pdf;
- screenshots: the final frame of every slide — {{PACK}}/final/NN-<key>.png ({{SLIDES}} files); every reveal step — {{PACK}}/shots/dark-NNN.png ({{PAGES}} files); slide to pages — {{PACK}}/slides.txt.
If your tool can look at images or PDFs, you must look. If it cannot, say so at the top of the report and review from the code.

Motion (a screenshot is a frozen frame): {{MOTION}}

## Already decided by the author — do not argue

{{DECIDED}}

## What to roast

1. Facts. Check EVERY factual claim on the slides — commands, flags, defaults, versions, names, numbers, who does what — against {{SOURCES}}, with the `path:line` you actually read. A claim you cannot confirm is a finding too. Do this first: the last roast found seven factual errors that the authors had missed.
2. Story: does it hold for the whole slot, is "why do I need this" clear from the first slides, are there sagging parts, repeats, extra slides, what is missing (a demo? numbers? an answer to the obvious objection of a sceptic?). Is the chapter order right. Is the ending strong, and the call to action.
3. Slides one by one: what is unclear without the speaker's voice, where there is too much text, where there is bureaucratese or jargon, where a claim has no support.
4. Visuals: readability on a shared screen or a projector, hierarchy, density, consistency between slides (paddings, reveal order, sizes), whether the decor gets in the way.

## Report rules

- Be harsh, but only on the merits: findings you are ready to defend. Before writing a finding, try to refute it: did the author mean it? is it visible on a screenshot / written in the text, or is it a guess? It does not hold — drop it. Mark taste as taste.
- Every finding: the slide (number and data-key) plus the screenshot you actually looked at and/or the `path:line` you actually saw. A made-up reference is worse than no finding.
- For each one, a concrete fix: the new wording, what to remove / move / add, or a CSS edit (selector and value) as the smallest change. No new abstractions.
- Format: first an overall verdict in 3–5 sentences (what will work, what will fail); then a numbered list of findings by importance with a severity (high / medium / low), facts first; at the end the 5 most important edits, one line each. No intro and no praise.
