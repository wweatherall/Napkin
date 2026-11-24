### H142 — T128: Make `tools/job.py take` collision-proof for parallel Gemini workers

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: open | For: either

References: T128, P24, P37, T102, T117, T126.

Touches: tools/job.py (`default_agent`, `default_session`, `_take`, `guard_checkout`), tools/test_job.py, GEMINI.md.

Why: When two Gemini workers are launched in the same minute, both follow `GEMINI.md` and frequently invent the same manual `--session` name (e.g. `gemini-cedar-1124-0658`). The second worker then hits `refused: this session already holds H128` even though it is a completely different AGY conversation. Every AGY session already exports a unique `ANTIGRAVITY_CONVERSATION_ID` (and `ANTIGRAVITY_AGENT`) environment variable — using it automatically makes parallel `job.py take` collision-proof, enables `guard-checkout` (T102) for Gemini, and lets `tools/usage.py` find Gemini transcripts in O(1) by UUID.

Today (checked 2026-11-24):
- `tools/job.py`:
  - `default_agent()` (~374–379) checks `CLAUDECODE` / `CLAUDE_CODE_SESSION_ID` and `CODEX*`, returning `None` for Gemini/AGY.
  - `default_session(agent)` (~382–384) checks `CLAUDE_CODE_SESSION_ID`, `CODEX_SESSION_ID`, `CODEX_THREAD_ID`, else returns `agent` — ignoring `ANTIGRAVITY_CONVERSATION_ID` (and `SHOPSKETCH_SESSION`).
  - `guard_checkout()` (~387–395) calls `default_session(None)`, so it silently skips Gemini sessions today.
  - `_take()` (~425–475) checks `held` and `jobs_taken(st, session)` purely by the `--session` string: if a second Gemini conversation happens to pass the same manual `--session` name, it is refused.
- `GEMINI.md` (~7–10) tells Gemini workers to invent `gemini-<a short word>-<MMDD-HHMM>` for `job.py take --session`.

Request:
1. **Auto-detect Gemini/AGY in `tools/job.py`:**
   - `default_agent()`: return `"gemini"` when `os.environ.get("ANTIGRAVITY_AGENT") or os.environ.get("ANTIGRAVITY_CONVERSATION_ID")` is set (after Claude and Codex checks).
   - `default_session(agent)`: check `os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID") or os.environ.get("ANTIGRAVITY_CONVERSATION_ID") or os.environ.get("SHOPSKETCH_SESSION") or agent`.
   - Because `default_session(None)` now returns `ANTIGRAVITY_CONVERSATION_ID` in AGY sessions, `guard_checkout()` automatically protects Gemini workers too (verify with a unit test!).
2. **Prevent same-minute manual `--session` collisions in `_take()`:**
   - Keep `MAX_JOBS = 1` enforcement strict for the **same** session (P37: one session cannot take a second job!).
   - When `ANTIGRAVITY_CONVERSATION_ID` is set in the environment and the caller passed a manual `--session <name>` (i.e. `name != conv_id`):
     - Normalize/tag the session identity deterministically with the short conversation ID suffix (e.g. if `conv_id` is set and `not session.endswith("-" + conv_id[:8])` and `session != conv_id`, use `f"{session}-{conv_id[:8]}"` or store `"conv_id": conv_id` on the job record — **prefer deterministic suffix `f"{session}-{conv_id[:8]}"`** OR using `conv_id` when `--session` is omitted!).
     - Why deterministic suffix `f"{session}-{conv_id[:8]}"` when a manual `--session` is given alongside `ANTIGRAVITY_CONVERSATION_ID`?
       - Same conversation calling `take` twice with the same `--session` gets the **exact same** tagged session (`gemini-cedar-1124-0658-c56ddaee`), so `MAX_JOBS = 1` and `already holds` still refuse it cleanly!
       - Two **different** conversations calling `take` in the same minute with `gemini-cedar-1124-0658` get **distinct** session IDs (`...-c56ddaee` vs `...-a1b2c3d4`), so both succeed with zero collision and zero delay!
       - Also check `counted(session)`: ensure `counted()` still returns `True` for UUIDs and suffixed names (it checks `session not in AGENTS and bool(session)` — verify!).
       - And when `ANTIGRAVITY_CONVERSATION_ID` is NOT set (unit tests, non-AGY shells), keep exact existing `--session` behaviour unchanged!
3. **Update `GEMINI.md`:**
   - Tell Gemini workers they can simply run `python3 tools/job.py take --as gemini` with no `--session` flag (`job.py` automatically uses `ANTIGRAVITY_CONVERSATION_ID`), and keep the `gemini-<word>-<MMDD-HHMM>` fallback only for environments without `ANTIGRAVITY_CONVERSATION_ID` (e.g. `integrator.py take`).

What can fail (each gets a named test in `tools/test_job.py`, isolating `os.environ` cleanly):
1. Two different `ANTIGRAVITY_CONVERSATION_ID` values calling `take --as gemini` (with no `--session`) in the same run both succeed and take two non-overlapping jobs.
2. Two different `ANTIGRAVITY_CONVERSATION_ID` values calling `take --as gemini --session gemini-cedar-1124-0658` (same manual name!) both succeed without colliding.
3. The **same** `ANTIGRAVITY_CONVERSATION_ID` calling `take --as gemini` a second time (either holding a job or after `done`, P37 `MAX_JOBS=1`) is still refused!
4. `guard_checkout()` refuses running tests in the main checkout when `ANTIGRAVITY_CONVERSATION_ID` holds an active job in a worktree (and allows it when `SHOPSKETCH_ANY_CHECKOUT=1`).
5. Without `ANTIGRAVITY_CONVERSATION_ID`, existing `--session` collision/counting behaviour is 100% unchanged.

Cases that must still work:
- All existing checks in `tools/test_job.py`, `tools/test_usage.py`, `tools/test_integrate.py`, and `python3 tools/job.py test`.

Reading path: `tools/job.py` (`default_agent`, `default_session`, `guard_checkout`, `counted`, `_take`, `main` lines 1077–1095) → `tools/test_job.py` → `GEMINI.md`.

Run `python3 tools/test_job.py` and `tools/featuretest.sh` while building, then `python3 tools/job.py test`. End your response with `Follow-up:` lines for leftovers and a `Result:` line.
