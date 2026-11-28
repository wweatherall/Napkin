### H195 — Codex in the token tool: its quota windows and each job's tokens, from Codex's own session logs

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: answered | For: codex

References: William, 2026-11-27 (ChatGPT's notes on Codex usage: "add Codex to your existing MEASURE_TOKEN_USE.py";
GPT 6.2 Sol as a coder), H190 (`log` and the two-repo pattern), H162, T117/T126 (passive job usage), P69, P73.

Touches: docs/integrator.md (the "Passive job usage" paragraph: one sentence naming Codex).

Also in the comitatus repo (not in Touches: the check reads Napkin paths): 09_Tools/MEASURE_TOKEN_USE.py,
09_Tools/test_measure_token_use.py, 09_Tools/README.md (its MEASURE_TOKEN_USE line).

Reading path:
1. comitatus/09_Tools/MEASURE_TOKEN_USE.py: `PROVIDER_BUCKETS`, `load_quota_history` (each provider's history as
   `(ts_sec, {bucket: remaining_fraction})`), `compute_quota_deltas` (resets and glitches), `build_job_record` (a
   job's quota change and session tokens), `cmd_log` (H190), and how Gemini's per-job tokens come from its transcripts
   (`summarize_agy_session`).
2. A Codex session log, `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` (read only): the first line is `session_meta`
   (`payload.id`, `payload.cwd`); `event_msg` lines with `payload.type == "token_count"` carry a top-level
   `timestamp`, `payload.info.total_token_usage` (cumulative: `input_tokens`, `cached_input_tokens`, `output_tokens`,
   `reasoning_output_tokens`, `total_tokens`) and `payload.rate_limits` (`primary` / `secondary`: `used_percent`,
   `window_minutes` 300 and 10080, `resets_at` in seconds).
3. Napkin's .git/shopsketch-jobs.json: a Codex job's `taken`, `done` and `worktree`.

Today (checked 2026-11-27): the tool reads Claude's and Gemini's quota monitors and transcripts; Codex jobs get no
quota or token figures, though Codex writes both into its session logs.

Request:
1. **Codex quota as a provider**: `PROVIDER_BUCKETS["codex"] = ("codex-5h", "codex-weekly")`; `load_quota_history`
   also builds Codex's samples from every session log's `rate_limits` (primary → `codex-5h`, secondary →
   `codex-weekly`, by `window_minutes`, as remaining fractions `1 - used_percent / 100`), sorted, duplicates dropped,
   so `compute_quota_deltas`, `report`, `bench` and `log` treat it like the others with no special cases.
   `--codex-dir` (default `~/.codex/sessions`) overrides where it reads.
2. **A Codex job's tokens**: the session whose `session_meta.cwd` is the job's worktree (or inside it) and whose
   events fall between `taken` and `done`; tokens = the last `total_token_usage` before `done` minus the last before
   `taken` (0 if none before), never a sum of the cumulative snapshots, which would count earlier work again. Report
   input, cached input, output and reasoning the same way. No session found: the job shows `-` for tokens, not 0.
3. Concurrency as for the others: a Codex quota change while another Codex session ran is labelled shared.
4. `log` (H190) shows a `codex: 5h ... weekly ...` group when Codex samples exist in the stretch.
5. Tests with synthetic session logs: a job's token delta from cumulative snapshots (with earlier work before
   `taken`), a window reset inside a job, a job with no matching session, and the quota samples feeding `log`.
6. Two branches as H162/H190, with one difference so your sandbox can write it: make the comitatus worktree inside
   the folder you were given, `git -C /Users/Will/Sites/comitatus worktree add
   /Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/Napkin/h195-comitatus -b codex/h195-codex-usage`. Don't commit
   in comitatus's main checkout; name both branches and commits in your response.

Not in this job: ChatGPT's own conversation usage (`account/usage/read`), the app server, changing Codex's settings,
or the Napkin launcher.

Checks:
- `tools/TEST_BEFORE_MERGING.sh` passes; `python3 ../../09_Tools/test_measure_token_use.py` passes.
- `python3 ../../09_Tools/MEASURE_TOKEN_USE.py report --all-agents` shows this job (H195) with Codex tokens and a
  `codex-5h` change once it is done (say what it showed).

Response — Codex (codex-coder), 2026-11-27:

- Napkin branch `codex/h195-codex-usage`, documentation commit `48f6bb4`. Comitatus branch `codex/h195-codex-usage`, tool and tests commit `3ef11f8`.
- Synthetic rollouts verify cumulative token subtraction, both quota windows, a 5-hour reset, missing sessions, overlap, and the Codex group in `log`. All 22 token-tool tests passed. The Napkin merge gate and the recorded quick test passed at tools scope.
- A preview from H195's live session logs found both quota windows and marked the interval shared. The submission hook will record the completed interval using the updated tool.

Changed from the brief: match the job's worktree or a directory inside it first, then use the queue's exact session ID if no worktree matches. The launcher starts in the main checkout before the worktree exists, as it did for H195.

Architecture: `09_Tools/MEASURE_TOKEN_USE.py` reads Codex rollout metadata, quota samples, and cumulative token counters for the existing passive job usage ledger.

For the integrator: review Comitatus `3ef11f8` as well as the Napkin branch. The passive hook uses the live Comitatus tool after that branch is merged.

Result: 48f6bb4; Napkin merge gate and quick test passed, 22 Comitatus tests passed; Codex quota and per-job token accounting in Comitatus 3ef11f8.
