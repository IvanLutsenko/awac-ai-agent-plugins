#!/usr/bin/env bash
# PDF of a Craft deck for organizers, in ~/Downloads/talk-deck/<slug>.
# Usage: pdf.sh [deck] [--final] [--archive]
#   default    a page per reveal step, built by Craft's release.py
#   --final    a page per slide in its final frame
#   --archive  also keep the release ZIP, the offline deck for the venue

source "$(dirname "$0")/lib.sh"

deck_arg="" final=0 archive=0
for arg in "$@"; do
  case "$arg" in
    --final) final=1 ;;
    --archive) archive=1 ;;
    *) deck_arg="$arg" ;;
  esac
done

td_require "$deck_arg" || exit 1
python3 "$craft/scripts/check_project.py" "$deck" --full || { echo "talk-deck: the deck fails the full check, no PDF" >&2; exit 1; }

slug="$(basename "$deck")"
out="$HOME/Downloads/talk-deck/$slug"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$out"
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
  # Craft's own Chromium flags, so fonts and the deck's layout settle before printing.
  python3 - "$craft" "$deck" "$pdf" <<'PY' || exit 1
import subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from lib import chromium_args
deck, pdf = Path(sys.argv[2]), sys.argv[3]
page = (deck / "index.html").as_uri() + "?reveal=final&motion=static"
# Chrome on macOS may exit non-zero on teardown after writing the file;
# the size check after this block decides.
subprocess.run([*chromium_args(1280, 720), "--no-pdf-header-footer", f"--print-to-pdf={pdf}", page], capture_output=True)
PY
fi

[[ -s "$pdf" ]] || { echo "talk-deck: no PDF was written" >&2; exit 1; }
pages="$(python3 -c 'import re,sys; print(len(re.findall(rb"/Type\s*/Page[^s]", open(sys.argv[1], "rb").read())))' "$pdf")"
echo "pdf=$pdf"
echo "pages=$pages"
(( pages > 0 )) || echo "warning: could not count the pages; open the PDF to check it" >&2
echo "size=$(du -h "$pdf" | cut -f1)"
(( archive )) && echo "zip=$out/$slug.zip"
exit 0
