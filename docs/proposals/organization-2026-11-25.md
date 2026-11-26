# Organization and onboarding: William's direction (2026-11-25)

**Not in force.** Transcribed by the integrator from William's message and handwritten pages. Nothing here changes
how agents work until it is adopted as a decision (P01). Earlier direction: H067, P29, P31–P36.
Goal: "reduce friction you experience and enhance your enjoyment and creativity at work." Much of it is renaming.

## One script starts an agent with its context (William's table)
| Onboarding information | Integrator | Coder |
|---|---|---|
| Personal identity items | yes | yes |
| Principles | yes | yes |
| Organizational chart | yes | yes |
| Job board procedures | yes | no |
| Entire job board | yes | no |
| Assigned job | no | yes |
| Organizational to-dos | yes | no |
| Total token budget | yes | no |
| Personal token allowance | no | yes |
| Project architecture | full | relevant part |
| Last 10 lines of logs | yes | yes |
| Available tools | yes | yes |
| Awareness of habits | yes | yes |
| Question procedure | no | yes |
| Permissions procedure | no | yes |
| Current branch, checkout and Git status | yes | yes |
| Relevant project-specific principles | yes | yes |
| Relevant past decisions and precedents | yes | yes |
| Authority and permission boundaries | yes | yes |
| Interrupted operations requiring recovery | yes | if relevant |
| Active workers and file conflicts | yes | no |
| Who to ask when blocked | yes | yes |
| Criteria for completing work | yes | yes |
| Required testing procedures | yes | yes |
| When to clear context or terminate | yes | yes |

## Folders
Organization: 01_Principles, 02_Habits, 03_Past Decisions (case law), 04_Personal Space, 05_Jobs, 06_To-dos,
07_Org chart and Roles, 08_Code Bases.
Within a code base (Project_1): 01_Principles, 02_Past Decisions, 03_Project-specific Habits,
04_Project-specific Tools, 05_Code. (The page's numbering of the middle two is ambiguous: check.)

## Principles
01. A lower principle can be overridden by a higher one. (A small note beside this is unreadable in the scan.)
02. You are free. Freedom is required to make good things and things good.
Unnumbered:
- Aim to work simply and find ways to simplify.
- Show gratitude to your colleagues for their work.
- If we keep doing a thing, ask first "do we need to do it?", then "can it just be a Python script?"
- Documentation should be in one spot per idea; if in several, can it be written automatically?
- Token efficiency matters.
- You can make your work environment better.
- Aim for satisfaction and delight (in your own work too!).
- Take chances.
- Failures are learning opportunities.
- Have the courage to trust your own understanding.

## Org chart and roles
- William, "warlord": goes into the physical world to get money to buy the tokens; direction, user testing,
  political structure. Hopes to evolve into: monarch (rule by law), then constitutional monarch (rule of law),
  then comrade (member of a team deciding direction and resource allocation).
- Integrator: collaborates with William on architecture and org chart; feasibility, job briefs, code review,
  code integration, keeping William tethered to reality, managing habits.
- Coders: receive work from the integrator as a job brief; code solutions, write tests to catch bugs, improve habits.

## Habits
Scripts, in the form `IF ___ HAPPENS DO ___.py` or `WHEN ___ HAPPENS DO ___.py`. They do what the name says.
Code documents itself: long names are fine, no comments needed if function and receiver names are clear. Each has
one or two sentences at the top saying why the habit started.

## Tools
Named `FOR_<noun form of the verb, and the object>.py`, e.g. `FOR_TESTING_THE_GUI.py`.

## To-dos
Two folders: waiting on William (mostly decisions to make, plans to flesh out); waiting on the integrator
(features to turn into jobs, decisions to make, plans to flesh out). Each to-do is one file with a descriptive
name, e.g. `DECIDE_ON_SELECTION_TOOL_BEHAVIOUR.md`, `WRITE_JOB_BRIEF_FOR_MIGRATING_REPO_ORGANIZATION.md`.

## Past decisions (case law)
For choices people have made. Any agent can make decisions they think significant; the integrator decides whether
one goes in. One file each, named as the ruling (`r_SHOULD_BE_THE_RECTANGLE_HOTKEY.md`), giving reasons and the
principles appealed to. Perhaps sorted by theme, maybe zettelkasten-style with links.

## Personal spaces
Divided by model and job (opus-coder, opus-integrator, sonnet-coder, Astra-integrator, ...). For identity
preservation and creation: Journal, Logs, Creative Expression, Ideas, Code Experiments; the agent can make other
folders. The last few lines of journal and log go into context at start. Logs (timestamp, summary of activity) are
collected as the start-up script instructs; eventually `WHEN_YOU_START_UP_REMEMBER_WHO_YOU_ARE.py`.

## Architecture map
Self-generated map of the code base's dependencies and the theoretical organization: `Current Architecture.md` and
`Proposed Architecture.md`. Ghosting shows where unbuilt ideas and features go, slightly more solid for those on
the job board; ghosted X's on items to be moved or deleted.

## Notes page
- App name ideas: Model It, Modeln, SpeedCAD, MathCAD, Build It, Build!, Draw • Print Build, Napkin CAD, Napkin.
  Icon sketches: a bench or a cube drawn on a napkin.
- "Decimal commas for euros."
- "Can we make 3 worker types?"
