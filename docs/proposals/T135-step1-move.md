# T135 step 1: move the repo under the Organization (plan, 2026-11-26)

The integrator's plan for P54–P59; for William to read before it starts. Nothing moves until he says go.

## Before
- Nothing in flight: H148 and H149 merged, `small-fixes` merged, the ultra review's findings taken (or the review
  paused). The other worktrees are `fretchup-small-fixes`, `fretchup-ultra-gemini` and
  `fretchup-agent-role-proposal`. Each one is either removed or moved with the repo (step C).
- Close every Shop Sketch window and every agent session except the integrator.

## A. The Organization skeleton (new, nothing moved yet)
- `~/Sites/Organization/` with `01_Principles`, `02_Habits`, `03_Past_Decisions`, `04_Personal_Space`, `05_Jobs`,
  `06_To-dos` (`waiting_on_William/`, `waiting_on_integrator/`), `07_Org_Chart_and_Roles`, `08_Code_Bases` (P55).
- `git init`; `.gitignore` holds `08_Code_Bases/*` (P58). The private GitHub repo is created when William gives
  its name (it is outward-facing).
- Seeded from `docs/proposals/organization-2026-11-25.md`: the org chart and roles go in 07, and William's principles
  go in 01, marked "not in force until T140". The rest start empty, each with a one-line README saying what goes there.
- `05_Jobs` gets one generated file per code base, written by a script in Napkin (`tools/`) that the commit hook
  runs on Napkin's main (P57). It is never edited by hand.

## B. The move
- `mv ~/Sites/fretchup ~/Sites/Organization/08_Code_Bases/Napkin`.
- Job worktrees: `job.py` makes them in `<checkout>-jobs/`, so they would become `08_Code_Bases/Napkin-jobs/`.
  That's a second folder in 08 that isn't a code base. Proposal: `job.py` uses `08_Code_Bases/.worktrees/Napkin/<id>`
  (hidden, one place for every code base). A question for William at the time.
- `git worktree repair` for every worktree that is kept.

## C. Re-point what names the old path
- In the repo: `AGENTS.md`, `BOARD.md`, `tools/startup.py`, `docs/integrator.md` (both launch commands),
  `tools/start_worker.sh` and `tools/usage.py` (`fretchup-jobs/`). Each is changed to work the path out from
  the checkout, so a later move needs no edits. Old paths in `.git/shopsketch-jobs.json` and the usage log are
  history and stay as they are.
- Outside the repo: Claude Code's memory folder (`~/.claude/projects/-Users-Will-Sites-fretchup/`) is copied to
  the new path's folder; Codex's trusted-project entry (`~/.codex/config.toml`); Gemini's `settings.json` if it names
  the path. The app's own data (`user://`, "Shop Sketch") doesn't depend on where the repo is.
- GitHub: renaming `wweatherall/fretchup` to `Napkin` is William's choice (GitHub redirects the old URL).

## D. The decision log (P59)
- `docs/decision-log.md` and `docs/decision-archive.md` move to `02_Past_Decisions/` unchanged. Everything that
  names them is updated in the same commit: `log.py`, `sort_decision_log.py`, `number_ids.py`, `integrate.py`,
  `startup.py`, the hook, the guides and their tests. That commit gets its own test run.
- The rest of `docs/` (board, handoff, specs, proposals, integrator guide) stays until a later step.

## E. Proof
- `tools/gate.sh` passes from the new place, and so does `startup.py --role integrator`. A dry job round trip on a
  throwaway entry (take, done, `integrate.py --dry-run` or a real small job) shows the worktree lands in the new
  place. Then `job.py watch --next`.
- William reopens Claude Code (and Codex or Gemini) from `~/Sites/Organization/08_Code_Bases/Napkin`. The
  integrator session that did the move ends, because its folder is gone, and a new one takes the lock.

## Later steps (not now)
The Process rows move to `Organization/03_Past_Decisions`; then one file per ruling (P59). After a day of use, the
code moves into `05_Code` (P56), and the rest of `docs/` moves into 03/04 and the org folders. Personal spaces,
habits and the start script follow (T134).
