# Codex instructions for Shop Sketch

Read [CLAUDE.md](CLAUDE.md) for the shared workflow (its "Working with William" and "Working with Codex"
sections), the architecture overview and tests; its folder guides apply to Codex too. [BOARD.md](BOARD.md) says
how to take, run and finish a job. This file owns what is Codex's only;
[ARCHITECTURE.md#documentation-ownership](ARCHITECTURE.md#documentation-ownership) routes other questions.

## At the start of every session

1. Run `python3 tools/startup.py` first (add a Work list ID, e.g. `T54`, for its row and the decisions it cites).
   Then read [docs/agent-handoff.md](docs/agent-handoff.md) and the open entries for Codex in docs/handoff/.
2. Check `git log --oneline -15 main` and `git branch -a` for changes since the last session.
3. Read the decision log as CLAUDE.md says (its top down to `## Decisions`, then `python3 tools/log.py show
   <subject>` or `show <ID>`; add rows with `python3 tools/log.py add <kind> "<text>"`, no arguments for its usage).
   Active decisions govern.

## Codex work and delivery

- "Check the board" means: follow BOARD.md (P14), with `python3 tools/job.py take --as codex`; your branch is
  `codex/<id>-<slug>`. Nothing Ready and you can't wait in the background: say so and stop.
- Work only in the job's worktree, never by switching branches in `/Users/Will/Sites/fretchup`: Claude uses that
  checkout. Touch the job's Touches files; William's direct instructions can authorize a wider scope. Merge into
  main or push only when William asks. Keep a job to one session; merge main into your branch at least once a
  day while it's open.
- Record every choice William makes, including names, labels, keys, defaults and wording, as its own
  decision row (P01/P09). Merge main into your branch before editing the log. List your placeholder IDs in your
  handoff response.
- Date and sign your response; it also gives the decision IDs, the verification and the `Architecture:`
  lines (P28). Set the entry's Status; archive resolved exchanges with `python3 tools/handoff.py archive H0NN`.
- Use P22's light path for small fixes with Codex's standing branch `codex/small-fixes`; the integrator merges
  and pushes it when the gate passes.
- Behaviour choices are William's. Put unresolved questions in the handoff and mention them in chat.

Nothing notifies Claude automatically. Tell William which handoff entry and branch are ready for review,
so he can pass them on.
