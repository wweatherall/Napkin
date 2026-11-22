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

You're the integrator only if William said so in this session (P13); a fresh session is a worker. Review every
branch whose job says answered, merge what's good, update the board and the Work list, then write the next jobs
so each agent has one Ready.

## Jobs

| Job | For | Status | Item | Handoff | Waits for |
|---|---|---|---|---|---|
| H036 | Claude | **Ready** | T75: keyboard + measurements box out of viewport/main.gd | [H036](docs/handoff/H036-t75-keyboard-and-measurements-box.md) | |
| H037 | Codex | **Ready** | T54: plane fits re-fit only what changed (worker) | [H037](docs/handoff/H037-t54-plane-fits-refit-only-changed.md) | |
| H038 | Codex | **Ready** | T78: a drawing request during a sync is lost (viewport/document.gd) | [H038](docs/handoff/H038-t78-drawing-request-lost-during-sync.md) | |
| next | Claude | Queued | T70: a late worker reply can't replace a newer state (incl. stale open replies) | written when ready | H036 (main.gd), H038 (document.gd) |
| next | either | Queued | T79: a failed save is forgotten; shutdown waits on a saved revision | written when ready | H036 (main.gd shutdown) |
| next | either | Queued | T33: small distances (tools, inference) | written when ready | H036 |
| next | either | Queued | T66: units in the measurements box | written when ready | H036 |

Done since the board started: H034 (T76), H035 (T44), H033 (T74 + T77).

## Notes

- Codex: two jobs are Ready (H037, H038); they touch different files, so two Codex sessions can take one each.
