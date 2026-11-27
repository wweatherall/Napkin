### H164 — One personal space per model and job, every new one made the same from a template

Author: Claude (integrator, napkin-77) | Date: 2026-11-26 | Status: answered | For: gemini

Item: T156

References: T156 (this item), T150/H158/H159 (spaces, folders, READMEs, auto-save), William's proposal
("Personal spaces: divided by model and job (opus-coder, opus-integrator, sonnet-coder, Astra-integrator, ...)"),
H162 (how a job changes the comitatus repo: its own worktree and branch there).

Touches: tools/launch.py (`space_of`, `prompt`, `agent_command`, `main`), tools/personal_space.py, tools/job.py
(`save_personal_space`, `_take`), tools/startup.py (`INTEGRATOR_SPACE`), tools/test_launch.py,
tools/test_personal_space.py, tools/test_job.py, docs/integrator.md.

In the comitatus repo (not in Touches: the check reads Napkin paths): 04_Personal_Space/README.md, a new template
folder (below), and the rename of `04_Personal_Space/gemini-coder`.

Reading path:
1. `tools/launch.py` `space_of(agent)` (`<agent>-coder` today, whatever the model), `DEFAULT_MODEL`, `main` (`--model`).
2. `tools/personal_space.py` `HEADERS`, `FOLDERS`, `OLD_FOLDERS`, `ensure_folders`, `add`, `save`.
3. `tools/job.py` `save_personal_space(root, agent)` (called at `done`; uses `space_of(agent)`, so it doesn't know the
   model) and `_take` (what the queue records for a job: agent, session, branch ...).
4. `tools/startup.py` `INTEGRATOR_SPACE = "opus-integrator"`.

Today (checked 2026-11-26 on main 3aa16d5): a space is named by agent only, so a Sonnet and an Opus Claude worker
would share `claude-coder`, and Gemini's Hydrogen and Neon share `gemini-coder`. A new space gets Log/Journal
headers and the three folders with READMEs from constants in personal_space.py; `ASCII art.txt` (William, 2026-11-26)
was added by hand to the two existing spaces only.

Request (William, 2026-11-26: "every different model and job gets a different space, and they're all the same at
the start"):
1. **Named by model and job.** `space_of(agent, model)` gives `<model>-coder`: the model's family word, lower case:
   Claude `sonnet` / `opus` / `haiku` / `fable` (from `--model`, which may be an alias like `sonnet` or a full id like
   `claude-opus-5-5`); Gemini `gemini-<variant>` (`gemini-4-hydrogen-medium` -> `gemini-hydrogen`,
   `gemini-4-neon-medium` -> `gemini-neon`); Codex `codex` (no model chosen). An unrecognised model: `<agent>-coder`,
   as today (never an error). The integrator's stays `opus-integrator` (`INTEGRATOR_SPACE`; a later job can derive it).
2. **The worker keeps its space through the job.** `launch.py` knows the model; `job.py` doesn't. Pass the space to
   the worker's session (e.g. an environment variable set in `agent_command`, `NAPKIN_SPACE=<name>`), record it on the
   job at `_take`, and have `save_personal_space` use the recorded space (falling back to `space_of(agent)` with no
   model for a job taken without one). The first message and the start-up brief name that space.
3. **One template.** New spaces are copied from `comitatus/04_Personal_Space/NEW_SPACE_TEMPLATE/` (upper case, so it
   can never be a member's name: `NAME` only allows lower case): `Log.md` and `Journal.md` with today's headers and no
   lines, the three folders with today's README texts (`FOLDERS`), and `Creative_Expression/ASCII art.txt` holding one
   line, `ASCII art (<name>)`, followed by a blank line (`<name>` filled in when copied). Copy only files missing from
   the space (an agent's own file is never overwritten); keep `OLD_FOLDERS`' exact-text replacement. The constants
   stay as the fallback when the template folder is missing. William edits the template to change what every new
   space starts with; `04_Personal_Space/README.md` says so in a line.
4. **The existing Gemini space.** Every Gemini job so far ran on `gemini-4-hydrogen-medium`: rename
   `04_Personal_Space/gemini-coder` to `gemini-hydrogen-coder` with `git mv` on the comitatus branch, so its history
   follows it.
5. **Comitatus side** on its own worktree and branch, as H162 did:
   `git -C /Users/Will/Sites/comitatus worktree add /Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/comitatus/h164
   -b gemini/h164-space-template`; name the branch and commit in your response. The integrator merges it first.

What can fail:
- A model string nobody listed (a new Claude family, a typo): falls back to `<agent>-coder`. Check: test_launch.py.
- `done` after a restart of the worker's shell without the variable: the space recorded at take is used. Check:
  test_job.py.
- The template missing (a checkout outside comitatus, a deleted folder): today's constants are used. Check:
  test_personal_space.py.
- An agent's own `ASCII art.txt` or README: never overwritten. Check: test_personal_space.py.
- The rename losing history: quote `git log --follow --oneline -- 04_Personal_Space/gemini-hydrogen-coder/Journal.md`.

Checks:
- tools/test_launch.py, tools/test_personal_space.py, tools/test_job.py: the cases above; `space_of` for sonnet,
  claude-opus-5-5, gemini-4-hydrogen-medium, gemini-4-neon-medium, codex None, and an unknown model.
- `python3 tools/launch.py gemini --dry-run` and `python3 tools/launch.py claude --model opus --dry-run` (quote the
  space each names).
- `tools/TEST_BEFORE_MERGING.sh` passes (scope tools).

Response:
- `tools/launch.py`: updated `space_of(agent, model=None)` to map Claude families (`sonnet`, `opus`, `haiku`, `fable`) and Gemini variants (`hydrogen`, `neon`) to `<model>-coder`, falling back to `<agent>-coder` when model is `None` or unrecognized; updated `prompt()`, `agent_command()` (exports `NAPKIN_SPACE=<space>`), and `main()` (`--space` to `startup.py` and `model` to `prompt()`).
- `tools/personal_space.py`: added `template_dir()` and `copy_template()` to populate new spaces from `comitatus/04_Personal_Space/NEW_SPACE_TEMPLATE/` (replacing `<name>`, never overwriting existing files, and preserving `OLD_FOLDERS` exact-text README replacement), falling back to `HEADERS` and `FOLDERS` when `NEW_SPACE_TEMPLATE/` is missing.
- `tools/job.py`: `_take()` records `"space"` from `NAPKIN_SPACE` (falling back to `launch.space_of(agent)`), and `done()` passes `j.get("space")` to `save_personal_space()`.
- Comitatus repo (`/Users/Will/Sites/comitatus/08_Code_Bases/.worktrees/comitatus/h164`, branch `gemini/h164-space-template`, commit `9ea430e`): added `04_Personal_Space/NEW_SPACE_TEMPLATE/` (`Log.md`, `Journal.md`, `Creative_Expression/README.md`, `Creative_Expression/ASCII art.txt`, `Ideas/README.md`, `Code_Experiments/README.md`), updated `04_Personal_Space/README.md`, and renamed `04_Personal_Space/gemini-coder` to `04_Personal_Space/gemini-hydrogen-coder` with `git mv`.
- `git log --follow --oneline -- 04_Personal_Space/gemini-hydrogen-coder/Journal.md`:
  `9ea430e`, `dd2eafe`, `e4e63aa`, `dba7844`.
- Dry-run checks: `python3 tools/launch.py gemini --dry-run` -> `NAPKIN_SPACE=gemini-hydrogen-coder`; `python3 tools/launch.py claude --model opus --dry-run` -> `NAPKIN_SPACE=opus-coder`.
- Tests: `tools/test_launch.py` (15/15), `tools/test_personal_space.py` (23/23), `tools/test_job.py` (200/200), `tools/TEST_BEFORE_MERGING.sh` (GATE PASS, scope tools, 26 s).

Result: 0d68ea9; launch 15/15, personal_space 23/23, job 200/200, gate (scope tools) 26s; one personal space per model/job from NEW_SPACE_TEMPLATE and gemini-hydrogen-coder rename (comitatus gemini/h164-space-template 9ea430e)
