#!/bin/bash
# burn-subtitles.sh — burn subtitles into clips using Pillow direct frame rendering
# Uses ffmpeg pipe + Pillow (precise positioning, Cyrillic support)
# Usage: burn-subtitles.sh <moments_json> <transcript_json> <clips_dir>

set -euo pipefail

if ! python3 -c "from PIL import ImageFont" 2>/dev/null; then
  echo "Pillow missing, run install-deps.sh" >&2
  exit 1
fi

export MOMENTS_JSON="$1"
export TRANSCRIPT_JSON="$2"
export CLIPS_DIR="$3"

python3 -c "
import json, subprocess, os
from PIL import Image, ImageDraw, ImageFont

moments_path = os.environ['MOMENTS_JSON']
transcript_path = os.environ['TRANSCRIPT_JSON']
clips_dir = os.environ['CLIPS_DIR']

# Font: Baskerville for Cyrillic support and readability
FONT_PATHS = [
    '/System/Library/Fonts/Supplemental/Baskerville.ttc',
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
]
FONT = None
for fp in FONT_PATHS:
    if os.path.exists(fp):
        FONT = ImageFont.truetype(fp, 60)
        break
if FONT is None:
    FONT = ImageFont.load_default()

W, H = 1080, 1920
MARGIN = 30
SUB_Y = int(H * 0.78)

with open(moments_path) as f:
    moments = json.load(f)
with open(transcript_path) as f:
    transcript = json.load(f)

for i, moment in enumerate(moments):
    moment_id = i + 1
    clip_path = os.path.join(clips_dir, f'clip_{moment_id:02d}.mp4')
    if not os.path.exists(clip_path):
        continue

    clip_start = moment['start']
    clip_end = moment['end']

    # Filter transcript segments for this clip
    clip_segments = [
        {'start': max(0, s['start'] - clip_start),
         'end': min(clip_end - clip_start, s['end'] - clip_start),
         'text': s['text'].strip()}
        for s in transcript
        if s['end'] > clip_start and s['start'] < clip_end and s['text'].strip()
    ]

    if not clip_segments:
        print(f'Clip {moment_id}: no segments, skipping')
        continue

    probe = subprocess.run([
        'ffprobe', '-v', 'quiet',
        '-show_entries', 'stream=width,height,r_frame_rate',
        '-of', 'json',
        clip_path
    ], capture_output=True, text=True, check=True)
    probe_data = json.loads(probe.stdout)
    streams = probe_data.get('streams', [])
    if not streams:
        raise SystemExit(f'Clip {moment_id}: ffprobe returned no stream info')
    stream = streams[0]
    width = stream.get('width')
    height = stream.get('height')
    if width != W or height != H:
        raise SystemExit(f'Clip {moment_id}: expected {W}x{H}, got {width}x{height}')
    fps_str = stream.get('r_frame_rate', '')
    if fps_str in ('', '0/0'):
        raise SystemExit(f'Clip {moment_id}: invalid frame rate {fps_str or "<empty>"}')
    fps_num, fps_den = map(int, fps_str.split('/'))
    if fps_den == 0 or fps_num == 0:
        raise SystemExit(f'Clip {moment_id}: invalid frame rate {fps_str}')
    fps = fps_num / fps_den

    # Save original for audio
    tmp_path = clip_path + '.orig.mp4'
    os.rename(clip_path, tmp_path)

    decoder = subprocess.Popen(
        ['ffmpeg', '-i', tmp_path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-v', 'quiet', '-'],
        stdout=subprocess.PIPE)
    encoder = subprocess.Popen([
        'ffmpeg', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps),
        '-i', '-', '-i', tmp_path, '-map', '0:v', '-map', '1:a',
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', '-c:a', 'copy', '-v', 'quiet', clip_path
    ], stdin=subprocess.PIPE)

    frame_size = W * H * 3
    frame_idx = 0
    max_w = W - MARGIN * 2

    while True:
        raw = decoder.stdout.read(frame_size)
        if len(raw) < frame_size:
            break
        t = frame_idx / fps
        frame_idx += 1

        active_text = None
        for seg in clip_segments:
            if seg['start'] <= t < seg['end']:
                active_text = seg['text']
                break

        if active_text:
            img = Image.frombytes('RGB', (W, H), raw)
            draw = ImageDraw.Draw(img)

            # Word wrap if text exceeds frame width
            bbox = draw.textbbox((0, 0), active_text, font=FONT)
            tw = bbox[2] - bbox[0]

            if tw > max_w:
                words = active_text.split()
                lines = []
                current = ''
                for word in words:
                    test = (current + ' ' + word).strip()
                    test_bbox = draw.textbbox((0, 0), test, font=FONT)
                    if test_bbox[2] - test_bbox[0] > max_w and current:
                        lines.append(current)
                        current = word
                    else:
                        current = test
                if current:
                    lines.append(current)
                text_to_draw = chr(10).join(lines)
            else:
                text_to_draw = active_text

            bbox = draw.multiline_textbbox((0, 0), text_to_draw, font=FONT)
            tw = bbox[2] - bbox[0]
            x = (W - tw) // 2

            # Black outline
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    draw.multiline_text((x+dx, SUB_Y+dy), text_to_draw, font=FONT, fill='black', align='center')
            draw.multiline_text((x, SUB_Y), text_to_draw, font=FONT, fill='white', align='center')

            raw = img.tobytes()

        encoder.stdin.write(raw)

    decoder.stdout.close()
    encoder.stdin.close()
    decoder.wait()
    encoder.wait()
    os.remove(tmp_path)
    print(f'Clip {moment_id}: subtitles burned ({len(clip_segments)} segments)')

print('All subtitles burned.')
"
