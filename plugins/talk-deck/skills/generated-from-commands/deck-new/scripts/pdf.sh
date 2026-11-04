#!/usr/bin/env bash
# PDF of a Craft deck for organizers, in ~/Downloads/talk-deck/<slug>.
# Usage: pdf.sh [deck] [--final] [--archive] [--into dir]
#   default     a page per reveal step, built by Craft's release.py
#   --final     a page per slide in its final frame
#   --archive   also keep the release ZIP, the offline deck for the venue
#   --into dir  final frames into <dir>/<slug>.pdf; inside a GitLab or GitHub
#               repo also print the blob link it gets once committed and pushed

source "$(dirname "$0")/lib.sh"

deck_arg="" final=0 archive=0 into=""
while (( $# )); do
  case "$1" in
    --final) final=1 ;;
    --archive) archive=1 ;;
    --into) into="${2:-}"; shift; [[ -n "$into" ]] || { echo "talk-deck: --into needs a folder" >&2; exit 1; } ;;
    *) deck_arg="$1" ;;
  esac
  shift
done
[[ -n "$into" ]] && final=1

td_require "$deck_arg" || exit 1
python3 "$craft/scripts/check_project.py" "$deck" --full || { echo "talk-deck: the deck fails the full check, no PDF" >&2; exit 1; }

slug="$(basename "$deck")"
out="${into:-$HOME/Downloads/talk-deck/$slug}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$out"
out="$(cd "$out" && pwd)"
pdf="$out/$slug.pdf"
rm -f "$pdf"

if (( !final || archive )); then
  release_args=(--out "$work" --name "$slug" --check static)
  (( final )) || release_args+=(--pdf)
  python3 "$craft/scripts/release.py" "$deck" "${release_args[@]}" || exit 1
  zip="$(ls "$work"/*.zip | head -1)"
  if (( !final )); then
    unzip -o -j -q "$zip" "*.pdf" -d "$work/pdf" && mv "$work/pdf/"*.pdf "$pdf" || exit 1
  fi
  (( archive )) && cp "$zip" "$out/$slug.zip"
fi

if (( final )); then
  td_print_final "$deck" "$pdf"
fi

[[ -s "$pdf" ]] || { echo "talk-deck: no PDF was written" >&2; exit 1; }
pages="$(python3 -c 'import re,sys; print(len(re.findall(rb"/Type\s*/Page[^s]", open(sys.argv[1], "rb").read())))' "$pdf")"
echo "pdf=$pdf"
echo "pages=$pages"
(( pages > 0 )) || echo "warning: could not count the pages; open the PDF to check it" >&2
echo "size=$(du -h "$pdf" | cut -f1)"
(( archive )) && echo "zip=$out/$slug.zip"
if [[ -n "$into" ]]; then
  link="$(td_blob_link "$pdf")" && echo "link=$link"
fi
exit 0
