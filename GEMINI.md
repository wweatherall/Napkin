# Gemini instructions for Shop Sketch

Follow [AGENTS.md](AGENTS.md) (written for Codex; every rule applies to you) with these differences:

- "Check the board": follow [BOARD.md](BOARD.md) with `--as gemini` (your branch: `gemini/<id>-<slug>`). Take
  only jobs whose For is `either` or `gemini`.
- No small fixes: anything outside your job goes in your response as a Follow-up line.
- Your session name for `job.py take --session`: `gemini-<a short word of your choice>`, the same for the whole
  session.
- Nothing notifies Claude or Codex: when your job is done (`python3 tools/job.py done`), tell William.
