### H216 — Reading cost per job: what each agent read before and while doing its job, from the saved transcripts (T175)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: open | For: Codex | Item: T175

References: T175 (ChatGPT's review, 2026-11-28: tell "better documentation" — agents find what they need faster —
from "better architecture" — they need less in the first place); William, 2026-11-28: "put it on the board"; T117 (the
usage ledger); `comitatus/09_Tools/MEASURE_TOKEN_USE.py` (`holes`, `discover_transcript`, `analyze_transcript`,
`list_agy_transcripts`, `load_codex_sessions`); C06, C07.

Today: `MEASURE_TOKEN_USE.py holes <job>` finds a job's transcript from the ledger (`.git/shopsketch-usage.jsonl`,
`latest_records_by_job`; `backfill` fills it) through `discover_transcript`, which knows Claude
(`~/.claude/projects/**/<session>.jsonl`) and Gemini (`~/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/
transcript.jsonl`) but not Codex (`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, `load_codex_sessions` reads their
token and quota events only). `analyze_transcript` gives phases, token totals and the biggest tool outputs; nothing counts
what was read. On hand (2026-11-28): the project started 2026-11-20; about 130 Gemini and 120 Codex transcripts, about
12 Claude ones (older Claude ones are gone); 211 archived jobs in `docs/handoff-archive.md`. The script lives in the
comitatus repository, outside this repo's job branches, so the new code goes in this repo's tools/ and imports it (as
`tools/job.py` `_usage_tool` finds it); moving it into comitatus later is a separate step.

Touches: tools/reading_cost.py (new), tools/test_reading_cost.py (new), tests/reading_cost.json (new, generated).
The integrator adds its line to the tools README at merge.

Request:
1. For one job, find its transcript for any of the three agents (reuse `discover_transcript` for Claude and Gemini; add
   Codex by the session id the ledger or the job queue (`.git/napkin-jobs.json` entry `session`) records, matching the
   rollout's `session_meta` id) and measure, from its tool calls:
   - source files read (distinct paths, repo-relative, worktree prefix stripped so `.worktrees/Napkin/h214/tools/x.py`
     and `tools/x.py` are one file), split into code, tests, docs (`*.md`, `03_Past_Decisions/`) and other;
   - lines read: unique (file, line) pairs and repeated ones (the same lines read again), from the ranges each read
     asked for (a whole-file read counts the file's line count at the job's merge commit, or now if that's gone);
     searches (`grep`, `rg`) count their output lines as read, kept separate;
   - tokens before the first edit (the first file write or edit tool call), and total;
   - files the job changed (from its merge commit: `git show --stat`), and lines changed.
   Agents call their tools differently (Claude `Read`/`Edit`/`Bash`, Gemini `read_file`/`run_command`, Codex
   `exec_command`/`apply_patch`, shell `cat`/`sed -n`/`head`): map each to "read a range", "search", "edit" or "other"
   in one table at the top of the file, so a new tool name is one line.
2. `python3 tools/reading_cost.py --all` measures every archived job it can find a transcript for and writes
   `tests/reading_cost.json`: per job, its agent, model, merge date, kind and the numbers above. Kind: from the files
   changed (worker op, viewport tool, tools/process, docs only, mixed), so like is compared with like. A job with no
   transcript is listed with the reason, not left out silently.
3. `--report` prints, for each kind, the jobs in date order with their numbers and a median per day, so a trend (or none)
   shows; and flags the jobs that read the most docs relative to code (documentation doing the work) or the most code per
   line changed (architecture making them read). Say in your response what the numbers show and how far to trust them.
4. Read-only on the transcripts: never write into `~/.claude`, `~/.gemini` or `~/.codex`.

What can fail:
- A job ran in more than one session (returned and resumed, or stacked): count every session the queue recorded for
  it, and say so in its row.
- A Gemini transcript holds two jobs (a worker that took a second job): split at the second `GET_A_JOB` call and say so.

Checks:
- `tools/test_reading_cost.py` (summary line `READING COST TESTS: N passed, M failed`): a small fake transcript of each of
  the three formats gives the expected files, unique and repeated lines, tokens before the first edit; a worktree path
  and a repo path count as one file; an unknown tool name counts as "other", not an error.
- Run it for real, commit `tests/reading_cost.json`, paste the report into your response.
- `tools/TEST_BEFORE_MERGING.sh` passes.
