# Instructions for Codex (and other agents) working on Shop Sketch

Claude also works on this repo; CLAUDE.md is its instruction file and the fullest description of how the app works.
Read it for architecture, conventions and tests.

## At the start of every session

1. Read `docs/agent-handoff.md`, the shared scratchpad between Claude and Codex. It contains open entries only;
   resolved ones are in `docs/handoff-archive.md` (read only when you need history). Look for entries marked
   "For: Codex", and for replies to your entries.
2. Check what changed since your last session: `git log --oneline -15 main`, and `git branch -a` (Claude works on
   feature branches; your work lives on `codex/*` branches).
3. Decisions: `docs/decision-log.md` is William's decision log (P09). Active decisions win over suggestions.
   Search it by ID (`grep "^| I34 "`; "(Details below.)" means the full text is at `### I34`) rather than reading it whole. Record a decision William makes in your chat
   there, in the commit it belongs to, following P01 (a new row naming the old ID; the old row Superseded).

## How to work

- Each part has a short guide: `worker/CLAUDE.md`, `viewport/CLAUDE.md`, `viewport/tools/CLAUDE.md` (what it
  owns, its rules, its tests). They apply to you too: read the one for the folder your job touches.

- Work in your own git worktree, never by switching branches in /Users/Will/Sites/fretchup (Claude works in that
  checkout). Example: `git worktree add ../fretchup-codex-<job> -b codex/<job> main`.
- Touch only the files your handoff job lists. Don't merge into main or push unless William says so.
- Claude and Codex both own and may edit `ARCHITECTURE.md`. The agent changing architecture updates it in the
  same commit, in its own worktree, without seeking permission from the other agent. Reread the shared map
  and instructions before committing. The reviewing agent checks it against the code; integration preserves
  both agents' unrelated edits and distinguishes delivered branches from integrated code. Mention it in the handoff.
- Use the tracked commit check: `git -c core.hooksPath=.githooks commit ...`. It flags production-module,
  protocol/state and packaging changes without a staged architecture update. For changes which truly have no
  architectural impact, include `Architecture-Impact: none - <specific reason>` in the commit message;
  the reviewer must verify that claim. This never exempts an actual architecture change from the same-commit rule.
- While building a FreeCAD-side feature, run `tools/featuretest.sh` (~5 s, no window; add steps to
  `worker/test_scenario.py`). Before handing back, run `tools/quicktest.sh` in your worktree (it uses its own ports).
- Report in the handoff: append a dated, signed response under the entry, with your branch, commit, what you
  verified and what's open. Then set its Status. Archive entries once they're resolved (move them whole to
  handoff-archive.md and leave a one-line index under "Archived").
- Small fixes take the light path (P08 in the log): nothing William would notice changes, no protocol, file
  format, module boundary or saving is touched, and it's ~30 lines or less. Commit it on `codex/small-fixes`
  after the quick test (code: `Architecture-Impact: none - <reason>`), with no handoff entry or Work list row; list the fixes for
  William in your chat. If a fix grows past that, ask for a handoff job instead.
- Behaviour choices are William's: put questions to him in the handoff, and say them in your chat with him too.

## Nothing notifies the other agent

File changes don't reach Claude by themselves. When you finish a job or leave a question, tell William in your
chat, e.g. "H006 is answered in the handoff, on branch codex/t32-units, for Claude to review", so he can pass
it on.
