# Codex instructions for Shop Sketch

Read [CLAUDE.md](CLAUDE.md) for the shared development workflow, architecture overview and tests.
Its folder guides apply to Codex too. This file owns Codex-specific startup, isolation and delivery rules;
[ARCHITECTURE.md#documentation-ownership](ARCHITECTURE.md#documentation-ownership) routes other questions.

## At the start of every session

1. Read [docs/agent-handoff.md](docs/agent-handoff.md): its rules and the open list. Each open entry is its own
   file in docs/handoff/; read the Codex ones and their replies. Read the archive only for needed history.
2. Check `git log --oneline -15 main` and `git branch -a` for changes since the last session.
3. Search [docs/decision-log.md](docs/decision-log.md) by ID, e.g. `rg '^\| I34 ' docs/decision-log.md`;
   a row marked "(Details below.)" has its full text at `### <ID>`. Active decisions govern.

## Codex work and delivery

- A Claude session is the integrator (P13): take the job it assigned you in the handoff's Jobs section and
  deliver your branch to it for review. "Check the board" means: follow [BOARD.md](BOARD.md) (P14).
- Work on `codex/*` in your own worktree, never by switching branches in `/Users/Will/Sites/fretchup`:
  Claude uses that checkout. Start new jobs from main; touch the job's assigned files. William's direct
  instructions can authorize a wider scope. Merge into main or push only when William asks.
- Before starting, list the files you expect to touch in the job's handoff entry ("Touches: ...") and check
  the other open jobs' lists; if one overlaps, say so in chat before starting. Keep a job to one session;
  merge main into your branch at least once a day while it's open.
- Record every choice William makes, including names, labels, keys, defaults and wording, as its own
  decision row. Follow P01/P09 in the log. Merge main into your branch before editing the log, then
  change only rows your job adds or supersedes. New IDs are placeholders (I-new-N, T-new-N, H-new-N; a new
  entry is docs/handoff/H-new-N-slug.md): the integrator numbers them at merge (tools/number_ids.py, T74).
  List your placeholders in your handoff response.
- Follow CLAUDE.md for tests and architecture maintenance. Both agents own ARCHITECTURE.md; neither needs
  the other's permission to update it. Run commits with `git -c core.hooksPath=.githooks commit ...`.
  A specific `Architecture-Impact: none - <reason>` is only for genuinely non-architectural changes.
- Use P08's light path for small fixes, with Codex's standing branch `codex/small-fixes`.
  Otherwise record the result in the Work list and append a dated, signed response in the handoff:
  branch, commit, decision IDs, verification, architecture sections changed and anything open. Set the
  entry's Status; archive resolved exchanges with `python3 tools/handoff.py archive H0NN`.
- Behaviour choices are William's. Put unresolved questions in the handoff and mention them in chat.

Nothing notifies Claude automatically. Tell William which handoff entry and branch are ready for review,
so he can pass them on.
