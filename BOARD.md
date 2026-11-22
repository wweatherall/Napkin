# Work board

William says "check the board": this file tells each agent what to do next. The integrator (a Claude session in
/Users/Will/Sites/fretchup, P13) keeps it; nobody else edits it.

## If you're not the integrator

1. Read the board from main, not your worktree's copy: `git -C /Users/Will/Sites/fretchup show main:BOARD.md`.
2. Read "Notes" below for anything addressed to you (Claude or Codex) and do it.
3. Take the first job in "Jobs" that's for you, says **Ready**, and nobody has claimed. A job is claimed when a
   branch named after it exists: `git -C /Users/Will/Sites/fretchup branch -a | grep -i <id>` (e.g. h036). The
   branch is the truth even if the board still says Ready.
4. Claim it by making that branch: `git -C /Users/Will/Sites/fretchup worktree add ../fretchup-<id> -b <you>/<id>-<slug> main`
   (`<you>` is `claude` or `codex`, `<id>` lower case, e.g. `claude/h036-keys`). Then read the job's handoff file and do it.
5. When it's done (the handoff rules: tests, response, Status answered), tell William "ready for review: <ID>".
6. Nothing Ready for you? Say so and stop; don't start something that isn't on the board.

## If you're the integrator

Review every branch whose job says answered, merge what's good (P13), update the board and the Work list, then
write the next jobs so each agent has one Ready.

## Jobs

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H036 | Claude | **Ready** | T75: keyboard + measurements box out of viewport/main.gd | [H036](docs/handoff/H036-t75-keyboard-and-measurements-box.md) | |
| H034 | Codex | Claimed (codex/h034-scenario) | T76: worker/test_scenario.py split by feature | [H034](docs/handoff/H034-t76-split-worker-test-scenario-py.md) | |
| H035 | Codex | Claimed (codex/h035-protocol) | T44: docs/protocol.md | [H035](docs/handoff/H035-t44-write-the-window-worker-protocol.md) | |
| next | Codex | Queued | T54: plane fits re-fit only what changed (worker/plane_fit.py) | written when ready | H034 (adds scenario steps) |
| next | Claude | Queued | T70: a late worker reply can't replace a newer state | written when ready | H036 (main.gd) |
| next | either | Queued | T33: small distances (tools, inference) | written when ready | H036 |
| next | either | Queued | T66: units in the measurements box | written when ready | H036 |

## Notes

- Codex: read H030 and H032 (docs/handoff/) if you haven't, then archive them: `python3 tools/handoff.py archive H030`
  (and H032) on your current branch.
- Codex: main changed while H034/H035 were open: handoff entries are files in docs/handoff/ now (T77) and new IDs
  are placeholders (T74). Merge main into your branch before writing your response; if you already
  answered in docs/agent-handoff.md, leave it, the integrator moves it.
