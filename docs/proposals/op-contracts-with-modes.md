# Op Contracts for Ops with Modes (`move`, `push_pull`, `property_edit`, `fit`)

**Status:** Proposal for William (2026-11-27) · **No code changed yet.**

Four ops (`move`, `push_pull`, `property_edit`, `fit`) plus `mirror` (deferred from H192) were left out of single-mode `CONTRACT` dicts because their active fields, exclusions, `creates`, or `refers_to` depend on mode flags or target shape.
- **`property_edit`** (`model.py:348-349`, `object_properties.py:168-229`) and **`fit`** (`model.py:336-339`, `plane_fit.py:603-653`) actually have one fixed field set: `property_edit` only needs `enum: ["value", "expression"]` on `mode`, and `fit`'s `axis` bound (`0..2` vs `2`, `plane_fit.py:613`) depends on target stock in FreeCAD, not on op fields.
- **`move`** (`move.py:218-299`), **`push_pull`** (`push.py:159-327`), and **`mirror`** (`replace` mode) change which fields apply by mode. If William approves **T159** (`docs/proposals/T159-push-pull.md`), `fit_face`, `new_board`, and `resize_stock` split out of `push_pull`, leaving `push_pull` with `edit_board` + `to_face`/`through`/`distance < 0` exclusions; `move` and `mirror` still need mode support either way.

---

## Option A: Declarative `variants` list (first-match `when` selectors)

`CONTRACT` replaces top-level `fields`/`creates`/`refers_to` with `"variants": [...]`. Each variant has `"name"`, `"when"` (declarative predicates on op keys/values), `"fields"`, `"creates"`, `"refers_to"`, and optional `"excludes"` / `"constraints"`.

```python
# move (move.py:180-299, 363-372; field_audit.py:20-26)
{"type": "move", "tool": "viewport/tools/move_tool.gd", "variants": [
  {"name": "cut", "when": {"present": ["cut"]},
   "fields": {
     "cut": {"required": True, "kind": "{body, op}"},          # move.py:183-186
     "vector": {"required": True, "kind": "[number, number, number]"},  # move.py:187; |v|>=0.001 "distance is zero" (188-189)
     "copy": {"required": False, "kind": "bool", "default": False},     # move.py:192
     "count": {"required": False, "kind": "integer", "default": 1, "when": {"eq": {"copy": True}}},   # move.py:201
     "divide": {"required": False, "kind": "bool", "default": False, "when": {"eq": {"copy": True}}}, # move.py:202
     "targets": {"required": False, "kind": "[string]", "viewport_only": True}, # move_tool sends []; field_audit.py:21-25
   }, "creates": ["id"], "refers_to": ["cut.body", "cut.op"]},
  {"name": "selection", "when": {"eq": {"selection": True, "copy": False}},
   "fields": {
     "targets": {"required": True, "kind": "[string]"},         # move.py:364
     "vector": {"required": True, "kind": "[number, number, number]"},  # move.py:372
     "selection": {"required": True, "kind": "bool"},           # move.py:221
     "detach": {"required": False, "kind": "bool", "default": False},   # move.py:366
     "copy": {"required": False, "kind": "bool", "default": False},     # move.py:221
   }, "creates": ["id"], "refers_to": ["targets"]},
  {"name": "move", "when": {},
   "fields": {
     "targets": {"required": True, "kind": "[string]"},         # move.py:240
     "vector": {"required": True, "kind": "[number, number, number]"},  # move.py:223
     "copy": {"required": False, "kind": "bool", "default": False},     # move.py:224
     "count": {"required": False, "kind": "integer", "default": 1},     # move.py:225
     "divide": {"required": False, "kind": "bool", "default": False},   # move.py:226
     "detach": {"required": False, "kind": "bool", "default": False},   # move.py:245
     "new_ids": {"required": False, "kind": "[string]"},        # move.py:228
     "groups": {"required": False, "kind": "{string: string|[string]}"}, # move.py:229-238 "each copied assembly needs its own assembly id"
     "selection": {"required": False, "kind": "bool"},          # move.py:221 (when copy=True)
   }, "creates": ["id", "new_ids", "groups.*"], "refers_to": ["targets", "groups.@keys"]}
]}
```

```python
# push_pull (push.py:159-327)
{"type": "push_pull", "tool": "viewport/tools/push_tool.gd", "variants": [
  {"name": "fit_face", "when": {"present": ["edge_fit", "target.face"], "absent": ["target.region"]},
   "fields": {
     "target": {"required": True, "kind": "{face}"},           # push.py:169,171
     "distance": {"required": True, "kind": "number", "nonzero": 0.001}, # push.py:160-162 "distance is zero"
     "edge_fit": {"required": True, "kind": "{target_body, face, fit_mode?}"}, # push.py:165,180-181
   }, "excludes": ["to_face"], "creates": ["id"], "refers_to": ["target.face.body", "edge_fit.target_body"]},
  {"name": "resize_stock", "when": {"eq": {"resize_stock": True}, "present": ["target.face"], "absent": ["target.region"]},
   "fields": {
     "target": {"required": True, "kind": "{face}"},           # push.py:192,194
     "distance": {"required": True, "kind": "number", "nonzero": 0.001}, # push.py:160-162
     "resize_stock": {"required": True, "kind": "bool"},        # push.py:192
   }, "excludes": ["to_face", "edge_fit"], "creates": ["id"], "refers_to": ["target.face.body"]},
  {"name": "new_board", "when": {"any": [{"present": ["body"]}, {"present": ["target.region"], "absent": ["target.face", "target.rect"]}]},
   "fields": {
     "target": {"required": True, "kind": "Target"},            # push.py:197-249
     "distance": {"required": True, "kind": "number", "nonzero": 0.001}, # push.py:160-162
     "body": {"required": False, "kind": "string"},             # push.py:255
     "assembly": {"required": False, "kind": "string"},         # push.py:275-279 "unknown assembly '...'"
     "edge_fit": {"required": False, "kind": "{target_body, face, fit_mode?}"}, # push.py:283-285
   }, "excludes": ["to_face"], "creates": ["id", "body?"],
   "refers_to": ["target.rect", "target.face.body", "target.region.lines", "assembly?", "edge_fit.target_body?"]},
  {"name": "edit_board", "when": {},
   "fields": {
     "target": {"required": True, "kind": "Target"},            # push.py:197-249
     "distance": {"required": True, "kind": "number", "nonzero": 0.001}, # push.py:160-162
     "through": {"required": False, "kind": "bool", "default": False},  # push.py:312
     "to_face": {"required": False, "kind": "{normal, point}", "when": {"lt": {"distance": 0}, "not": ["through"]}}, # push.py:167-168 "to_face is only for a cut into a board"
   }, "creates": ["id"], "refers_to": ["target.rect", "target.face.body", "target.region.lines"]}
]}
```

**Checks & H194:** `test_op_contracts.py` loops over each variant (`AuditedDict` + `creations`); `test_document.gd` builds one sample op per variant for `_op_makes`/`_op_refs`; `protocol_map.py` unions field names across variants; `validate(op)` evaluates `when` in order, then checks required/unknown/kind/`nonzero`/`excludes`.

---

## Option B: Flat `fields` with per-field `when` / `excludes`

Keep one `fields` dict per op (same top-level shape as H189) and attach `when` and `excludes` to individual fields, `creates`, and `refers_to`.

```python
# move (flat; move.py:180-299, 363-372)
{"type": "move", "tool": "viewport/tools/move_tool.gd", "fields": {
  "targets": {"required": True, "kind": "[string]", "unread_when": "cut"}, # move.py:240,364; field_audit.py:21-25
  "vector": {"required": True, "kind": "[number, number, number]"},        # move.py:187,223,372
  "cut": {"required": False, "kind": "{body, op}", "excludes": ["selection", "detach", "new_ids", "groups"]}, # move.py:183,219
  "selection": {"required": False, "kind": "bool"},                        # move.py:221
  "copy": {"required": False, "kind": "bool", "default": False},           # move.py:192,224
  "count": {"required": False, "kind": "integer", "default": 1, "when": "not (selection and not copy) and (not cut or copy)"}, # move.py:201,225
  "divide": {"required": False, "kind": "bool", "default": False, "when": "not (selection and not copy) and (not cut or copy)"}, # move.py:202,226
  "detach": {"required": False, "kind": "bool", "default": False, "when": "not cut"}, # move.py:245,366
  "new_ids": {"required": False, "kind": "[string]", "when": "not cut and copy"}, # move.py:228
  "groups": {"required": False, "kind": "{string: string|[string]}", "when": "not cut and copy"}, # move.py:229
}, "creates": ["id", "new_ids?", "groups.*?"], "refers_to": ["targets?", "cut.body?", "cut.op?", "groups.@keys?"]}
```

```python
# push_pull (flat; push.py:159-327)
{"type": "push_pull", "tool": "viewport/tools/push_tool.gd", "fields": {
  "target": {"required": True, "kind": "Target"},                          # push.py:163,197-249
  "distance": {"required": True, "kind": "number", "nonzero": 0.001},      # push.py:160-162
  "body": {"required": False, "kind": "string", "excludes": ["to_face", "through", "resize_stock"]}, # push.py:167,251,255
  "assembly": {"required": False, "kind": "string", "when": "new_board"},  # push.py:275-279
  "through": {"required": False, "kind": "bool", "default": False, "excludes": ["to_face", "body", "edge_fit", "resize_stock"]}, # push.py:167,312
  "resize_stock": {"required": False, "kind": "bool", "excludes": ["to_face", "through", "body", "edge_fit"]}, # push.py:167,192
  "edge_fit": {"required": False, "kind": "{target_body, face, fit_mode?}", "excludes": ["to_face", "through", "resize_stock"]}, # push.py:167,169,283
  "to_face": {"required": False, "kind": "{normal, point}", "when": "distance < 0", "excludes": ["through", "edge_fit", "resize_stock", "body"]}, # push.py:167-168,187-188,252-253
}, "creates": ["id", "body?"], "refers_to": ["target.rect?", "target.face.body?", "target.region.lines?", "assembly?", "edge_fit.target_body?"]}
```

**Checks & H194:** `protocol_map.py` needs zero structural change; `test_op_contracts.py` and `validate(op)` must parse boolean `when` expressions (`not (selection and not copy) ...`) and cannot easily generate all valid combinations without a solver.

---

## Option C: Named `variants` dict + Python classifier function beside the handler

`CONTRACT` holds `"variants": {"cut": {...}, "selection": {...}, "move": {...}}` (same per-variant `fields`, `creates`, `refers_to` as Option A, **without** a `when` mini-DSL in JSON). Beside the handler, a small pure function `variant(op) -> str` (listed in `op_contracts.py` as `VARIANT_SELECTORS`) mirrors the handler's exact `if/elif` dispatch:

```python
# worker/move.py — beside MoveActions.op_move (lines 218-222)
def move_variant(op):
    if op.get("cut"): return "cut"
    if op.get("selection") and not op.get("copy", False): return "selection"
    return "move"

# worker/push.py — beside PushActions.op_push_pull (lines 167-251)
def push_pull_variant(op):
    tgt = op.get("target", {})
    if op.get("edge_fit") and "face" in tgt and "region" not in tgt: return "fit_face"
    if op.get("resize_stock") and "face" in tgt and "region" not in tgt: return "resize_stock"
    if op.get("body") or ("region" in tgt and "face" not in tgt and "rect" not in tgt): return "new_board"
    return "edit_board"
```

The `variants` dicts for `move` and `push_pull` have the exact same `fields`, `creates`, and `refers_to` as Option A, with `when` replaced by the Python selector (plus a `"sample"` seed per variant so tests can construct each mode without solving `when`).

**Checks & H194:**
- **Fields read (`test_op_contracts.py`)**: loops over `contract["variants"]`, checks `variant(op) == name`, runs `AuditedDict` and `creations` per variant.
- **Creates / Refers to (`test_document.gd`)**: GDScript reads `tests/op_contracts.json` (`variants`) and builds one sample op per variant (using `"sample"` seed); no `when` evaluator needed in GDScript.
- **Protocol row (`protocol_map.py`)**: unions field names across `variants` (matching `move` + `move with cut` rows in `docs/protocol.md:254-255`).
- **Tools / Draft (`test_tool_context.gd`, `push_tool.gd`, `move_tool.gd`)**: tool tests pass each committed op to `variant(op)` (or match against one variant) and verify no undocumented fields. (Board ops draw no profile draft.)
- **H194 (`validate(op)`)**: calls `variant(op)` to pick the active variant dict, then runs the exact same required/unknown/kind/`min`/`nonzero`/`excludes` check as single-mode ops.

---

## Recommendation & Questions for William

**Recommend Option C** (named `variants` dict in `tests/op_contracts.json` + small `*_variant(op)` Python function beside the handler):
- No `when` expression mini-DSL to invent, parse, or port to GDScript.
- `op_contracts.json` stays pure data; `validate(op)` in H194 only runs in Python anyway.
- Pairs cleanly with **T159**: if T159 splits `push_pull`, three variants become their own single-mode contracts and `push_pull` shrinks to one, while `move` and `mirror` still use `variants`.

**Questions for William:**
1. **Pick a contract shape for ops with modes:** Option C (named `variants` + Python `*_variant(op)` selector, recommended), Option A (declarative `when` rules in JSON), or Option B (flat `fields` with per-field `when`/`excludes`)?
2. **`move_tool.gd` sending `targets: []` on `cut` moves** (`field_audit.py:21-25`): keep `targets` marked `viewport_only: True` on the `cut` variant, or stop sending `targets` on `cut` moves?
3. **Should `mirror` (`replace` mode) be included** in the follow-up job that writes the contracts for `move`, `push_pull`, `property_edit`, and `fit`?
