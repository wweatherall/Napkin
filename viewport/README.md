# Running the viewport directly

See [README.txt](../README.txt) for setup, controls, model saving and user-visible feedback.
For development rules and tests, read [CLAUDE.md](CLAUDE.md); for component boundaries,
read [ARCHITECTURE.md](../ARCHITECTURE.md).

Open this folder in Godot and press Play, or run from the repository root:

```sh
/Applications/Godot.app/Contents/MacOS/Godot --path viewport
```

Arguments after `--` override paths when needed:

| Argument | Purpose |
|---|---|
| `--model=/absolute/path/model.FCStd` | Open a specific model instead of the last-used/default model |
| `--out=/absolute/path/out` | Set the export root; normal windows use a per-model subfolder, tests use it directly |
| `--freecad=/path/to/freecadcmd` | Override the FreeCAD executable |
| `--worker=/path/to/replay.py` | Override the worker entry point |
| `--worker-log=/path/worker.log` | Override the worker log (default `user://worker.log`) |
| `--drawing=/path/to/drawing.py` | Override the drawing composer |
| `--port=N` | Connect to an externally started worker on that port |

Normal launch manages worker discovery/start/recovery automatically. Model data lives in the
FCStd and adjacent journal; `user://settings.cfg` remembers the last model. For transport,
identity and ownership rules, see [the architecture map](../ARCHITECTURE.md#protocol-at-a-glance).
