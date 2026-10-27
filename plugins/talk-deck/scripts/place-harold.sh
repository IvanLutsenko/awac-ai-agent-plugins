#!/usr/bin/env bash
# Copy a Harold picture into a deck's media folder.
# Usage: place-harold.sh [deck] [image]
# Without an image, takes the newest picture in ~/Downloads. Shrinks only a
# picture wider than 2000 px, never enlarges. Prints the stored path.

source "$(dirname "$0")/lib.sh"

deck="$(td_resolve_deck "${1:-}")" || { echo "talk-deck: no Craft deck at '${1:-$PWD}'" >&2; exit 1; }
image="${2:-}"
if [[ -z "$image" ]]; then
  image="$(ls -t "$HOME/Downloads"/*.{png,jpg,jpeg,webp,PNG,JPG,JPEG,WEBP} 2>/dev/null | head -1)"
fi
[[ -f "$image" ]] || { echo "talk-deck: no picture found; pass its path" >&2; exit 1; }

width="$(sips -g pixelWidth "$image" 2>/dev/null | awk '/pixelWidth/ {print $2}')"
[[ "$width" =~ ^[0-9]+$ ]] || { echo "talk-deck: cannot read the size of $image" >&2; exit 1; }

mkdir -p "$deck/media"
ext="$(echo "${image##*.}" | tr '[:upper:]' '[:lower:]')"
if command -v cwebp >/dev/null; then
  target="media/harold.webp"
  args=(-quiet -q 82)
  (( width > 2000 )) && args+=(-resize 2000 0)
  cwebp "${args[@]}" "$image" -o "$deck/$target" || exit 1
elif [[ "$ext" == "webp" ]]; then
  # sips reads WebP but cannot write it, so the picture is kept as it is.
  target="media/harold.webp"
  cp "$image" "$deck/$target" || exit 1
  (( width > 2000 )) && echo "warning: $width px wide; install cwebp to shrink it" >&2
else
  target="media/harold.jpg"
  args=(-s format jpeg -s formatOptions 85)
  (( width > 2000 )) && args+=(--resampleWidth 2000)
  sips "${args[@]}" "$image" --out "$deck/$target" >/dev/null || exit 1
fi

# One Harold per deck: drop the other format left by an earlier run.
for old in "$deck"/media/harold.webp "$deck"/media/harold.jpg; do
  [[ "$old" != "$deck/$target" ]] && rm -f "$old"
done

echo "source=$image ($(stat -f '%Sm' "$image"))"
echo "stored=$target"
echo "width=$width"
(( width < 1600 )) && echo "warning: under 1600 px, it will look soft on a projector" >&2
exit 0
