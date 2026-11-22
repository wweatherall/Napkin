#!/bin/bash
# The merge gate (P-new-2): the quick test, then the full test, one verdict line. A quick-test failure passes only
# when tests/known_failures.txt lists it (each line: the check's name as the quick test prints it, then "# T<n>"
# naming the Work list item that fixes it). The full test must pass outright.
#   tools/gate.sh          exit 0 = GATE PASS
cd "$(dirname "$0")/.." || exit 2
OUT=$(mktemp -d "${TMPDIR:-/tmp}/shopsketch-gate.XXXXXX")
KNOWN=tests/known_failures.txt
tools/quicktest.sh > "$OUT/quick.log" 2>&1; QRC=$?
tools/fulltest.sh > "$OUT/full.log" 2>&1; FRC=$?
NEW=0; KNOWN_SEEN=0
while IFS= read -r line; do
  name=$(echo "$line" | sed -E 's/^QUICK FAIL (\[[^]]*\] [^<[{]*[^ <[{]).*/\1/; s/ +$//')
  if [ -f "$KNOWN" ] && grep -vE '^\s*(#|$)' "$KNOWN" | sed -E 's/ *#.*//' | grep -qxF "$name"; then
    KNOWN_SEEN=$((KNOWN_SEEN + 1)); echo "known: $name"
  else
    NEW=$((NEW + 1)); echo "NEW FAILURE: $line"
  fi
done < <(grep -hE "^QUICK FAIL" "$OUT/quick.log")
grep -qE "SCRIPT ERROR|did not finish" "$OUT/quick.log" && { NEW=$((NEW + 1)); echo "NEW FAILURE: the quick test didn't finish cleanly (see $OUT/quick.log)"; }
[ $QRC -ne 0 ] && [ $NEW -eq 0 ] && [ $KNOWN_SEEN -eq 0 ] && { NEW=1; echo "NEW FAILURE: the quick test failed without a QUICK FAIL line (see $OUT/quick.log)"; }
[ $FRC -ne 0 ] && grep -vE "^(SHOT|JOINTEST|REJECTTEST|SHELLTEST)" "$OUT/full.log" | tail -5
Q=$(grep -E "\| viewport: QUICK" "$OUT/quick.log" | sed -E 's/.*viewport: (QUICK [^(]*).*/\1/')
if [ $NEW -eq 0 ] && [ $FRC -eq 0 ]; then
  echo "GATE PASS: full test passes; ${Q:-quick test}; $KNOWN_SEEN known failure(s) (logs: $OUT)"; exit 0
fi
echo "GATE FAIL: $NEW new quick-test failure(s); full test $([ $FRC -eq 0 ] && echo passes || echo FAILS) (logs: $OUT)"; exit 1
