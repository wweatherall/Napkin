#!/bin/bash
# The merge gate (P18): quick then full, one verdict; successful quick checks are reused (T90). A failure passes only
# when tests/known_failures.txt lists it (each line: the check's name as the quick test prints it, then "# T<n>"
# naming the Work list item that fixes it). The full test must pass outright.
#   tools/gate.sh          exit 0 = GATE PASS
# The other test entry points source these helpers before running their own checks.
set_test_tmpdir() {
  if [ -f .git ] && [ -f "$(git rev-parse --git-dir)/commondir" ]; then
    local scratch="$(pwd -P)/scratch" requested
    mkdir -p "$scratch" || return 1
    requested=$(cd "${TMPDIR:-/tmp}" 2>/dev/null && pwd -P)
    case "$requested/" in
      "$scratch/"*) export TMPDIR="$requested" ;;
      *) export TMPDIR="$scratch" ;;
    esac
  fi
  # In the main checkout, leave the caller's environment alone. With TMPDIR unset,
  # gate historically uses /tmp and its children use Darwin's per-user temp folder.
  TEST_TMPDIR=${TMPDIR:-${1:-$(getconf DARWIN_USER_TEMP_DIR 2>/dev/null || echo /tmp)}}
  [[ "$TEST_TMPDIR" = /* ]] || TEST_TMPDIR="$PWD/$TEST_TMPDIR"
}

run_stage() {
  local label=$1 start=$SECONDS rc verdict=passed
  shift
  echo "$label started"
  "$@"
  rc=$?
  [ "$rc" -eq 0 ] || verdict=failed
  echo "$label $verdict in $((SECONDS - start)) s"
  return "$rc"
}

run_features() {
  local out=$1; shift
  tools/featuretest.sh "$@" "$out/feature" > "$out/feature.log" 2>&1
}

resolve_test_scope() {
  local force_full=0 arg
  for arg in "$@"; do
    [ "$arg" = "--full" ] && force_full=1
  done
  [ "${GATE_FULL:-0}" = "1" ] && force_full=1
  if [ "$force_full" -eq 1 ]; then
    export GATE_FULL=1
    TEST_SCOPE=full
    TEST_SCOPE_DESC="scope full (forced)"
    return 0
  fi
  local out lines=()
  out=$(python3 tools/test_scope.py 2>/dev/null)
  if [ $? -ne 0 ] || [ -z "$out" ]; then
    TEST_SCOPE=full
    TEST_SCOPE_DESC="scope full (no diff)"
    return 0
  fi
  while IFS= read -r arg; do
    [ -n "$arg" ] && lines+=("$arg")
  done <<< "$out"
  TEST_SCOPE=${lines[0]:-full}
  local files=("${lines[@]:1}") count=${#files[@]} sample=""
  if [ "$count" -gt 0 ]; then
    local show=("${files[@]:0:5}")
    sample="${show[*]}"
    [ "$count" -gt 5 ] && sample="$sample ..."
  fi
  if [ "$TEST_SCOPE" = "tools" ]; then
    TEST_SCOPE_DESC="scope tools ($count file(s); app tests skipped: $sample)"
  else
    TEST_SCOPE=full
    if [ "$count" -gt 0 ]; then
      TEST_SCOPE_DESC="scope full ($count file(s): $sample)"
    else
      TEST_SCOPE_DESC="scope full (no diff)"
    fi
  fi
}

if [[ ${BASH_SOURCE[0]} != "$0" ]]; then return 0; fi

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo "$(dirname "$0")/..")" || exit 2   # the checkout you run it in
# Only exit on the guard's refusal; an unavailable helper must not block tests.
python3 tools/job.py guard-checkout
[ $? -eq 1 ] && exit 1
set_test_tmpdir /tmp || exit 1
OUT=$(mktemp -d "${TEST_TMPDIR%/}/napkin-gate.XXXXXX") || exit 1
KNOWN=tests/known_failures.txt
START=$SECONDS
# Keep the complete child log and forward its progress as each line arrives.
run_logged() {
  local log=$1 line
  shift
  "$@" 2>&1 | tee "$log" | while IFS= read -r line; do
    case "$line" in "quick: "*|"full: "*) echo "$line" ;; esac
  done
  local statuses=("${PIPESTATUS[@]}")
  [ "${statuses[1]}" -eq 0 ] || return 1
  return "${statuses[0]}"
}
resolve_test_scope "$@"
echo "$TEST_SCOPE_DESC"
GATE_HEAD=$(git rev-parse HEAD 2>/dev/null)
GATE_CLEAN=0
[ -z "$(git status --porcelain 2>/dev/null)" ] && GATE_CLEAN=1
run_stage "gate: quick test" run_logged "$OUT/quick.log" tools/quicktest.sh
QRC=$?
if [ "$QRC" -eq 0 ] && [ "$TEST_SCOPE" != "tools" ] && [ -n "$GATE_HEAD" ]; then
  python3 tools/job.py record-test --commit "$GATE_HEAD" --clean "$GATE_CLEAN" >/dev/null 2>&1 || true
fi
if [ "$TEST_SCOPE" = "tools" ]; then
  FRC=0
else
  # A successful quick run already parsed every script and checked every feature. Reuse those checks.
  # After any quick failure, retain fulltest's independent parse and feature checks.
  FULL_ARGS=()
  if [ $QRC -eq 0 ] && grep -qE "^features:.*\| viewport: QUICK" "$OUT/quick.log" &&
     ! grep -q "SCRIPT ERROR" "$OUT/quick.log"; then FULL_ARGS=(--gate-ui-only); fi
  run_stage "gate: full test" run_logged "$OUT/full.log" tools/fulltest.sh "${FULL_ARGS[@]}"
  FRC=$?
fi
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
if [ "$TEST_SCOPE" = "tools" ]; then
  if [ $NEW -eq 0 ]; then
    echo "GATE PASS (scope tools): tools quick test passes; $((SECONDS - START)) s total (logs: $OUT)"; exit 0
  fi
  echo "GATE FAIL (scope tools): $NEW new quick-test failure(s); $((SECONDS - START)) s total (logs: $OUT)"; exit 1
fi
if [ $NEW -eq 0 ] && [ $FRC -eq 0 ]; then
  echo "GATE PASS: full test passes; ${Q:-quick test}; $KNOWN_SEEN known failure(s); $((SECONDS - START)) s total (logs: $OUT)"; exit 0
fi
echo "GATE FAIL: $NEW new quick-test failure(s); full test $([ $FRC -eq 0 ] && echo passes || echo FAILS); $((SECONDS - START)) s total (logs: $OUT)"; exit 1
