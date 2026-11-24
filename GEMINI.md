# Gemini instructions for Shop Sketch

Follow [AGENTS.md](AGENTS.md) (written for Codex; every rule applies to you) with these differences:

- "Check the board": follow [BOARD.md](BOARD.md) with `--as gemini` (your branch: `gemini/<id>-<slug>`). Take
  only jobs whose For is `either` or `gemini`.
- No small fixes: anything outside your job goes in your response as a Follow-up line.
- Taking a job: run `python3 tools/job.py take --as gemini` with no `--session` flag — `job.py` automatically uses
  `ANTIGRAVITY_CONVERSATION_ID` (collision-proof for parallel workers). Only in environments without
  `ANTIGRAVITY_CONVERSATION_ID` (or for `integrator.py take`), pass a manual session name like
  `gemini-<a short word>-<MMDD-HHMM>` (e.g. `gemini-juniper-1123-0705`), the same for the whole session.
- Nothing notifies Claude or Codex: when your job is done (`python3 tools/job.py done`), tell William.
- Follow [AGENTS.md](AGENTS.md) when asking a question. Use `job.py wait --scope` for the integrator and
  plain `job.py wait` for William. Run either in the background and quote the answer in your response.
