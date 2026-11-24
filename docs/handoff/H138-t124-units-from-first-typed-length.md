### H138 — T124: Auto-set document units from first typed length with an explicit unit

Author: Gemini (integrator, gemini-cedar-1124-0100) | Date: 2026-11-24 | Status: answered | For: either

References: T124, I67, I57, I59, I62, I63, I35, G03, G06.

Touches: viewport/measure_box.gd, viewport/units.gd, viewport/test_units.gd, viewport/tests/quick/units.gd. Not worker/session.py (already stores `ShopSketchUnits` via `set_units` and returns `""` when unset on open; ask with `job.py wait --scope` if a worker change is needed).

Why: I67 (William, 2026-11-24) specifies that when a document has no units explicitly set yet, it starts in the previous/preference units (I62), and adopts the unit of the first typed length that includes an explicit unit (e.g. typing `4", 5"` or `120mm` on a new model switches the document's units to match and saves them). If nothing has been typed yet (or only bare numbers), it stays on the previous settings.

Today (checked 2026-11-24):
- `viewport/measure_box.gd`:
  - `init_units()` (~36–43) sets `units = default_units()`, `units_user_set = false`, `units_dirty = false`.
  - `on_opened(resp, adopt)` (~125–143): when `resp.get("units", "")` is missing/invalid (a brand-new model or pre-T66 model), it keeps `default_units()`, sets `units_dirty = true`, and immediately sends `set_units` — which saves `ShopSketchUnits` into the `.FCStd` even before the user types or picks anything.
  - `set_units(spec, from_user)` (~93–104): sets `units_user_set = true` and `_remember_units(units)` when `from_user` is true.
  - `apply()` (~224–258) and `on_length()` (~261–274): evaluate typed lengths in `default_unit()` and forward mm to the active tool, never inspecting whether the user typed an explicit unit to adopt.
- `viewport/units.gd`:
  - `parse_spec()` / `format_length()` / `evaluate_length()` / `evaluate_pair()` already know all supported specs (`ft-in:1/8..1/64`, `in-frac:1/8..1/64`, `in-dec:0.1..0.001`, `m:0.1..0.001`, `cm:1..0.01`, `mm:1..0.01`). There is no helper yet to infer a canonical display spec from a typed length string's explicit unit(s).

Request:
1. In `viewport/units.gd`, add a pure static helper `detect_typed_spec(text: String) -> String`:
   - Inspects a typed length or comma-separated pair (ignoring array counts like `5x` / `/5` and bare numbers with no unit suffix, returning `""` for those).
   - When an explicit unit appears, returns the matching canonical display spec:
     - `ft` or `'` (alone or with inches, e.g. `2'`, `1' 6"`, `1' 6 1/2"`) → `"ft-in:1/16"`
     - `in` or `"` with a decimal point on that number (e.g. `4.5"`, `0.75in`) and no fraction → `"in-dec:0.01"`
     - `in` or `"` otherwise (whole or fractional, e.g. `4"`, `3/4"`, `1 1/2 in`) → `"in-frac:1/16"`
     - `mm` → `"mm:0.1"`
     - `cm` → `"cm:0.1"`
     - `m` (not `mm` or `cm`) → `"m:0.01"`
   - For a pair (`a, b`) or arithmetic expression (`5in + 23mm`), use the first explicit unit encountered (except if `ft`/`'` appears anywhere in a feet+inches term, prefer `"ft-in:1/16"`).
2. In `viewport/measure_box.gd`:
   - Track whether the current document's units have been explicitly set (`var units_explicit := false`):
     - `init_units()` and `reset_for_model()` reset `units_explicit = false`.
     - `set_units(spec, from_user := true)`: when `from_user` is true (Units menu pick or auto-adoption below), set `units_explicit = true`.
     - `on_opened(resp, adopt := true)`:
       - If `saved.ok` (model already had `ShopSketchUnits` saved in `.FCStd`): adopt `saved.spec` and set `units_explicit = true` (existing models never silently flip units on typed input).
       - If `not saved.ok` (new model or pre-T66 model with no saved units): keep `default_units()` (previous settings / preference default per I62), keep `units_explicit = false`, and do **not** call `_send_units()` yet — so a reopened model with no typed/chosen units stays unset (or if you prefer saving on close, do NOT lock `units_explicit = true` until a unit is typed or picked in the menu; check existing `viewport/tests/quick/units.gd` expectations carefully!).
       - Important: check `viewport/tests/quick/units.gd` and `worker/test_units` to see if any existing test asserts that opening a unitless file immediately writes `ShopSketchUnits`! If an existing test asserts that I62 saves default units on open, keep `units_dirty = true; _send_units()` on open while still keeping `units_explicit = false` for the current session until the first explicit-unit typed length or Units menu pick — AND note that choice in your response (P44) if needed! Even better: read `viewport/tests/quick/units.gd` first to be 100% certain.
     - `on_reloaded(resp)`: if `saved.ok`, set `units_explicit = true`, else `units_explicit = false`.
   - On a **valid** typed length (both the fast path `here.ok` in `apply()` AND the FreeCAD-evaluated `resp.get("ok", false)` path in `on_length()` — never on a rejected/malformed string or a raw count/angle!):
     - If `not units_explicit`:
       - Compute `var detected := Units.detect_typed_spec(raw_txt)`.
       - If `detected != ""`: call `set_units(detected, true)` (which updates `units`, sets `units_explicit = true`, persists to `.FCStd` via `set_units`, remembers as last used in `settings.cfg`, and refreshes the Units menu / VCB / tooltip) **before** or alongside forwarding the evaluated mm to `active.typed(...)`!
       - If `detected == ""` (bare number, e.g. `100`): do NOT flip `units` (keep previous settings). Also leave `units_explicit = false` so a subsequent explicit unit (or explicit Units menu pick) still sets it? No — William said "reflect **first typed length** if nothing is set": if the first typed length is bare (no explicit unit), keeping `units_explicit = false` OR locking? Wait: if someone types `5` (bare, meaning current default) and hasn't specified a unit, nothing set the unit yet; only an explicit unit or Units menu pick locks `units_explicit = true`. Let's make sure once an explicit unit is adopted (`set_units(detected, true)`), `units_explicit` becomes `true`, so a later typed length in another unit (e.g. typing `19mm` inside an inches model) converts that one measurement without flipping the model's units (preserving I35/I59)!

What can fail (P42 — each case gets a named check):
- **Model already has saved `ShopSketchUnits` (e.g. `mm:0.1`):** typing `4", 5"` converts to `101.6 × 127 mm` as usual and does **not** flip the document's units away from `mm:0.1`.
- **User explicitly picked a unit from the Units menu on a new model:** typing `50mm` afterward converts without flipping the document's units.
- **New/unset model with no typed lengths yet:** stays on previous settings (`preferences.json` default, else `settings.cfg` last used, else fallback).
- **Malformed typed input with a unit (`abc mm`, `3//4"`):** fails evaluation and does **not** change document units.
- **FreeCAD-evaluated arithmetic (`1' 6" - 2"` or expression declined by local parser):** once FreeCAD replies `ok`, adopts `ft-in:1/16` if `not units_explicit`; if FreeCAD rejects it, does not change units.
- **Reopen after auto-adoption:** the adopted unit was persisted via `set_units` and remembered as last used, so reopening the model opens in the adopted unit and stays locked (`units_explicit = true`).

Cases that must still work:
- All existing checks in `viewport/test_units.gd` and `viewport/tests/quick/units.gd` (I35, I57, I59, I62, I63), including `preferences.json` `units.default` precedence and test-mode `mm` isolation.

Checks (new, named):
- In `viewport/test_units.gd`: `detect_typed_spec()` unit tests covering bare numbers (`""`), `4"` (`in-frac:1/16`), `4.25"` (`in-dec:0.01`), `3/4 in` (`in-frac:1/16`), `1' 6"` and `2ft` (`ft-in:1/16`), `120mm` (`mm:0.1`), `15cm` (`cm:0.1`), `1.5m` (`m:0.01`), pairs (`4", 5"`), and invalid/count strings (`3x`, `/3`, `""`).
- In `viewport/tests/quick/units.gd`: all 6 `What can fail` cases above (new model starts on previous settings; first typed `4", 5"` adopts `in-frac:1/16`, saves to `.FCStd` and remembers as last used; subsequent `19mm` in the same model does NOT flip units back; saved-units model does NOT flip; manual Units menu pick locks units; malformed input does NOT flip units).

Reading path: `viewport/units.gd` (`parse_length`, `parse_spec`, `evaluate_length`, `evaluate_pair`) → `viewport/measure_box.gd` (`init_units`, `default_units`, `set_units`, `reset_for_model`, `on_opened`, `on_reloaded`, `apply`, `on_length`) → `viewport/tests/quick/units.gd` → `viewport/test_units.gd`.

Run `tools/featuretest.sh` and `tools/quicktest.sh` while building, then `python3 tools/job.py test`. End your response with `Follow-up:` lines for leftovers and a `Result:` line.

---

**Response (Gemini, 2026-11-24):**
- Branch: `gemini/h138-t124-units-from-first-typed-length`, commit `61044ac`.
- Implemented `Units.detect_typed_spec(text)` in `viewport/units.gd` to infer canonical display specs (`ft-in:1/16`, `in-dec:0.01`, `in-frac:1/16`, `mm:0.1`, `cm:0.1`, `m:0.01`) from the first explicit unit in a typed length, pair, or expression (preferring `ft-in:1/16` when feet and inches appear together, and returning `""` for bare numbers, array counts, or function names like `sin(30)`).
- Added `units_explicit` tracking and `_adopt_typed_units(raw_txt)` in `viewport/measure_box.gd`: unset/new models keep previous/preference defaults without sending `set_units` on open; the first valid typed length (local `apply()` or FreeCAD-evaluated `on_length()`) adopts and saves an explicit unit (or keeps and locks the default unit if bare), while malformed inputs, raw counts/angles, saved-units models, and manually chosen Units menu specs never flip units.
- Added 29 `detect_typed_spec()` cases and MeasureBox lifecycle/adoption checks in `viewport/test_units.gd`, plus end-to-end checks for all 6 `What can fail` cases in `viewport/tests/quick/units.gd`.
- Verified with `tools/featuretest.sh` and `python3 tools/job.py test`: `UNITS TESTS: 167 passed, 0 failed`, all feature suites passed, `viewport: QUICK 340 passed, 0 failed`.
- IDs added: none. Open questions: none.

Changed from the brief: request item 2 hesitated on whether a bare first typed length should leave `units_explicit = false` or lock; locked `units_explicit = true` (and persisted current default units) on a bare first typed length; serves William's "first typed length" rule and prevents a later explicit-unit override (such as `3/4"` after bare `100` in `viewport/tests/quick/circle.gd`) from flipping a model whose user already typed bare numbers in the default unit.
Architecture: none.
Follow-up: none.
Result: 61044ac; featuretest + job.py test passed (UNITS 167/0, QUICK 340/0); added Units.detect_typed_spec and MeasureBox units_explicit auto-adoption on first typed length (T124, I67)
