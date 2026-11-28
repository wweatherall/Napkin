# How a fit lets go

**Draft for William · H202 · 2026-11-28**

I77 keeps the fitted board at its last length when a cut or deletion removes the target face. I76 also holds that length while a rectangular target turns edge-on, then resumes the fit as the opposite face turns toward the board. The draft uses charcoal marks over Napkin's confirmed stock, with the same dark outlines and softly edged strokes as the viewport. The fitted stock stays still through both effects.

## Watch the two drafts

Open `viewport/project.godot` in Godot 4.6, open [the comparison scene](../../viewport/demos/fit_detach_demo.tscn), and press **F6** to run the current scene. From the repository root you can also run:

```sh
/Applications/Godot.app/Contents/MacOS/Godot --path viewport res://demos/fit_detach_demo.tscn
```

Choose **Falling links** or **Slack thread**, then use **Replay detach** to repeat the selected look. The left target is cut back while the right target stays paused at a quarter turn. The boards on the left and right both start and finish at **600 mm**. The captions give you a length to compare while viewing the draft. The scene stands alone and uses sample geometry.

| Look | When the face goes away | What stays on the fitted end | Beside a paused fit |
|---|---|---|---|
| **Falling links** | Four interlocked outlines come apart from the target side, tip downward in succession and fade near the grid. The target face disappears and the fitted board's outline holds still, so the motion belongs to the connection. | A small open-link mark sits on the fitted end face. You can see the same square end and the space where the face used to be. | An intact chain droops slightly between the boards. Closed loops read as a connection that can take up tension again. |
| **Slack thread** | One line loses tension and droops. Its two halves separate, with the free end slipping away first. The fitted end and its outline stay in place as the thread falls. | Two short strokes with a gap sit on the fitted end face. The gap echoes the released thread against the full-size board. | A single shallow curve joins both ends. Continuity carries the distinction, which may be hard to see if the connector is nearly edge-on or just a few pixels wide. |

The motion lasts **1.08 seconds**. Replay includes a short look at the live fit, for **1.32 seconds** in total.

## What it would take to build

Both looks can use the existing `stock_frame.fit_state` and the presenter's line meshes. A viewport implementation could compare confirmed states in `viewport/presenter.gd`, with a small overlay script for the mark and animation and a focused check in `viewport/tests/quick/properties.gd`. Keep the last live geometry anchor in memory so there is still a place to start the effect when the target has been deleted. Check that anchor and the surviving fitted end before drawing. Initial open and cached state restoration can show a settled mark straight away. Play the motion once when a new edit confirms the detachment, so repeated receipts and a reopened file stay quiet. When FreeCAD's answer determines that the face is gone, the effect can start with that same confirmed frame and leave input and the edit's draft on their existing path.

| Look | Overlay work | Per-frame cost to verify |
|---|---|---|
| **Falling links** | Four cached link outlines, staggered transform and alpha changes, and one static end mark. The paused connector can be one batched mesh. | Up to four moving draw calls per visible detachment during the effect, plus one for the end mark as the motion settles. The settled view needs one static draw call and no animation updates. |
| **Slack thread** | Two cached strokes with independent motion and alpha, a continuous paused curve, and one static end mark. The demo bends the thread by posing two smooth, prebuilt halves. | Up to two moving draw calls per visible detachment during the effect, plus one for the end mark as it settles. The settled view needs one static draw call and no animation updates. |

These are estimates of work per frame. Profile both costs in milliseconds against a plain viewport frame, including a cut that detaches several fits at once. Check the end marks at shallow camera angles and when a face is occluded. I would first try showing the settled marks and the intact paused connector when the fitted board is selected or its fit is being inspected. That lets someone find the state again after the motion has passed, while keeping the drawing quiet.

## Recommendation

Try **Falling links** first. The intact chain beside the opened link makes the pause easier to recognize by shape, and the separate outline of the board lets the chain fall without making the board look damaged. The thread is a quieter gesture, with a smaller difference between the two settled states.

After replaying both next to the paused example, **which look best tells you that the board kept its length and the fit has let go?** I would start with Falling links and check how it reads at the zoom William uses for fitting boards.
