### H124 — T117: wire passive job-usage lifecycle hooks into job.py and integrate.py

Author: Gemini (integrator, gemini-cedar-1123-1844) | Date: 2026-11-23 | Status: answered | For: either

References: T117, P37, P39, P40, `/Users/Will/Sites/job-usage/README.md`.

Touches: tools/job.py (`_take`, `done`, `return_job`, new `record_usage` helper), tools/integrate.py (`clean_up_job`), tools/test_job.py, tools/test_integrate.py. Not docs/integrator.md (write the `viz` / `report` usage note as a `For the integrator:` line). Not `/Users/Will/Sites/job-usage/job_usage.py` (lives outside this repo).

Why: passive usage capture at job lifecycle boundaries (`take`, `done`, `return`, `merge`) costs zero extra tokens and writes to the untracked ledger `.git/shopsketch-usage.jsonl` (shared across worktrees, right next to `shopsketch-jobs.json`), letting us compare worker vs. integrator overhead, brief traits, and Claude vs. Gemini burn.

Today (checked 2026-11-23):
- `tools/job.py` manages job state in `.git/shopsketch-jobs.json` inside `_take` (~379–439), `done` (~720–764), and `return_job` (~777–787). None of them notifies `/Users/Will/Sites/job-usage/job_usage.py`.
- `tools/integrate.py` marks a job merged in `clean_up_job` (~975–981) via `job.merged(root, branch, out=say)` (which returns the merged job id `H0NN` or `None`) and optionally `job.merged(root, state["job_branch"], out=say)` for `--job`.
- `/Users/Will/Sites/job-usage/job_usage.py` accepts top-level `--repo <path>` before the subcommand `snapshot`:
  `python3 /Users/Will/Sites/job-usage/job_usage.py --repo <root> snapshot --event take|done|return|merge --job <H0NN> [--agent <agent>] [--session <session>] [--quiet]`.
  Passing `--repo <root>` routes the ledger to `<git-common-dir>/shopsketch-usage.jsonl` of `<root>` so unit tests running in temp repos never pollute `/Users/Will/Sites/fretchup/.git/shopsketch-usage.jsonl`.

Request:
1. In `tools/job.py`, add a fail-open helper `record_usage(root, event, jid, agent=None, session=None, quiet=True)`:
   - Reads the script path from `os.environ.get("SHOPSKETCH_USAGE_TOOL", "/Users/Will/Sites/job-usage/job_usage.py")` (an empty string disables the hook, so tests can opt out or inject a stand-in).
   - If the path doesn't exist (`not tool or not os.path.isfile(tool)`), returns immediately without spawning a subprocess (so machines without `job-usage` pay nothing).
   - Builds `[sys.executable, tool, "--repo", root, "snapshot", "--event", event, "--job", jid]`, adding `--agent <agent>` when given, `--session <session>` when given, and `--quiet` when `quiet=True`.
   - Runs `subprocess.run(cmd, check=False, timeout=5)` inside `try / except Exception: pass` so a missing/broken/hung usage script or unreadable monitor log can never block or fail a job command.
2. Call `record_usage(...)` after the queue lock is released (never inside `with locked(...)`, so a slow subprocess can't hold the queue lock):
   - At the end of `_take(...)`: `record_usage(root, "take", job["id"], agent=agent, session=session, quiet=True)`.
   - At the end of `done(...)`: `record_usage(main_root(cwd), "done", k, quiet=True)` (after `with_job` commits state `"done"`).
   - At the end of `return_job(...)`: `record_usage(main_root(cwd), "return", jid, quiet=True)` (after `with locked` commits state `"returned"`).
3. In `tools/integrate.py` `clean_up_job(s)`:
   - Capture the job id returned by `job.merged(root, branch, out=say)` (and, if `state.get("job_branch")` is set, the id returned by `job.merged(root, state["job_branch"], out=say)`).
   - For the merged job id (if not `None`; deduplicate if both return the same id), call `job.record_usage(root, "merge", jid, quiet=False)` so the 1-line usage summary prints at merge.
4. Keep the ledger untracked in `.git/shopsketch-usage.jsonl` (the default of `job_usage.py`); do not commit or add any export step.

What can fail (each gets a named check in `tools/test_job.py` / `tools/test_integrate.py`):
- `take`, `done`, `return`, and `merge` call the configured `SHOPSKETCH_USAGE_TOOL` stand-in with `--repo <tmp_root>`, `snapshot`, `--event <take|done|return|merge>`, `--job <id>`, `--agent`/`--session` on `take`, `--quiet` on `take`/`done`/`return`, and no `--quiet` on `merge`.
- Missing `SHOPSKETCH_USAGE_TOOL` path: `take`, `done`, `return`, and `merge` all succeed with no error.
- Failing `SHOPSKETCH_USAGE_TOOL` (exits 1 or raises): `take`, `done`, `return`, and `merge` all still succeed (fail-open).
- Existing `tools/test_job.py` and `tools/test_integrate.py` runs do not write to `/Users/Will/Sites/fretchup/.git/shopsketch-usage.jsonl` (because `--repo` points to their temp repo).

Reading path: `/Users/Will/Sites/job-usage/README.md` (Wiring Into the fretchup Workflow) → `tools/job.py` (`_take`, `done`, `return_job`, `merged`) → `tools/integrate.py` (`clean_up_job`) → `tools/test_job.py` and `tools/test_integrate.py`.

Run `python3 tools/test_job.py` and `python3 tools/test_integrate.py` while building, then `python3 tools/job.py test`. End your response with a `Result:` line; leftovers as `Follow-up:` lines; the `docs/integrator.md` note on `job_usage.py viz` / `report` as a `For the integrator:` line.

#### Response — Gemini (worker, gemini-maple-1123-2132), 2026-11-23

- Branch: `gemini/h124-usage-tracker-hooks`
- Commit: `cc7f3ef`
- What changed:
  - Added fail-open `record_usage(root, event, jid, agent=None, session=None, quiet=True)` to `tools/job.py` (reads `SHOPSKETCH_USAGE_TOOL`, defaults to `/Users/Will/Sites/job-usage/job_usage.py`, returns immediately if empty or missing, runs `snapshot` with `--repo <root>` and `timeout=5` inside `try / except Exception: pass`).
  - Wired `record_usage` outside the queue lock at the end of `_take` (`--event take --agent <agent> --session <session> --quiet`), `done` (`--event done --quiet`), and `return_job` (`--event return --quiet`).
  - Updated `tools/integrate.py` `clean_up_job` to capture and deduplicate the merged job ID(s) from `job.merged(...)` (both normal and `--job` scratch-branch merges) and call `job.record_usage(root, "merge", jid, quiet=False)`.
  - Added named unit checks in `tools/test_job.py` and `tools/test_integrate.py` covering all four events and arguments, temp-repo `--repo` isolation, missing/empty `SHOPSKETCH_USAGE_TOOL`, and fail-open behavior on non-zero exit and raised subprocess exceptions.
- Verified: `python3 tools/test_job.py` (166 passed, 0 failed), `python3 tools/test_integrate.py` (80 passed, 0 failed), and `python3 tools/job.py test` on `cc7f3ef` (all feature tests green, viewport QUICK 319 passed, 0 failed).
- IDs added: none.
- Open questions: none.

For the integrator: add a short note in `docs/integrator.md` on inspecting passive job usage in `.git/shopsketch-usage.jsonl` with `python3 /Users/Will/Sites/job-usage/job_usage.py viz` (visual dashboard, `--solo --sort burn`, `--job <H0NN>`) and `python3 /Users/Will/Sites/job-usage/job_usage.py report --only-measured` (tabular per-job usage; `compare`, `overhead`, and `holes <H0NN>` also available).
Result: cc7f3ef; job.py test passed (JOB TESTS 166/0, INTEGRATE TESTS 80/0, viewport QUICK 319/0); wired fail-open passive job-usage lifecycle hooks into job.py (take/done/return) and integrate.py (merge)
