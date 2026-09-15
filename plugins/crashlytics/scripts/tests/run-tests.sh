#!/usr/bin/env bash
# Smoke tests for validate-report.py.
#
# Each fixture should validate to 14/14 with pass: true.
# - sample-en-report.md       English headers, English body
# - sample-ru-report.md        English headers (live forensics output), Russian body
# - sample-translated-*.md    Translated headers + translated body — exercises SECTION_ALIASES
#
# Run: bash scripts/tests/run-tests.sh

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
VALIDATOR="$HERE/../validate-report.py"
RESULTS=()

run_one() {
    local fixture="$1"
    local label="$2"
    # Extract the Firebase URL from the fixture itself so the URL-match check passes.
    local url
    url=$(grep -oE 'https://console\.firebase\.google\.com[^[:space:]"]*' "$fixture" | head -1)
    local out
    if [[ -n "$url" ]]; then
        out=$(python3 "$VALIDATOR" --console-url "$url" < "$fixture" 2>&1)
    else
        out=$(python3 "$VALIDATOR" < "$fixture" 2>&1)
    fi
    local score
    score=$(printf '%s\n' "$out" | awk '/score:/ {gsub(/[",]/,""); print $2; exit}')
    local pass
    pass=$(printf '%s\n' "$out" | awk '/pass:/ {print $2; exit}')
    if [[ "$pass" == "true" && "$score" == "14/14" ]]; then
        printf '  %-45s OK  %s\n' "$label" "$score"
        RESULTS+=("OK")
    else
        printf '  %-45s FAIL pass=%s score=%s\n' "$label" "$pass" "$score"
        printf '    %s\n' "$out" | sed 's/^/    /'
        RESULTS+=("FAIL")
    fi
}

echo "Validator smoke tests:"
run_one "$HERE/sample-en-report.md"          "en (English headers, English body)"
run_one "$HERE/sample-ru-report.md"          "ru (English headers, Russian body)"
run_one "$HERE/sample-translated-es.md"      "es (translated headers — alias check)"
run_one "$HERE/sample-translated-de.md"      "de (translated headers — alias check)"
run_one "$HERE/sample-translated-fr.md"      "fr (translated headers — alias check)"
run_one "$HERE/sample-translated-pt.md"      "pt (translated headers — alias check)"
run_one "$HERE/sample-translated-it.md"      "it (translated headers — alias check)"

# Negative case: `git fetch` alone is a pre-flight step, not evidence of inspection.
printf '  %-45s ' "negative (fetch alone is not evidence)"
if python3 - "$VALIDATOR" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("v", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.chk_executed_commands({'executed commands': 'git fetch origin --quiet'}) == 'MISSING'
assert m.chk_executed_commands({'executed commands': 'git blame -L 200,220 -- a.kt'}) == 'OK'
PY
then
    echo "OK"
    RESULTS+=("OK")
else
    echo "FAIL"
    RESULTS+=("FAIL")
fi

failed=0
for r in "${RESULTS[@]}"; do
    [[ "$r" == "FAIL" ]] && failed=$((failed+1))
done
echo
if [[ $failed -eq 0 ]]; then
    echo "All ${#RESULTS[@]} fixtures passed."
    exit 0
else
    echo "$failed of ${#RESULTS[@]} fixtures failed."
    exit 1
fi
