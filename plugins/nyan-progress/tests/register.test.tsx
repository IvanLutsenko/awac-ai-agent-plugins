import { describe, expect, mock, test } from 'claude-code/testing'

import { CAT_W } from '../hooks/cat'
import { pack, packDots } from '../hooks/register'

const cellsOf = (b64: string) => new Uint32Array(Uint8Array.fromBase64(b64).buffer)
const width = CAT_W + 10
const SPINNER = {
  component: 'Spinner',
  props: { word: 'Sauteing', message: null, suffix: '…', mode: 'thinking' },
  viewport: { columns: 100, rows: 40 },
} as const

describe('register', () => {
  test('pack: the rainbow spans up to the cat, which ends the strip', async () => {
    const cells = cellsOf(pack(width, 0))
    const at = (row: number, x: number) => [...cells.slice((row * width + x) * 3, (row * width + x) * 3 + 3)]
    expect(at(2, 0)).toEqual([0x2580, 0xff0000, 0xff9900]) // the first column is already rainbow
    expect(at(2, 6)).toEqual([0x2580, 0xff0000, 0xff0000]) // lowered wave block: the 2-px red stripe
    expect(at(0, width - CAT_W + 9)).toEqual([0x2580, 0x000000, 0xffcc99]) // tart: outline over crust
  })

  test('packDots: speed lines then the cat, braille in the text color', async () => {
    const w = 40
    const cells = cellsOf(packDots(w, 0))
    const at = (row: number, x: number) => [...cells.slice((row * w + x) * 3, (row * w + x) * 3 + 3)]
    expect(at(1, 0)).toEqual([0x2805, 0x968000, 0x01000000]) // two lines, left dot column only, in a rainbow colour
    const [ch, fg, bg] = at(0, w - 16 + 4) // over the tart's top outline
    expect(ch! > 0x2800 && ch! <= 0x28ff).toBe(true)
    expect([fg, bg]).toEqual([0x01000000, 0x01000000])
  })

  test('the spinner: the gif by default, braille after /nyan dots', async ($, on) => {
    mock.clock(on)
    mock.store(on, {})
    on('session.start', ($, e) => ({ cwd: e.cwd }))
    on('command.register', ($, e) => ({ value: { command: e.name } }))
    on('ui.render', ($, e) => {
      const { Text } = $.ui.resolve(e)
      return <Text>Sauteing…</Text>
    })
    await $.session.start({ surface: 'terminal', isInteractive: true, cwd: '/work' })

    const gif = await $.ui.mount({ plugin: 'nyan-progress', surface: 'terminal', ...SPINNER })
    expect(await gif.find({ type: 'Image', key: 'cat' })).toBeDefined()
    expect(await gif.find({ type: 'Image', key: 'rainbow' })).toBeDefined()
    await gif.unmount()

    const { text } = await $.command.run({ command: 'nyan', args: 'dots', origin: { kind: 'composer' }, presentation: { isFullscreen: true, columns: 100 } })
    expect(text).toBe('dots') // Claude Code names the command itself
    const dots = await $.ui.mount({ plugin: 'nyan-progress', surface: 'terminal', ...SPINNER })
    expect(await dots.find({ type: 'Raster', key: 'nyan' })).toBeDefined()
    expect(await dots.find({ type: 'Image' })).toBeUndefined()
    expect(await dots.find({ type: 'Text', text: 'Sauteing…' })).toBeDefined()
  })
})
