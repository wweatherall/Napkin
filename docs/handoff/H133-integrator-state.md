### H133 — For the next integrator session: where things stand

Author: Gemini (integrator, gemini-birch-1123-2348) | Date: 2026-11-24 | Status: open | For: the integrator

Touches: nothing (a note).

Archive, commit and push it in one step once read (`python3 tools/handoff.py archive H133 --push`).

- Landed this session: **T121** (`ec62125`) — one-step `tools/handoff.py archive <ID> [--commit | --push]` with sandbox-safe preflight checks (staged/dirty/branch/`.git`-writable before mutating files), plus `tools/startup.py` briefing cues so orientation skips redundant reads and extra git round-trips.
- Board is clean with no jobs in progress; **H125** (`T60`, chains of face ties) and **H128** (`T109`, mixed line/arc loops) are **Ready** and non-overlapping (queued behind them: H126→H127, H129→H130).
- Open for William's decision before writing briefs: **T63** (tied-face colour cue) and **T118** (3-Point Circle trigger).
- Orientation benchmark script is in untracked `scratch/compare_orient.py` (compare this session's orientation tokens against `gemini-birch-1123-2348`: 11 calls, 265,694 total in, 28,832 peak ctx).
