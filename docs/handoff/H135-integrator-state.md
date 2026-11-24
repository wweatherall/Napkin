### H135 — For the next integrator session: where things stand

Author: Gemini (integrator, gemini-maple-1124-0028) | Date: 2026-11-24 | Status: open | For: the integrator

Touches: nothing (a note).

Take the lock and archive, commit and push this note in one step once read (`python3 tools/integrator.py take <session> --william --archive H135 --push`, outside sandbox / `BypassSandbox: true`).

- Orientation small fix (`168e443`, pushed to `main`): added `integrator.py take ... --archive <ID> --push`, updated `startup.py --role integrator` to emit the combined command + `BypassSandbox: true` cue, and added the lean Turn-1 rule to `AGENTS.md` / `docs/integrator.md` (skip `CLAUDE.md` and `BOARD.md` upfront).
- Orientation benchmark (`scratch/compare_orient.py`): `gemini-cedar-1124-0011` = **4 calls, 70,987 total in, 21,090 peak ctx**; `gemini-maple-1124-0028` = **6 calls, 127,609 total in, 24,333 peak ctx** (serialized `take`→`archive` sandbox retries + read `CLAUDE.md`/`BOARD.md`). William is re-running startup to benchmark `168e443` + updated permissions.
- Board is clean with no jobs in progress; **H125** (`T60`, chains of face ties) and **H128** (`T109`, mixed line/arc loops) are **Ready** and non-overlapping (queued behind them: H126→H127, H129→H130).
- Open for William's decision before writing briefs: **T63** (tied-face colour cue) and **T118** (3-Point Circle trigger).
- Untracked benchmark script stays in `scratch/compare_orient.py`.
