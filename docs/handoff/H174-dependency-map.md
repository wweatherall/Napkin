### H174 — A generated dependency map: who uses which file, and who calls a function

Author: Claude (integrator, napkin-77) | Date: 2026-11-27 | Status: answered | For: gemini

References: William, 2026-11-27 (architecture order, step 2: "a generated dependency map, which also writes Touches
lines"), T136 (the current/proposed map: this is its "current" half), P36 (an architect plans from the map without
reading code), P45 (Touches names files and functions), comitatus principles C05 and C06.

Touches: tools/dependency_map.py (new), tools/test_dependency_map.py (new), docs/dependency-map.md (new, generated),
.githooks/pre-commit (one block), tools/README.md (one line).

Reading path:
1. tools/architecture_map.py (H165): how a generated file is built and checked (`--check`), the folders it scans.
2. How files use each other today: GDScript `preload("res://...")`, `load(...)`, `extends`, and `m.<name>` (main.gd's
   forwarders: viewport/CLAUDE.md explains them); Python `import x` / `from x import` inside worker/ and tools/.
3. docs/integrator.md's line "Grep callers before finalizing Touches".

Today (checked 2026-11-27): nothing lists which files depend on which. The integrator finds a function's callers by
grep when writing a brief's Touches line; a miss shows up later as a worker's scope question (H170, H171 and H173
each asked one or more).

Request:
1. **`python3 tools/dependency_map.py`** writes docs/dependency-map.md (generated; a don't-edit line at the top): one
   line per code file in viewport/, viewport/tools/, worker/ and tools/ (tests in a separate short section or left
   out; say which): `file — uses: a, b, c — used by: d, e`. Python from `ast` imports; GDScript from `preload`/
   `load`/`extends`/`class_name` references and the `res://` paths in each file. Short names where unambiguous.
   Aim under 8 KB; if it can't fit, say so and why.
2. **`python3 tools/dependency_map.py callers <file>:<function>`** prints every call site (`path:line`) of that
   function across the repo's code and tests, word-boundary matched, its definition left out; and
   **`... touches <file>:<function> [...]`** prints a ready Touches line: the files defining and calling those
   functions, each with the function names in backticks (P45's format), tests on their own. The integrator pastes
   it into a brief.
3. **Kept current:** the pre-commit hook rebuilds docs/dependency-map.md when a .gd or .py file under those folders
   is committed (as the module map is), and `--check` fails when it's stale. Fast: well under a second (quote it).
4. tools/README.md lists the script (the integrator updates docs/integrator.md's grep line after the merge).

Not in this job: the proposed/ghosted map (T136's other half), anything in ARCHITECTURE.md, call graphs inside a
file.

What can fail:
- A dependency missed because it goes through main.gd's `m.` forwarders (a tool calls `m.selection`, which is
  selection.gd): resolve each forwarder to its file where main.gd's forwarder says which; say in the response which
  patterns you resolve and which you can't.
- A false caller from a common word (`apply`, `sync`): `callers` takes `<file>:<function>` and, for a method name used
  by several files, says how many definitions share it rather than guessing.
- The hook slowing every commit: it runs only when code files are staged.

Checks:
- tools/test_dependency_map.py on throwaway files (Python import, GDScript preload, an `m.` forwarder, a common name).
- On the real repo, quote `callers viewport/document.gd:next_id` and `touches worker/plane_fit.py:apply`, and compare
  each with a grep: anything grep finds that the tool misses is a bug.
- `tools/TEST_BEFORE_MERGING.sh` passes (scope tools).

**Response (Gemini, gemini-teak-1127-0954, 2026-11-27):**

Branch: `gemini/h174-dependency-map` | Commit: `a185f1c`

- **Generated map (`docs/dependency-map.md`)**: 7,419 bytes (under 8 KB). Covers non-test `.gd` and `.py` files in `viewport/`, `viewport/tools/`, `worker/`, and `tools/` (tests are excluded from the map and included by `callers`/`touches`). Short names used where unique across those folders.
- **`--check` speed**: `0.247s` total (`python3 tools/dependency_map.py --check`).
- **`m.` forwarder resolution in `viewport/main.gd`**:
  - Resolved: `const Alias := preload/load("res://...")`, `var x [: Alias] = Alias.new(...)` / `load("res://...").new(...)`, property forwarders (`var prop: ...` with `get: return subobj.<member>`), and one-line function forwarders (`[static] func fn(...): [return] subobj.<other>(...)` or `Alias.<other>(...)`).
  - Not resolved: properties assigned onto `m` from outside `main.gd` (e.g., `m.properties_panel = load("res://property_panel.gd").new()` in `ui.gd`), dynamic `call()`/`get()`, and `main.gd`'s own methods/fields (`m.test_mode`, `m.set_tool`, `m.sync`, etc.).
- **Checks**:
  - `python3 tools/test_dependency_map.py`: `DEPENDENCY MAP TESTS: 17 passed, 0 failed`.
  - `python3 tools/TEST_BEFORE_MERGING.sh`: `GATE PASS (scope tools): tools quick test passes; 115 s total`.
  - `callers viewport/document.gd:next_id` vs `rg -n "\bnext_id\b" viewport/ worker/ tools/`: matched all 42 code/test occurrences (leaving out `viewport/document.gd:500`'s `func next_id` definition) and noted the 4 defining files (`tools/log.py`, `viewport/document.gd`, `viewport/test_selection.gd`, `viewport/tool_context.gd`).
  - `touches worker/plane_fit.py:apply` vs `rg -n "\bapply\b" viewport/ worker/ tools/`: matched all defining/calling code and test files, noted the 8 files defining `apply`, and printed:
    - `Touches: worker/plane_fit.py (\`apply\`), tools/integrate.py (\`apply\`), tools/launch.py (\`apply\`), tools/number_ids.py (\`apply\`), viewport/appearance.gd (\`apply\`), viewport/keys.gd (\`apply\`), viewport/main.gd (\`apply\`), viewport/measure_box.gd (\`apply\`), viewport/property_panel.gd (\`apply\`), viewport/tool_context.gd (\`apply\`), viewport/tools/paint_tool.gd (\`apply\`), viewport/tools/rect_tool.gd (\`apply\`), worker/model.py (\`apply\`), worker/object_properties.py (\`apply\`), worker/push.py (\`apply\`), worker/session.py (\`apply\`)`
    - `Tests: tools/test_log_archive.py (\`apply\`), tools/test_number_ids.py (\`apply\`), viewport/test_tool_context.gd (\`apply\`), viewport/test_units.gd (\`apply\`), worker/test_floor_copy.py (\`apply\`), worker/test_native.py (\`apply\`)`

Result: done. Ready for integrator review.
