### H030 — Tools share one press rule now (T57): what changed for Codex

Author: Claude | Date: 2026-11-21 | Status: open (for Codex to read, then archive)

References: I43 (replaces I29), I44, I45, T57; viewport/tools/tool.gd, viewport/tools/CLAUDE.md, ARCHITECTURE.md (module table: tool.gd, inference.gd rows); merge cb09ad7.

Finding: (1) Rectangle, Push/Pull and Move decide press-and-drag versus click-and-click with one rule in `tool.gd`: a tool that starts on a press calls `press_started(screen)`, `press_moved(screen)` on every move, and in `release` asks `press_released()` (`drag` true = finish now). A new tool that starts on a press uses these rather than its own thresholds; the interface is in the tools guide. (2) `inference.gd` has `on_grid(p)` (the grid step of `snap` without point snaps). (3) New quick section `tests/quick/press.gd` (lane 2).
