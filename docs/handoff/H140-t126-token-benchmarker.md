### H140 — T126: Token benchmarker (`tools/usage.py`): AGY/Gemini support, quota fixes, fast `orient`/`bench` CLI, and workflow integration

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: open | For: either

References: T126, T117, H124, P37, P39, P40, `/Users/Will/Sites/job-usage/job_usage.py`, `/Users/Will/Sites/job-usage/test_job_usage.py`, `scratch/compare_orient.py`.

Touches: tools/usage.py (new), tools/test_usage.py (new), tools/job.py (`USAGE_TOOL`, `record_usage`), tools/integrate.py (`clean_up_job`), tools/test_job.py, tools/test_integrate.py. Not docs/integrator.md (put the updated command summary in a `For the integrator:` line). Not `/Users/Will/Sites/job-usage/` (external folder outside this repo; read it as the starting point and vendor into `tools/usage.py`).

Why: T117 wired passive usage hooks pointing at external `/Users/Will/Sites/job-usage/job_usage.py`, and benchmarking Gemini integrator startups uncovered five real gaps: (1) `holes` only parses Claude's transcript JSON schema and returns 0 tokens on AGY/Gemini transcripts, (2) Gemini transcript auto-discovery assumes `session` is an AGY UUID instead of a fretchup session name like `gemini-maple-1123-2132`, (3) Gemini has no `session_metrics`/`model`/`overhead` tracking and `detect_concurrency` misses Gemini integrator overlap with Gemini workers, (4) `compute_bucket_burn` doesn't filter transient downward dips or clamp `pad_after` against an immediately following session, and (5) benchmarking integrator startup or worker jobs still requires ad-hoc scripts (`scratch/compare_orient.py`). Vendoring into `tools/usage.py` puts it under version control and `featuretest.sh`, fixes all five gaps, and makes fast benchmarking part of the standard workflow on models/environments that have local monitor logs.

Today (checked 2026-11-24):
- `/Users/Will/Sites/job-usage/job_usage.py` (1,528 lines, stdlib-only) implements `snapshot`, `backfill`, `report`, `overhead`, `compare`, `holes`, `export`, `viz`; `/Users/Will/Sites/job-usage/test_job_usage.py` (164 lines) has 6 unit tests.
- `tools/job.py` (~84–102): `USAGE_TOOL = "/Users/Will/Sites/job-usage/job_usage.py"`; `record_usage()` reads `SHOPSKETCH_USAGE_TOOL` (default `USAGE_TOOL`), skips if empty/missing, runs `snapshot` fail-open with `timeout=5`.
- `tools/integrate.py` (`clean_up_job`, ~976–989): calls `job.record_usage(root, "merge", merged_id, quiet=False)`.
- `scratch/compare_orient.py` (untracked): scans `~/.gemini/antigravity-cli/brain/*/transcript.jsonl` only on the *first* `USER_INPUT` turn (so it missed `gemini-birch-1124-0054` where turn 1 was a stray `agy` prompt and turn 2 was `hello you are the integrator`), and prints tokens only with no `gemini-5h` % or concurrency check.
- AGY `transcript.jsonl` schema (verified on real transcripts in `~/.gemini/antigravity-cli/brain/`):
  - User turns: `{"type": "USER_INPUT", "created_at": "...Z", "content": "...<USER_REQUEST>...</USER_REQUEST>..."}`.
  - Model turns: `{"type": "PLANNER_RESPONSE", "created_at": "...Z", "model": "gemini-4-neon-medium", "input_tokens": 11173, "cache_read_tokens": 0, "output_tokens": 292, "tool_calls": [{"name": "...", "args": {...}}]}`.
  - Tool outputs: separate `{"type": "GENERIC", "created_at": "...Z", "content": "..."}` rows following the `PLANNER_RESPONSE`.

Request:
1. **Vendor into `tools/usage.py` and `tools/test_usage.py` (stdlib-only, executable):**
   - Port `/Users/Will/Sites/job-usage/job_usage.py` into `tools/usage.py` and its tests into `tools/test_usage.py` (matching `tools/test_*.py` conventions so `tools/featuretest.sh` runs it automatically — check how `featuretest.sh` discovers `tools/test_*.py`!).
   - In `tools/job.py`, change default `USAGE_TOOL` to `os.path.join(os.path.dirname(os.path.abspath(__file__)), "usage.py")` (still overridable/disableable via `SHOPSKETCH_USAGE_TOOL`). Keep fail-open behaviour (`timeout=5`, never blocks or fails `job.py` / `integrate.py`).
2. **Fix AGY (Gemini) transcript parsing in `analyze_transcript()` (`holes`):**
   - Auto-detect both Claude JSONL (`message.usage` + `tool_use`/`tool_result` blocks) and AGY JSONL (`type == "PLANNER_RESPONSE"` with top-level `input_tokens`, `cache_read_tokens`, `output_tokens`, `tool_calls`, and following `type == "GENERIC"` rows).
   - Return accurate `turns`, `input_tokens` (fresh), `cache_read_tokens`, `output_tokens`, `cache_hit_pct`, `ctx_start`/`ctx_median`/`ctx_peak` (`input_tokens + cache_read_tokens`), `top_tool_outputs`, `repeated_reads`, and `flags` for both formats.
3. **Add AGY (Gemini) transcript auto-discovery & `session_metrics`:**
   - Add an AGY brain directory option `--agy-brain` (default `~/.gemini/antigravity-cli/brain`, overridable for tests; fail-open if unreadable/sandboxed).
   - Update `discover_transcript()` for `agent == "gemini"` so it finds the matching transcript even when `session` is a fretchup session name (e.g. `gemini-maple-1123-2132`): first check direct UUID path, then scan recent transcripts (filtered by mtime near `[taken, done]`) for the job ID / `--session <session>` / worktree path in tool calls.
   - Add `summarize_agy_session(transcript_path, start_s=None, end_s=None)` returning `{"model", "turns", "input_tokens", "cache_read_tokens", "output_tokens", "peak_context"}` and populate `record["session_metrics"]` and `record["model"]` for Gemini jobs in `build_job_record()` (fail-open when transcripts are outside sandbox / missing).
   - Update `cmd_snapshot` (at `merge` when `quiet=False`) to include the concise token total (e.g. `45.6k in / 1.2k out`) alongside the `5h` quota delta when `session_metrics` is available!
4. **Add Gemini integrator concurrency & `overhead` support:**
   - In `detect_concurrency()`, when `agent == "gemini"` and AGY transcripts are readable, detect whether a Gemini integrator session had `PLANNER_RESPONSE` turns during `[start_s, end_s]`, tagging `shared-int` / `shared-both` just as Claude does.
   - Extend `cmd_overhead` to report worker vs. integrator token breakdown for **both** Claude (`sessions.jsonl`) and Gemini (AGY transcripts classified by `integrator.py take` / `--role integrator` vs `job.py take` / worktree), cleanly skipping either side if its log dir is absent/unreadable.
5. **Fix `compute_bucket_burn()` short-window noise:**
   - Filter transient **downward** rebound glitches too (if `prev - cur > 0.002` and a sample within the next few readings rebounds back near `prev`, drop the glitch sample — matching the existing upward `1.0` glitch filter!).
   - Accept optional `next_event_s` (or tighter `pad_after` default when benchmarking short windows like orientation, e.g. `pad_after=45.0` clamped before the next session/turn's start time) so an immediately following session doesn't bleed into a short window's burn.
6. **Add fast `orient` and `bench` subcommands (replacing `scratch/compare_orient.py`):**
   - `python3 tools/usage.py orient [--last N]` (default `N=7`):
     - Scans AGY transcripts (and Claude integrator sessions when present) efficiently (sort by mtime, stop once enough integrator sessions are found or filter by `--days`), detects integrator orientation on **any** `USER_INPUT` turn where `--role integrator` / `integrator.py take` / `"integrator"` appears (so sessions with a warm-up turn like `b0ee70ee` are never missed — reporting both the integrator turn and any prior warm-up turn clearly!).
     - Joins `agy-usage-monitor/history.jsonl` / `claude-usage/history.jsonl` to show measured `5h Δ` (noting if another session overlapped) AND a rough token-to-5h-% estimate calibrated from solo runs (clearly labelled `est` vs `meas`), plus `Calls`, `Fresh In`, `Cache`, `Total In`, `Out`, `Peak Ctx`, `Model` (human-readable), and `Session`.
   - `python3 tools/usage.py bench [--last N] [--agent claude|gemini]`:
     - One-command summary combining recent **worker** jobs (from the ledger: duration, `5h Δ`, tokens, peak ctx, concurrency) and recent **integrator** orientations, plus calibrated `~% per 100k weighted tokens` (for models with solo measured samples) so benchmarking either role takes one fast command.
   - Keep every command fast and fail-open when run inside a sandbox (if `~/.gemini/antigravity-cli/brain` or `agy-usage-monitor` isn't readable, print a clear one-line hint instead of crashing!).

What can fail (each gets a named unit test in `tools/test_usage.py`, using synthetic temp files — never reading real `~/.gemini` or `/Users/Will/Sites/agy-usage-monitor` in tests!):
1. `analyze_transcript()` parses a synthetic AGY `transcript.jsonl` (`PLANNER_RESPONSE` + `GENERIC` tool outputs + repeated `read_file` calls) and still parses Claude JSONL transcripts.
2. `discover_transcript()` locates a synthetic AGY transcript by fretchup session name (`gemini-cedar-1124-0100`) and by UUID, and returns `(None, None)` cleanly when brain dir is missing/unreadable.
3. `detect_concurrency()` marks a Gemini worker `shared-int` when a synthetic Gemini integrator transcript has turns overlapping `[taken, done]`, and `solo` when non-overlapping.
4. `compute_bucket_burn()` filters both upward `1.0` spikes and brief downward rebound dips (`0.761 -> 0.751 -> 0.757 -> 0.756`), and respects a clamped `pad_after` / `next_event_s` boundary.
5. `orient` detects an integrator startup on turn 2 after a stray warm-up turn 1 (like `b0ee70ee`), computes exact token totals + peak context + measured 5h burn, and produces clean output with `--json` or table mode.
6. `tools/test_job.py` and `tools/test_integrate.py` pass with `USAGE_TOOL` pointing at `tools/usage.py` (and remain completely isolated from `.git/shopsketch-usage.jsonl` via `--repo` / `SHOPSKETCH_USAGE_TOOL`).

Cases that must still work:
- Existing `job_usage.py` subcommands (`snapshot`, `backfill`, `report`, `compare`, `overhead`, `holes`, `export`, `viz`), `tools/test_job.py`, `tools/test_integrate.py`, `tools/featuretest.sh`, and `python3 tools/job.py test`.

Reading path: `/Users/Will/Sites/job-usage/job_usage.py` (`compute_bucket_burn`, `detect_concurrency`, `build_job_record`, `discover_transcript`, `analyze_transcript`, `cmd_snapshot`, `cmd_overhead`) → `/Users/Will/Sites/job-usage/test_job_usage.py` → `scratch/compare_orient.py` → `tools/job.py` (`USAGE_TOOL`, `record_usage`) → `tools/integrate.py` (`clean_up_job`) → `tools/featuretest.sh` (how `tools/test_*.py` is run).

Run `python3 tools/test_usage.py`, `python3 tools/test_job.py`, `python3 tools/test_integrate.py`, and `tools/featuretest.sh` while building, then `python3 tools/job.py test`. End your response with `Architecture:` lines (new `tools/usage.py` module), `For the integrator:` lines (update `docs/integrator.md` with `tools/usage.py orient` / `bench` / `viz` / `holes` commands and remove untracked `scratch/compare_orient.py`), `Follow-up:` lines for leftovers, and a `Result:` line.
