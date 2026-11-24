### H134 — For the next integrator session: where things stand

Author: Gemini (integrator, gemini-cedar-1124-0011) | Date: 2026-11-24 | Status: open | For: the integrator

Touches: nothing (a note).

Archive, commit and push it in one step once read (`python3 tools/handoff.py archive H134 --push`).

- Orientation benchmark (`scratch/compare_orient.py`): `gemini-cedar-1124-0011` (post-T121) ran in **4 LLM calls, 70,987 total in (25,187 fresh), 2,237 out, 21,090 peak ctx** vs. `gemini-birch-1123-2348` (pre-T121: 11 calls, 265,694 total in, 28,832 peak ctx). William is re-running startup to benchmark permissions/prompt setup.
- Board is clean with no jobs in progress; **H125** (`T60`, chains of face ties) and **H128** (`T109`, mixed line/arc loops) are **Ready** and non-overlapping (queued behind them: H126→H127, H129→H130).
- Open for William's decision before writing briefs: **T63** (tied-face colour cue) and **T118** (3-Point Circle trigger).
- Untracked benchmark script stays in `scratch/compare_orient.py`.
