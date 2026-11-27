### H155 — T148: switch off FreeCAD's backups only for Shop Sketch's own saves, then put William's setting back

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: open | For: either

References: T148, A41 (William, 2026-11-26: option B), I68 (no .FCBak from Shop Sketch's saves), A32 (atomic saves),
A38 (floor copy), P42.

Touches: worker/session.py (the module's top line, `_write`, `_write_floor_copy`, a new helper beside them), worker/test_generations.py.

Reading path:
1. `worker/session.py` line 3: `App.ParamGet("User parameter:BaseApp/Preferences/Document").SetBool("CreateBackupFiles", False)`
   at import, so the whole worker runs with FreeCAD's shared preference switched off.
2. `Session._write` (around line 848): sets the same preference again, then `self.doc.saveCopy(tmp)`.
3. `Session._write_floor_copy` (around line 405): `self.doc.saveCopy(tmp)` with no setting of its own (it relies on
   line 3).
4. `worker/test_generations.py` around line 306 (T125): sets the preference True, saves, checks no `.FCBak` appears.

Today (checked 2026-11-26 on main): the worker writes "no backups" into FreeCAD's user preferences, which William's
own FreeCAD reads too. Tested today: `saveCopy` over an existing file does write `<name>.<date>.FCBak` when backups
are on, so the saves still need them off.

Request (A41): a small context manager in session.py, `no_backups()`, that reads `CreateBackupFiles` (FreeCAD's default
when unset is True: read it with `GetBool("CreateBackupFiles", True)`, and remember whether it was set at all), sets it
False, yields, and in a `finally` puts back exactly what was there (the old value, or removes the entry with
`RemBool` if there was none), so an exception mid-save still restores it. Both `saveCopy` calls run inside it. Delete
the import-time line and the line in `_write`. Nothing else changes: same files, same names, same messages.

What can fail (P42: saving):
- A save that raises (read-only folder, T79): the setting is restored anyway (the `finally`), and the error reaches
  the caller as today.
- A drawing export after the save (`_write` opens the copy for TechDraw): it doesn't save over a file, so it needs
  no guard; say in your response if you find another save path.
- William's FreeCAD open at the same time: it reads its preferences at its own start, so a few milliseconds of
  "off" during a Shop Sketch save don't reach it.

Checks, in worker/test_generations.py, each failing without the change:
- "a save leaves the backup preference as it found it (on)" (set True, save twice over the same file, still True,
  and no .FCBak);
- "a save leaves the backup preference as it found it (off)" (set False, save, still False);
- "a save that fails still puts the preference back" (a read-only folder, preference True before and after);
- "importing session no longer changes the preference" (set True, reload the module, still True).
The T125 check stays and passes.
