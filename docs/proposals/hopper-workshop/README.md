# Napkin Hopper workshop prototype

This is a proposed UI-only change based on the `main` versions of `tools/job.py`, `tools/hopper_picture.py`, and `tools/SHOW_THE_HOPPER.py` inspected on November 28, 2026. Nothing has been pushed to GitHub.

## Try without Napkin

From this folder:

```sh
python3 hopper_workshop.py --demo --watch
python3 hopper_workshop.py --demo --width 78
python3 hopper_workshop.py --demo --width 120
python3 -m unittest -v test_hopper_workshop
```

The demo contains fictional jobs. Resize the terminal while watching. A short window uses compact characters; enlarge its height to see full avatars. `HOPPER_NO_ANIMATION=1` disables motion. Ctrl-C exits the demo.

## Integrate into Napkin

From the root of a Napkin checkout, set `WORKSHOP` to the extracted folder's absolute path, then:

```sh
cp "$WORKSHOP/hopper_workshop.py" tools/
cp "$WORKSHOP/test_hopper_workshop.py" tools/
git apply --check "$WORKSHOP/integration.patch"
git apply "$WORKSHOP/integration.patch"
python3 tools/test_hopper_workshop.py
python3 tools/test_hopper_picture.py
python3 tools/test_job.py
python3 tools/SHOW_THE_HOPPER.py --watch
```

`SHOW_THE_HOPPER.py --watch` is read-only; after stopping it, use the existing `RUN_THE_HOPPER.py --forever` command only when ready to dispatch real jobs. Redirected output and `SHOW_THE_HOPPER.py --plain` retain the old renderer. No changes to dispatcher state transitions or locks are intended. The existing renderer and its golden tests remain unchanged.

## Design

- Claude: rotating sunburst; Gemini: pulsing twin diamonds; Codex: circulating ASCII knot.
- Active jobs animate; waiting jobs retain the first static sprite. The hopper spout moves only when a launch is recorded. Completed and merged jobs are static.
- At 100 usable columns the workbench and questions panel sit side by side; narrower terminals stack them. Below a practical avatar width or when height is limited, the display uses compact symbols. An explicit overflow notice appears if the compact picture still cannot fit.
- Terminal size is checked each animation tick. Queue state is loaded once per existing dispatch or watch cycle, not per frame. Animation ticks at 4 Hz, with sprite changes every two ticks. No AI calls or extra token usage.
- Standard-library Python only. Unicode column widths use a best-effort approximation; unusual grapheme clusters and terminal-specific width settings can differ.

## Verification and limitations

Seven new unit tests passed in the prototype, including all widths from 1 to 240, active/static sprites, base-before-stacked order, Unicode clipping, terminal escape stripping, small-window fallback and the 20-second clock. The integration patch was checked against reconstructed exact source excerpts from GitHub, not a full live checkout. Run the repository's existing tests before merging. No live dispatch or real macOS Terminal session was exercised here. State changes are only observed at the existing poll cadence, so the graphics represent recorded status, not live agent thought or tool use.
