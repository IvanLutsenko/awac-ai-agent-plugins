#!/usr/bin/env bash
# Everything /deck-publish needs before the card is written: the deck must
# live in the site repo and pass the full check; the cover is rendered.
# Usage: publish-prep.sh [deck]

source "$(dirname "$0")/lib.sh"

td_require "${1:-}" || exit 1
site="$(td_site_repo)"
[[ -n "$site" && -d "$site" ]] || { echo "talk-deck: site_repo is not set or missing" >&2; exit 1; }
deck_real="$(cd "$deck" && pwd -P)"
site_real="$(cd "$site" && pwd -P)"
[[ "$deck_real" == "$site_real"/* ]] || { echo "talk-deck: $deck is not inside the site repo $site" >&2; exit 1; }

python3 "$craft/scripts/check_project.py" "$deck" --full || { echo "talk-deck: the deck fails the full check" >&2; exit 1; }

# The cover for the card: the first slide in its final frame, 1600x900.
rm -f "$deck/cover.png"
python3 - "$craft" "$deck" <<'PY' || exit 1
import subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from lib import chromium_args
deck = Path(sys.argv[2])
page = (deck / "index.html").as_uri() + "?reveal=final&motion=static#1"
# Chrome on macOS may exit non-zero on teardown after writing the file.
subprocess.run([*chromium_args(1600, 900), f"--screenshot={deck / 'cover.png'}", page], capture_output=True)
sys.exit(0 if (deck / "cover.png").is_file() else "talk-deck: Chromium wrote no cover")
PY
size="$(sips -g pixelWidth -g pixelHeight "$deck/cover.png" | awk '/pixel/ {printf "%s ", $2}')"
[[ "$size" == "1600 900 " ]] || { echo "talk-deck: the cover is ${size:-unreadable}, not 1600x900" >&2; exit 1; }
sips -s format jpeg -s formatOptions 82 "$deck/cover.png" --out "$deck/cover.jpg" >/dev/null && rm "$deck/cover.png" || exit 1

closing="end"
grep -q 'data-slide-layout="harold"' "$deck/index.html" && closing="harold"
echo "deck=$deck"
echo "site=$site"
echo "path=${deck_real#"$site_real"/}"
echo "cover=${deck_real#"$site_real"/}/cover.jpg"
echo "closing=$closing"
exit 0
