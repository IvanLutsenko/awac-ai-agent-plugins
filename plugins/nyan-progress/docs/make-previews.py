# Renders docs/{gif,pixel,dots}.gif: what each look draws over the spinner, cell for cell.
# It reads the sprite data from hooks/cat.ts and hooks/cat-png.ts and mirrors the packing in
# hooks/register.tsx, then paints the cells the way a terminal would (light Solarized theme).
# Run: uv run --with pillow python docs/make-previews.py   (from plugins/nyan-progress)
import base64
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
COLS, CW, CH = 64, 10, 20  # terminal columns, cell size in px (~1:2)
BG, FG, DIM = (253, 246, 227), (88, 110, 117), (147, 161, 161)
FONT = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14)
TICKS, TICK_MS = 24, 100

RAINBOW = [0xFF0000, 0xFF9900, 0xFFFF00, 0x33FF00, 0x0099FF, 0x6633FF]
DOT_RAINBOW = [0xE8202A, 0xD2690A, 0x968000, 0x2F9E35, 0x1F7FE0, 0x8A4CF2]
SEGMENT = 6

cat_ts = (ROOT / "hooks/cat.ts").read_text()
png_ts = (ROOT / "hooks/cat-png.ts").read_text()


def frames(name):
    body = cat_ts[cat_ts.index(f"export const {name}"):]
    body = body[: body.index("\n]\n")]
    return [re.findall(r"'([^']*)'", block) for block in body.split("  [\n")[1:]]


def pngs(name):
    body = png_ts[png_ts.index(f"export const {name}"):]
    body = body[: body.index("\n]")]
    return [Image.open(io.BytesIO(base64.b64decode(s))).convert("RGBA") for s in re.findall(r"'([^']+)'", body)]


FRAMES, DOT_FRAMES = frames("FRAMES"), frames("DOT_FRAMES")
PALETTE = {k: int(v, 16) for k, v in re.findall(r"(\w): 0x([0-9a-f]{6})", cat_ts)}
CAT_W, CAT_H, TART_LEFT = 34, 22, 7
PNG_FRAMES, RAINBOW_PNG = pngs("PNG_FRAMES"), pngs("RAINBOW_PNG")
rgb = lambda c: ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def rainbow(dx, y, frame, stripe, top):
    drop = ((dx + 1200) // SEGMENT + frame // 3) % 2
    i = (y - top - drop) // stripe
    return RAINBOW[i] if y - top - drop >= 0 and i < len(RAINBOW) else None


def canvas(rows, frame):
    im = Image.new("RGB", (COLS * CW, (rows + 1) * CH + 6), BG)
    d = ImageDraw.Draw(im)
    secs = 3 + frame * TICK_MS // 1000
    x, y = 0, rows * CH + 3  # the engine's own line, right under the strip
    for text, color in (("✻ ", (203, 75, 22)), ("Sauteing… ", FG), (f"({secs}s · ↓ {120 + frame * 9} tokens)", DIM)):
        d.text((x, y), text, font=FONT, fill=color)
        x += d.textlength(text, font=FONT)
    return im, d


def pixel(frame, width):
    tail = width - CAT_W
    sprite = FRAMES[frame % len(FRAMES)]

    def px(x, y):
        if x >= tail:
            c = sprite[y][x - tail]
            if c != ".":
                return PALETTE[c]
            if x - tail >= TART_LEFT:
                return None
        return rainbow(x - tail, y, frame, 2, 3)

    im, d = canvas(CAT_H // 2, frame)
    for y in range(CAT_H):
        for x in range(width):
            c = px(x, y)
            if c is not None:
                d.rectangle((x * CW, y * CH // 2, x * CW + CW - 1, y * CH // 2 + CH // 2 - 1), fill=rgb(c))
    return im


def dots(frame, width):
    sprite = DOT_FRAMES[frame % len(DOT_FRAMES)]
    rows, cols = len(sprite) // 4, len(sprite[0]) // 2
    tail = width - cols
    top = (len(sprite) - 12) // 2
    im, d = canvas(rows, frame)
    for y in range(len(sprite)):
        for x in range(width * 2):
            if x >= tail * 2:
                on, color = sprite[y][x - tail * 2] != ".", FG
            else:
                line = y - top - (((x - tail * 2 + 1200) // SEGMENT + frame // 3) % 2)
                on = x % 2 == 0 and 0 <= line < 12 and line % 2 == 0
                color = rgb(DOT_RAINBOW[((x // 2 - tail + 1200) // (SEGMENT // 2)) % 6])
            if on:
                cx, cy = (x // 2) * CW + 2 + (x % 2) * 5, (y // 4) * CH + 2 + (y % 4) * 5
                d.ellipse((cx, cy, cx + 3, cy + 3), fill=color)
    return im


def picture(frame, width):
    rows, cat_cols = 2, round(CAT_W / (CAT_H - 1) * 2 * 2)
    im, _ = canvas(rows, frame)
    bow = RAINBOW_PNG[(frame // 3) % 2].resize(((width - cat_cols) * CW, rows * CH), Image.NEAREST)
    cat = PNG_FRAMES[frame % len(PNG_FRAMES)].resize((cat_cols * CW, rows * CH), Image.LANCZOS)
    im.paste(bow, (0, 0), bow)
    im.paste(cat, ((width - cat_cols) * CW, 0), cat)
    return im


for name, draw in (("gif", picture), ("pixel", pixel), ("dots", dots)):
    shots = [draw(f, COLS - 2) for f in range(TICKS)]
    shots[0].save(OUT / f"{name}.gif", save_all=True, append_images=shots[1:], duration=TICK_MS, loop=0, optimize=True)
    print(name, shots[0].size, (OUT / f"{name}.gif").stat().st_size)
