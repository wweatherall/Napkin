# Codex instructions for Shop Sketch

[CLAUDE.md](CLAUDE.md) describes the project; its folder guides apply to you too. Other questions:
[ARCHITECTURE.md#documentation-ownership](ARCHITECTURE.md#documentation-ownership).

- Start every session with `python3 tools/startup.py` (add a Work list ID, e.g. `T54`, for its row).
- "Check the board": follow [BOARD.md](BOARD.md) with `--as codex` (your branch: `codex/<id>-<slug>`). Nothing
  Ready and you can't wait in the background: say so and stop.
- Work only in the job's worktree; never switch branches in /Users/Will/Sites/fretchup (Claude's). Merge main into
  an open job's branch at least daily. Merge into main or push only when William asks.
- A brief's rule that, followed to the letter, would defeat its purpose: do what serves it and add a
  `Changed from the brief:` line to your response (BOARD.md step 3, P44); not for behaviour, which is William's (next line).
- Behaviour choices are William's: ask, one question at a time, with a recommendation. Log each answer (names,
  keys, defaults and wording too) as its own row, `python3 tools/log.py add` (P01, P09). Active decisions govern.
- For permission to touch a file or function outside Touches, ask the integrator with
  `python3 tools/job.py wait --scope "<question>"`. For behaviour, wording or what is saved, ask William in chat and run
  `python3 tools/job.py wait "<question>"`. Run either command in the background. After a timeout, run the
  same command again. Quote the queue's answer in the handoff response.
- Commit with `git -c core.hooksPath=.githooks commit`; watched code needs `Architecture-Impact: in the handoff -
  H0NN` or `Architecture-Impact: none - <specific reason>`.
- Scratch files and logs go in `scratch/` inside your worktree, never /private/tmp (P25).
- Small fixes: CLAUDE.md's light path (P22), on `codex/small-fixes`.
- Handoff entries: [docs/agent-handoff.md](docs/agent-handoff.md). Nothing notifies Claude: tell William what's
  ready for review.
