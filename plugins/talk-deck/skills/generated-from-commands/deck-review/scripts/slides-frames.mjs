#!/usr/bin/env node
// Frames of a Craft deck for Google Slides, rendered at 2x through Chromium.
//   node slides-frames.mjs <deck> <outdir> [--steps] [--only key,key]
// Writes to <outdir>:
//   NNN-<key>-<step>.png   3840x2160, opaque: the slide panel and static decor; NNN is the slide number in Slides
//   NNN-<key>-<step>.gif   with --steps, for a step that counts ([data-count]) or is marked data-gif:
//                          the step's motion, cropped to the slide panel, played once
//   frames.json            {background, overlay: {x, y, width, height} in EMU, frames: [{n, key, step, png, gif}]}
// Without --steps there is one frame per slide in its final state and no GIFs.
// Static decor: <deck>/gslides.css when present, applied only here, so the deck itself stays untouched.
// Needs CRAFT_HOME (cdp.mjs), CHROMIUM and, for GIFs, ffmpeg.
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
const steps = args.includes('--steps');
const onlyAt = args.indexOf('--only');
if (onlyAt >= 0 && !args[onlyAt + 1]) throw Error('--only needs keys: --only key,key');
const only = onlyAt >= 0 ? new Set(args[onlyAt + 1].split(',')) : null;
const [deckDir, outDir] = args.filter((a, i) => !a.startsWith('--') && (onlyAt < 0 || i !== onlyAt + 1));
if (!deckDir || !outDir) throw Error('usage: slides-frames.mjs <deck> <outdir> [--steps] [--only key,key]');
const { launch, sleep } = await import(pathToFileURL(path.join(process.env.CRAFT_HOME, 'scripts', 'cdp.mjs')).href);

// Slides stretches a picture to the projector; 1x looks soft there.
// MAX_S covers Craft's longest data-count-duration; recording stops earlier once the picture holds.
const W = 1920, H = 1080, SCALE = 2, FPS = 25, MAX_S = 10, STILL = 12;
const EMU = 9144000 / W;
mkdirSync(outDir, { recursive: true });
const url = pathToFileURL(path.resolve(deckDir, 'index.html')).href;
const decor = path.resolve(deckDir, 'gslides.css');
// The controls panel and the rehearsal clock never belong in a frame.
const CSS = '.help-panel,.help-reveal-zone,.rehearsal-clock,.rehearsal-log{display:none!important}'
  + (existsSync(decor) ? readFileSync(decor, 'utf8') : '');

const page = await launch({ width: W, height: H });
await page.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: SCALE, mobile: false });
const open = async () => {
  await page.navigate(url);
  await page.evaluate(`(() => { const s = document.createElement('style'); s.textContent = ${JSON.stringify(CSS)};
    document.head.append(s); return true; })()`);
};
const settle = () => page.evaluate('new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => r(true), 150))))');
const capture = async (clip) => (await page.send('Page.captureScreenshot', { format: 'png', ...(clip ? { clip: { ...clip, scale: 1 } } : {}) })).data;

// The page's own clock: time moves only by __tick(ms), so GIF frames are even and repeatable,
// unlike a screencast.
const CLOCK = `(() => {
  const vt = { t: 0, q: [] };
  performance.now = () => vt.t;
  window.requestAnimationFrame = (cb) => vt.q.push(cb);
  window.cancelAnimationFrame = () => {};
  window.__tick = (dt) => {
    vt.t += dt;
    document.getAnimations().forEach((a) => { a.pause(); a.currentTime = (a.currentTime || 0) + dt; });
    const q = vt.q; vt.q = []; q.forEach((cb) => cb(vt.t));
    return true;
  };
  return true; })()`;

await open();
const pages = await page.evaluate('craftDeck.pages()');
const unknown = only ? [...only].filter((k) => !pages.some((p) => p.key === k)) : [];
if (unknown.length) throw Error(`no slide with key ${unknown.join(', ')}`);
const panel = await page.evaluate(`(() => { const r = document.querySelector('.slide[aria-current]').getBoundingClientRect();
  return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) }; })()`);
// The first opaque background up from body; a transparent page is white.
const background = await page.evaluate(`(() => {
  for (const el of [document.body, document.documentElement]) {
    const [r, g, b, a = 1] = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g).map(Number);
    if (a > 0) return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
  }
  return '#ffffff'; })()`);

// Slide numbers in Slides: every page with --steps, else the last step of each deck slide.
const shown = steps ? pages : pages.filter((p, i) => pages[i + 1]?.key !== p.key);
const frames = [];
for (const [i, p] of shown.entries()) {
  const n = String(i + 1).padStart(3, '0');
  if (only && !only.has(p.key)) continue;
  // 'static' puts counters and reveals in their final state; an unknown mode is silently ignored.
  await page.evaluate(`craftDeck.setMotion('static'), craftDeck.go(${p.page}), true`);
  await settle();
  const png = `${n}-${p.key}-${p.step}.png`;
  writeFileSync(path.join(outDir, png), Buffer.from(await capture(), 'base64'));
  frames.push({ n: i + 1, key: p.key, step: p.step, png, gif: null });
}

if (steps) {
  for (const f of frames) {
    // deck.js copies the slide per step: read the frags of the first copy. A step is the reveal
    // number, not the .frag index, since with-previous shares a step with the frag before it.
    // Step 0 animates a counter outside any frag: it runs as the slide comes in.
    const animated = await page.evaluate(`(() => { const s = document.querySelector('[data-key="${f.key}"]');
      if (${f.step} === 0) return [...s.querySelectorAll('[data-count]')].some((x) => !x.closest('.frag'));
      return [...s.querySelectorAll('.frag')].some((x) => Number(x.dataset.fragStep) === ${f.step}
        && (x.matches('[data-gif], [data-count]') || x.querySelector('[data-count]'))); })()`);
    const to = pages.find((p) => p.key === f.key && p.step === f.step);
    // The first page has nothing before it to start from.
    if (!animated || to.page === 1) continue;
    // A clean page per GIF: the clock and paused animations of the last one do not carry over.
    await open();
    await page.evaluate(`craftDeck.setMotion('show'), craftDeck.go(${to.page - 1}), true`);
    await settle();
    await page.evaluate(CLOCK);
    await page.evaluate(`craftDeck.go(${to.page}), true`);
    const tmp = mkdtempSync(path.join(tmpdir(), 'gif-'));
    let k = 0, still = 0, prev = '';
    // The first frame is the start of the step; then tick until the picture holds for STILL frames.
    for (let i = 0; i < MAX_S * FPS && still < STILL; i += 1) {
      await page.evaluate(`__tick(${i ? 1000 / FPS : 0})`);
      await sleep(20);
      const data = await capture(panel);
      still = data === prev ? still + 1 : 0;
      prev = data;
      writeFileSync(path.join(tmp, `c${String(k++).padStart(4, '0')}.png`), Buffer.from(data, 'base64'));
    }
    f.gif = f.png.replace(/\.png$/, '.gif');
    try {
      // -loop -1 plays once and holds the last frame, as the live slide does.
      execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-framerate', String(FPS), '-i', path.join(tmp, 'c%04d.png'),
        '-vf', 'split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];[b][p]paletteuse=dither=none',
        '-loop', '-1', path.join(outDir, f.gif)]);
    } finally {
      rmSync(tmp, { recursive: true });
    }
  }
}
await page.close();

const overlay = Object.fromEntries(Object.entries(panel).map(([k, v]) => [k, Math.round(v * EMU)]));
// map: every slide of the presentation in order, so an update can tell that slide n is still the same.
const map = shown.map((p) => `${p.key}/${p.step}`);
writeFileSync(path.join(outDir, 'frames.json'), JSON.stringify({ background, overlay, map, frames }, null, 2));
console.log(`frames=${path.resolve(outDir)}`);
console.log(`count=${frames.length}`);
console.log(`gifs=${frames.filter((f) => f.gif).length}`);
console.log(`slides=${shown.length}`);
