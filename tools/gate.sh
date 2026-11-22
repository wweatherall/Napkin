#!/bin/bash
# The merge gate (P18): quick then full, one verdict; successful quick checks are reused (T90). A failure passes only
# when tests/known_failures.txt lists it (each line: the check's name as the quick test prints it, then "# T<n>"
# naming the Work list item that fixes it). The full test must pass outright.
#   tools/gate.sh          exit 0 = GATE PASS
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo "$(dirname "$0")/..")" || exit 2   # the checkout you run it in
OUT=$(mktemp -d "${TMPDIR:-/tmp}/shopsketch-gate.XXXXXX")
KNOWN=tests/known_failures.txt
START=$SECONDS
tools/quicktest.sh > "$OUT/quick.log" 2>&1; QRC=$?
# A successful quick run already parsed every script and checked every feature. Reuse those checks.
# After any quick failure, retain fulltest's independent parse and feature checks.
FULL_ARGS=()
if [ $QRC -eq 0 ] && grep -qE "^features:.*\| viewport: QUICK" "$OUT/quick.log" &&
   ! grep -q "SCRIPT ERROR" "$OUT/quick.log"; then FULL_ARGS=(--gate-ui-only); fi
tools/fulltest.sh "${FULL_ARGS[@]}" > "$OUT/full.log" 2>&1; FRC=$?
NEW=0; KNOWN_SEEN=0
while IFS= read -r line; do
  name=$(echo "$line" | sed -E 's/^QUICK FAIL (\[[^]]*\] [^<[{]*[^ <[{]).*/\1/; s/ +$//')
  if [ -f "$KNOWN" ] && grep -vE '^\s*(#|$)' "$KNOWN" | sed -E 's/ *#.*//' | grep -qxF "$name"; then
    KNOWN_SEEN=$((KNOWN_SEEN + 1)); echo "known: $name"
  else
    NEW=$((NEW + 1)); echo "NEW FAILURE: $line"
  fi
done < <(grep -hE "^QUICK FAIL" "$OUT/quick.log")
# The feature tests (no window) must pass on their own: a known UI failure never excuses one of them.
FEAT=$(grep -E "^features:" "$OUT/quick.log" | tail -1 | sed "s/ | viewport:.*//")
if [ -z "$FEAT" ]; then NEW=$((NEW + 1)); echo "NEW FAILURE: the quick test printed no feature-test summary (see $OUT/quick.log)"
elif echo "$FEAT" | grep -qE " [1-9][0-9]* failed"; then NEW=$((NEW + 1)); echo "NEW FAILURE: feature tests: $(echo "$FEAT" | grep -oE "[A-Z ]+TESTS: [0-9]+ passed, [1-9][0-9]* failed" | tr '\n' ';')"; fi
grep -qE "SCRIPT ERROR|did not finish" "$OUT/quick.log" && { NEW=$((NEW + 1)); echo "NEW FAILURE: the quick test didn't finish cleanly (see $OUT/quick.log)"; }
[ $QRC -ne 0 ] && [ $NEW -eq 0 ] && [ $KNOWN_SEEN -eq 0 ] && { NEW=1; echo "NEW FAILURE: the quick test failed without a QUICK FAIL line (see $OUT/quick.log)"; }
[ $FRC -ne 0 ] && grep -vE "^(SHOT|JOINTEST|REJECTTEST|SHELLTEST)" "$OUT/full.log" | tail -5
Q=$(grep -E "\| viewport: QUICK" "$OUT/quick.log" | sed -E 's/.*viewport: (QUICK [^(]*).*/\1/')
if [ $NEW -eq 0 ] && [ $FRC -eq 0 ]; then
  echo "GATE PASS: full test passes; ${Q:-quick test}; $KNOWN_SEEN known failure(s); $((SECONDS - START)) s total (logs: $OUT)"; exit 0
fi
echo "GATE FAIL: $NEW new quick-test failure(s); full test $([ $FRC -eq 0 ] && echo passes || echo FAILS); $((SECONDS - START)) s total (logs: $OUT)"; exit 1
