// Rehearsal timer for a Craft deck: time per slide against a plan.
// R (or the stopwatch button in the controls panel) starts and stops a run,
// P shows the last run. A stopped run is saved to Downloads as JSON, plus the
// microphone recording when the browser was allowed to use it.
// Plan: data-plan="<seconds>" on a slide, the rest of data-talk-minutes on
// .deck is shared by the remaining slides in proportion to their reveal steps.
(() => {
  const deckApi = window.craftDeck;
  const deck = document.querySelector('.deck');
  if (!deckApi || !deck) return;

  const pages = deckApi.pages();
  const keys = [...new Set(pages.map((p) => p.key))];
  const titles = Object.fromEntries(keys.map((k) => [k, pages.find((p) => p.key === k).title || k]));
  const steps = Object.fromEntries(keys.map((k) => [k, pages.filter((p) => p.key === k).length]));

  const fixed = {};
  for (const slide of document.querySelectorAll('.slide[data-key][data-plan]')) {
    fixed[slide.dataset.key] = Number(slide.dataset.plan);
  }
  const totalSec = Number(deck.dataset.talkMinutes || 20) * 60;
  const fixedSum = Object.values(fixed).reduce((a, b) => a + b, 0);
  const freeSteps = keys.filter((k) => !(k in fixed)).reduce((a, k) => a + steps[k], 0);
  const plan = Object.fromEntries(keys.map((k) => [k,
    k in fixed ? fixed[k] : Math.round(Math.max(0, totalSec - fixedSum) * steps[k] / (freeSteps || 1))]));
  // Where the talk should be by the end of each slide.
  let acc = 0;
  const deadline = Object.fromEntries(keys.map((k) => [k, (acc += plan[k])]));

  const keyOf = (page) => pages[page - 1].key;
  const esc = (text) => text.replace(/[&<>]/g, (c) => `&#${c.charCodeAt(0)};`);
  const fmt = (sec) => {
    const s = Math.round(Math.abs(sec));
    return `${sec < 0 ? '−' : ''}${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  };

  const style = document.createElement('style');
  style.textContent = `
    .rehearsal-clock { position: fixed; top: .75rem; right: .75rem; z-index: 30;
      padding: .3rem .6rem; border: 1px solid var(--line); background: var(--bg); color: var(--text);
      font: 600 .9rem/1.2 var(--font-text); font-variant-numeric: tabular-nums; pointer-events: none; }
    .rehearsal-clock[data-rec]::before { content: '● '; color: #e5484d; }
    .rehearsal-clock[data-late] { color: #e5484d; border-color: #e5484d; }
    .help-panel button.rehearsal-button[aria-pressed="true"] { border-color: #e5484d; color: #e5484d; }
    .rehearsal-log { position: fixed; inset: 5vh 50% auto auto; transform: translateX(50%); z-index: 40;
      max-height: 90vh; overflow: auto; padding: 1rem 1.25rem; border: 1px solid var(--line);
      background: var(--bg); color: var(--text); font: 500 .85rem/1.35 var(--font-text); }
    .rehearsal-log table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
    .rehearsal-log th, .rehearsal-log td { padding: .15rem .6rem; text-align: right; }
    .rehearsal-log th:first-child, .rehearsal-log td:first-child { text-align: left; }
    .rehearsal-log tr[data-over] td { color: #e5484d; }
    .rehearsal-log tfoot td { border-top: 1px solid var(--line); font-weight: 700; }
    @media print { .rehearsal-clock, .rehearsal-log { display: none; } }`;
  document.head.append(style);

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'rehearsal-button';
  button.setAttribute('aria-label', 'Замер прогона');
  button.setAttribute('aria-pressed', 'false');
  button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="7.5"/><path d="M12 9v4l2.5 2M10 2.5h4M12 2.5v3"/></svg><span class="shortcut-key" aria-hidden="true">R</span>';
  document.querySelector('.help-actions')?.append(button);

  let run = null; // { started, key, since, spent: {key: ms}, log: [] }
  let starting = false;
  let recorder = null;
  let chunks = [];
  let last = null;
  let clock = null;
  let ticker = 0;

  function close(now) {
    const ms = now - run.since;
    run.spent[run.key] = (run.spent[run.key] || 0) + ms;
    run.log.push({ slide: run.key, start: run.since - run.started, end: now - run.started });
  }

  function tick() {
    const elapsed = (performance.now() - run.started) / 1000;
    const due = deadline[run.key];
    clock.textContent = `${fmt(elapsed)} / ${fmt(due)}`;
    clock.toggleAttribute('data-late', elapsed > due);
  }

  function save(blob, name) {
    const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: name });
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  async function start() {
    starting = true;
    let stream = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => chunks.push(event.data);
      recorder.start(1000);
    } catch (error) {
      // No microphone, no permission or no recorder: the run is timed without audio,
      // the clock shows no red dot, and the reason goes to the console.
      console.warn('rehearsal: recording is off,', error);
      stream?.getTracks().forEach((track) => track.stop());
      recorder = null;
    }
    starting = false;
    // The run starts with the recording, so the log times are offsets into the audio.
    const now = performance.now();
    run = { started: now, date: new Date().toISOString(), key: keyOf(deckApi.current), since: now, spent: {}, log: [] };
    clock = document.createElement('div');
    clock.className = 'rehearsal-clock';
    clock.toggleAttribute('data-rec', Boolean(recorder));
    document.body.append(clock);
    tick();
    ticker = setInterval(tick, 500);
    button.setAttribute('aria-pressed', 'true');
  }

  function stop() {
    close(performance.now());
    clearInterval(ticker);
    clock.remove();
    button.setAttribute('aria-pressed', 'false');
    const total = Object.values(run.spent).reduce((a, b) => a + b, 0) / 1000;
    last = {
      date: run.date,
      total: Math.round(total),
      plan: totalSec,
      slides: keys.filter((k) => k in run.spent).map((k) => ({
        slide: k, title: titles[k], spent: Math.round(run.spent[k] / 1000), plan: plan[k],
      })),
      log: run.log.map((e) => ({ ...e, start: Math.round(e.start / 100) / 10, end: Math.round(e.end / 100) / 10 })),
    };
    run = null;
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const stamp = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}-${pad(d.getMinutes())}-${pad(d.getSeconds())}`;
    if (recorder) {
      const rec = recorder;
      recorder = null;
      const name = `rehearsal-${stamp}.${rec.mimeType.includes('mp4') ? 'm4a' : 'webm'}`;
      const parts = chunks;
      last.audio = name;
      rec.onstop = () => {
        rec.stream.getTracks().forEach((track) => track.stop());
        save(new Blob(parts, { type: rec.mimeType }), name);
      };
      rec.stop();
    }
    save(new Blob([JSON.stringify(last, null, 2)], { type: 'application/json' }), `rehearsal-${stamp}.json`);
    showLog(true);
  }

  function showLog(on) {
    document.querySelector('.rehearsal-log')?.remove();
    if (!on || !last) return;
    const box = document.createElement('div');
    box.className = 'rehearsal-log';
    const rows = last.slides.map((s) => {
      const over = s.spent > s.plan * 1.15 ? ' data-over' : '';
      return `<tr${over}><td>${esc(s.title)}</td><td>${fmt(s.spent)}</td><td>${fmt(s.plan)}</td><td>${fmt(s.spent - s.plan)}</td></tr>`;
    }).join('');
    box.innerHTML = `<table><thead><tr><th>Слайд</th><th>Факт</th><th>План</th><th>Δ</th></tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr><td>Итого</td><td>${fmt(last.total)}</td><td>${fmt(last.plan)}</td><td>${fmt(last.total - last.plan)}</td></tr></tfoot></table>`;
    box.addEventListener('click', () => showLog(false));
    document.body.append(box);
  }

  const toggle = () => {
    if (starting) return; // the microphone prompt is still open
    run ? stop() : start();
  };
  button.addEventListener('click', toggle);

  addEventListener('craft-slidechange', (event) => {
    if (!run) return;
    const key = keyOf(event.detail.page);
    if (key === run.key) return;
    const now = performance.now();
    close(now);
    run.key = key;
    run.since = now;
    tick();
  });

  document.addEventListener('keydown', (event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.target instanceof Element && event.target.closest('input, textarea, select, [contenteditable]')) return;
    // The escaped letters are the same keys on the Russian keyboard layout.
    if ('rRкК'.includes(event.key)) {
      event.preventDefault();
      if (!event.repeat) toggle();
    } else if ('pPзЗ'.includes(event.key)) {
      event.preventDefault(); showLog(!document.querySelector('.rehearsal-log'));
    } else if (event.key === 'Escape') {
      showLog(false);
    }
  });
})();
