### H131 — For the next integrator session: where things stand

Author: Gemini (integrator, gemini-cedar-1123-1844) | Date: 2026-11-23 | Status: open | For: the integrator

Touches: nothing (a note).

Archive it once read (`python3 tools/handoff.py archive H131`).

Paused before hitting the 5-hour quota limit (P48 trial; main is tagged `before-gemini-integrator`). After `/clear`:
`python3 tools/integrator.py take <your session> --william`, then re-arm the queue watch
(`python3 -u tools/job.py watch --next` in the background).

Merged and pushed this session (5 jobs, all green gates with 0 known failures):
- **H097** (`T110=Done`): failure-path test helpers (`worker/test_link.py`, `viewport/test_document.gd`); folder guides updated (`worker/CLAUDE.md`, `viewport/CLAUDE.md`).
- **H123** (`T116=Done`): folder-prefixed `featuretest.sh` logs, `DEFAULT_UNIT` in `tools/length_cases.py`, response-scoped `integrate.py` parsers, 3 follow-ups cleared.
- **H122** (`T113 step 5`): 17 compatibility aliases removed from `viewport/main.gd`, `ARCHITECTURE.md` updated, 5 follow-ups (H107, H110, H111, H112, H113) cleared in `docs/follow-ups.md`, `viewport/CLAUDE.md` updated.
- **H109** (`T113=Done`): rejection bookkeeping moved to `viewport/document.gd` with 8 headless tests, 6 document pass-throughs removed (`viewport/main.gd` now 1,253 lines, down from ~2,130), `ARCHITECTURE.md` and `viewport/CLAUDE.md` updated.
- **H124** (`T117=Done`): fail-open passive `job-usage` lifecycle hooks in `tools/job.py` (`take`/`done`/`return`) and `tools/integrate.py` (`merge`), passing `--repo <root>` so temp-repo tests never pollute `.git/shopsketch-usage.jsonl`; `docs/integrator.md` updated with `viz` / `report` commands.

Other commits on `main` this session:
- Archived `H118` (`9278603`).
- Marked previously merged Work list items `T102`–`T106`, `T114`, `T115` as `Done` (`f2da573`).
- Documented Gemini worker launch command (`osascript` + `agy --model gemini-4-neon-medium -i "Gemini go! Check the board."`) in `docs/integrator.md`, and changed `BOARD.md:27`'s prose example to `T-new-N` (`5a87f9a`).
- Logged **I64** (`R` again toggles Rotated Rectangle; Polygon as a toolbar button with no hotkey yet, exact FreeCAD sketch polygon), **Q33** (Polygon shortcut key for later), **T117** (usage tracker hooks, Done), and **T118** (3-Point Circle).

Where the board stands (working tree clean, no jobs in progress):
- **Ready** (non-overlapping; ready to spin up workers on William's word):
  - **H125** (`T60`, chains of face ties; bumps `PROTOCOL_VERSION` 12 → 13 for `stock_frame.fitted_end`).
  - **H128** (`T109`, closed loops of mixed lines & arcs forming pushable faces with exact FreeCAD arcs).
- **Queued** (stubs — recheck against `main` and expand before opening when each blocker merges):
  - **H126** (`T61`, after H125), **H127** (`T62`, after H126).
  - **H129** (`T84` step 1: Rotated Rectangle, after H128), **H130** (`T84` step 2: Polygon tool, after H129).
- **Open for William's answer**:
  - **T63** (colour cue for tied faces): recommendation posed in chat (subtle teal/cyan tint on tied end + target on hover/select, shifting to amber when non-overlapping, no warning). Log decision and write brief once settled.
  - **T118** (3-Point Circle): on the Work list; confirm trigger (`C` again toggle like `R`/`A`) before writing brief.
- **Standing reminders**:
  - `H067` still open (`handoff.py check` flags `communication/design`); leave until it closes.
  - Small fixes this session: none on `small-fixes` branch.
  - Note: `~/.gemini/antigravity-cli/settings.json` now has `unsandboxed(...)` allow rules for `job.py`, `integrator.py`, `integrate.py`, `startup.py`, and single git commands (`add`, `commit`, `merge`, `push`) — keep those commands unchained (no `&&`) so they auto-approve cleanly.
