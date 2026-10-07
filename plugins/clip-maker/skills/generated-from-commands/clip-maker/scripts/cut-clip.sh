#!/bin/bash
# cut-clip.sh — cut and crop clips from video
# Usage: cut-clip.sh <video_path> <moments_json> <crop_coords_json> <output_dir>

set -euo pipefail

VIDEO_PATH="$1"
MOMENTS_JSON="$2"
CROP_COORDS_JSON="$3"
OUTPUT_DIR="$4"

mkdir -p "$OUTPUT_DIR"

VIDEO_PATH="$VIDEO_PATH" MOMENTS_JSON="$MOMENTS_JSON" CROP_COORDS_JSON="$CROP_COORDS_JSON" OUTPUT_DIR="$OUTPUT_DIR" python3 -c "
import json, subprocess, os
import sys

with open(os.environ['MOMENTS_JSON']) as f:
    moments = json.load(f)
with open(os.environ['CROP_COORDS_JSON']) as f:
    crops = json.load(f)

# Index crops by moment_id
crop_map = {c['moment_id']: c for c in crops}

for i, moment in enumerate(moments):
    moment_id = i + 1
    crop = crop_map.get(moment_id, crop_map.get(str(moment_id)))
    if crop is None:
        print(f'Moment {moment_id}: no crop coords', file=sys.stderr)
        sys.exit(1)

    start = moment['start']
    duration = moment['end'] - moment['start']
    output_path = os.path.join(os.environ['OUTPUT_DIR'], f'clip_{moment_id:02d}.mp4')

    crop_w = crop['crop_width']
    crop_h = crop['crop_height']
    crop_x = crop['crop_x']
    crop_y = crop.get('crop_y', 0)

    vf = f'crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale=1080:1920'

    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', os.environ['VIDEO_PATH'],
        '-t', str(duration),
        '-vf', vf,
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
        '-c:a', 'aac', '-b:a', '128k',
        output_path
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        if e.stderr:
            print(e.stderr, file=sys.stderr, end='')
        sys.exit(e.returncode or 1)
    print(f'Clip {moment_id}: {duration:.1f}s → {output_path}')
"

echo "All clips cut to $OUTPUT_DIR"
