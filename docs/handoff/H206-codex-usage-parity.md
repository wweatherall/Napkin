### H206 — Codex usage at parity: every view of the token tool shows Codex beside Claude and Gemini

Author: Claude (integrator, opus-integrator) | Date: 2026-11-27 | Status: open | For: codex

References: William, 2026-11-27 ("I would like Codex data at parity with Claude and Gemini"), H195 (Codex's quota windows
and job tokens from its session rollouts: `load_codex_sessions`, `find_codex_session`, the `codex-5h` /
`codex-weekly` buckets), H190 (the Log view), H162 (the two-repo pattern: a Napkin branch and a comitatus branch), P73.

Touches: docs/integrator.md (the "Passive job usage" paragraph: one sentence saying every view covers all three agents).

Also in the comitatus repo (not in Touches: the check reads Napkin paths): 09_Tools/MEASURE_TOKEN_USE.py,
09_Tools/SHOW_WHAT_EACH_STEP_COST.py, 09_Tools/test_measure_token_use.py, 09_Tools/README.md (its lines, if they name
only Claude and Gemini).

Reading path:
1. `grep -n -i -E "gemini|agy|claude" 09_Tools/MEASURE_TOKEN_USE.py`: each place that handles the two older agents
   and not Codex. Today (checked 2026-11-27) these include `viz` (agent tags `gem` / `cld` only), `overhead` (Claude
   and Gemini sections only), `orient --agent` (choices claude, gemini), the transcript scan at `for provider,
   base_dir in (("claude", ...), ("gemini", ...))`, and `log` / SHOW_WHAT_EACH_STEP_COST.py, whose totals line reads
   `claude: ... | gemini: ...` with no Codex column (`SHOW_WHAT_EACH_STEP_COST.py codex-coder` prints "no data").
2. H195's Codex readers: what Codex's rollouts hold (cumulative token counts, both quota windows, no context-size
   figure) and what they don't.

Request:
1. Every subcommand that reports per agent (report, overhead, compare, orient, bench, export, viz, log) covers Codex
   the way it covers Claude and Gemini, from H195's readers: its own tag and colour in `viz` (not cyan or magenta,
   which the others use), its section in `overhead`, `codex` in `--agent` choices, its column in the `log` totals.
2. Where Codex's rollouts lack a figure the others have (for example peak context), show `-` and say so once in the
   command's help, rather than guessing.
3. `SHOW_WHAT_EACH_STEP_COST.py codex-coder` shows Codex's quota used between its Log lines, like the other members.
4. Tests: each subcommand's output includes Codex from a synthetic rollout (H195's fixtures), and a view with no Codex
   data still runs.

Not in this job: reading Codex's live quota outside sessions (Codex's own `/status` shows it), the Gemini or Claude readers.

Checks:
- `python3 09_Tools/test_measure_token_use.py` passes in the comitatus repo; `tools/TEST_BEFORE_MERGING.sh` passes
  (docs scope) in Napkin.
