import type { Register } from 'claude-code'

import { CAT_H, CAT_W, FRAMES, MONO_FRAMES, MONO_H, MONO_W, PALETTE, TART_LEFT } from './cat'
import { PNG_FRAMES, RAINBOW_PNG } from './cat-png'

// Three looks, picked with /nyan: the real picture (where the terminal draws pictures, else the
// braille look), the sprite in half-block pixels (any truecolor terminal), or its outline in braille.
type Style = 'auto' | 'pixel' | 'mono'
const STYLES: readonly string[] = ['auto', 'pixel', 'mono']

const RAINBOW = [0xff0000, 0xff9900, 0xffff00, 0x33ff00, 0x0099ff, 0x6633ff]
const SEGMENT = 6 // wave: blocks this wide sit a pixel up or down, flipping every few frames
const NONE = 0x01000000 // terminal default color
const UPPER = 0x2580 // ▀: fg paints the upper half, bg the lower
const LOWER = 0x2584 // ▄: fg paints the lower half (an empty upper half stays the terminal's bg)
const BRAILLE = 0x2800
const DOTS = [[0x01, 0x08], [0x02, 0x10], [0x04, 0x20], [0x40, 0x80]] // [dot row][dot column] -> bit
const PIXEL_ROWS = CAT_H / 2
const MONO_ROWS = MONO_H / 4
const MONO_COLS = MONO_W / 2
const MONO_LINES_TOP = (MONO_H - 12) / 2 // six speed lines, a dot row apart, centred on the tart
const IMAGE_ROWS = 2
// The engine repaints the spinner row on request at most 10 times a second (the gif's own pace is
// FRAME_MS = 70): ticking at that cap gives every frame its paint, ticking faster drops some unevenly.
const TICK_MS = 100
const IMAGE_MAX_COLS = 255 // an Image's width limit: on a wider terminal the rainbow is just shorter
const IMAGE_COLS = Math.round((CAT_W / (CAT_H - 1)) * IMAGE_ROWS * 2) // keeps 34:21 with ~1:2 cells

// Rainbow color at column `dx` from the cat (negative: left of it) and pixel row `y`.
const rainbow = (dx: number, y: number, frame: number, stripe: number, top: number): number => {
  const drop = (Math.floor((dx + 1200) / SEGMENT) + Math.floor(frame / 3)) % 2
  const i = Math.floor((y - top - drop) / stripe)
  return y - top - drop >= 0 && i < RAINBOW.length ? RAINBOW[i]! : NONE
}

// A Raster of `width` x `rows` cells; `at` gives the [codePoint, fg, bg] of each.
const raster = (width: number, rows: number, at: (x: number, row: number) => readonly number[]): string => {
  const words = new Uint32Array(width * rows * 3)
  for (let row = 0; row < rows; row++) {
    for (let x = 0; x < width; x++) words.set(at(x, row), (row * width + x) * 3)
  }
  return new Uint8Array(words.buffer).toBase64()
}

// Two stacked pixels as one cell. A default fg is the text color, not transparent,
// so an empty half must sit on the bg.
const halves = (top: number, bottom: number): readonly number[] =>
  top === NONE && bottom === NONE ? [0x20, NONE, NONE] : top === NONE ? [LOWER, bottom, NONE] : [UPPER, top, bottom]

// Rainbow, then the pixel cat.
export const pack = (width: number, frame: number): string => {
  const tail = width - CAT_W
  const pixel = (x: number, y: number) => {
    if (x >= tail) {
      const c = FRAMES[frame % FRAMES.length]![y]![x - tail]!
      if (c !== '.') return PALETTE[c] ?? NONE
      if (x - tail >= TART_LEFT) return NONE
    }
    return rainbow(x - tail, y, frame, 2, 3)
  }
  return raster(width, PIXEL_ROWS, (x, row) => halves(pixel(x, row * 2), pixel(x, row * 2 + 1)))
}

// The braille look, all in the text color: the rainbow as six dotted speed lines (a dot every
// other column, waving like the colour one), then the cat's outline.
export const packMono = (width: number, frame: number): string => {
  const tail = width - MONO_COLS
  const sprite = MONO_FRAMES[frame % MONO_FRAMES.length]!
  const dot = (x: number, y: number): boolean => {
    if (x >= tail * 2) return sprite[y]?.[x - tail * 2] !== '.'
    if (x % 2) return false
    const line = y - MONO_LINES_TOP - ((Math.floor((x - tail * 2 + 1200) / SEGMENT) + Math.floor(frame / 3)) % 2)
    return line >= 0 && line < 12 && line % 2 === 0
  }
  return raster(width, MONO_ROWS, (x, row) => {
    let bits = 0
    for (let dy = 0; dy < 4; dy++) {
      for (let dx = 0; dx < 2; dx++) if (dot(x * 2 + dx, row * 4 + dy)) bits |= DOTS[dy]![dx]!
    }
    return [BRAILLE + bits, NONE, NONE]
  })
}

export const register: Register = on => {
  let style: Style = 'auto'
  let picturesDraw = true // until a blit says this terminal draws the Image's alt
  let frame = 0
  let timer: { cancel: () => void } | null = null
  const sites = new Map<string, number>() // spinner requestId -> strip width

  const look = (): 'image' | 'pixel' | 'mono' => (style === 'auto' ? (picturesDraw ? 'image' : 'mono') : style)

  const stop = () => {
    timer?.cancel()
    timer = null
  }

  on('session.start', async ($, e, next) => {
    const saved = await $.store.get('style')
    if (typeof saved === 'string' && STYLES.includes(saved)) style = saved as Style
    await $.command.register({
      name: 'nyan',
      description: 'Nyan spinner look: auto (the real picture where the terminal can, else braille), pixel, mono',
      argumentHint: 'auto|pixel|mono',
    })
    return next(e)
  })

  on('command.run', { command: 'nyan' }, async ($, e) => {
    const want = e.args.trim()
    if (STYLES.includes(want)) {
      style = want as Style
      await $.store.set('style', want)
    }
    const now = style === 'auto' ? `auto (${picturesDraw ? 'picture' : 'braille: this terminal draws no pictures'})` : style
    return { text: `nyan: ${now}${STYLES.includes(want) ? '' : '. Usage: /nyan auto|pixel|mono'}` }
  })

  on('turn.start', ($, e, next) => {
    stop()
    frame = 0
    timer = $.clock.every(TICK_MS, () => {
      frame += 1
      for (const [requestId, width] of sites) {
        // ponytail: blit refusals (site gone, resized) are ignored; the next render re-registers the site
        const mode = look()
        if (mode !== 'image') {
          void $.ui.blit({ requestId, key: 'nyan', cells: mode === 'mono' ? packMono(width, frame) : pack(width, frame) })
          continue
        }
        // an unchanged source sends nothing, so the rainbow costs a command only when its wave flips
        for (const [key, png] of [['rainbow', RAINBOW_PNG[Math.floor(frame / 3) % 2]!], ['cat', PNG_FRAMES[frame % PNG_FRAMES.length]!]]) {
          void $.ui.blit({ requestId, key: key!, source: { png: png! } }).then(r => {
            if (r.deny && /\balt\b/.test(r.deny) && picturesDraw) {
              picturesDraw = false // the terminal shows the alt: fall back to braille from the next draw on
              $.ui.log(`nyan: picture not drawn (${r.deny}); using braille`, { to: 'debug' })
              $.ui.invalidate('ui.render')
            }
          })
        }
      }
      // blits paint with the engine's next frame, and before the first tokens the engine draws
      // few frames: ask for one, or the strip stutters at the start of a turn
      $.ui.invalidate('ui.render') // also redraws a band drawn before this timer started
    })
    return next(e)
  })

  on('turn.complete', ($, e, next) => {
    stop() // fires on interrupts and errors too
    sites.clear() // not at turn.start: the band draws (and registers) before that hook runs
    return next(e)
  })

  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    if (e.surface !== 'terminal') return next(e)
    const mode = look()
    const width = Math.min(512, Math.max(CAT_W + 4, (e.viewport?.columns ?? 80) - 2)) // full width from the start
    sites.set(e.requestId, width)

    const { Box, Raster, Image } = $.ui.resolve(e)
    const engineLine = await next(e) // keeps the word, elapsed time and tokens
    const strip =
      mode === 'image' ? (
        <Box flexDirection="row">
          <Image key="rainbow" source={{ png: RAINBOW_PNG[Math.floor(frame / 3) % 2]! }} columns={Math.min(IMAGE_MAX_COLS, width - IMAGE_COLS)} rows={IMAGE_ROWS} alt=" " />
          <Image key="cat" source={{ png: PNG_FRAMES[frame % PNG_FRAMES.length]! }} columns={IMAGE_COLS} rows={IMAGE_ROWS} alt=" " />
        </Box>
      ) : mode === 'mono' ? (
        <Raster key="nyan" columns={width} rows={MONO_ROWS} cells={packMono(width, frame)} />
      ) : (
        <Raster key="nyan" columns={width} rows={PIXEL_ROWS} cells={pack(width, frame)} />
      )
    return (
      <Box flexDirection="column">
        {strip}
        {engineLine}
      </Box>
    )
  })
}
