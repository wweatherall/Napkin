# Follow-ups

Leftovers from merged jobs (P26): a worker writes each one as its own `Follow-up: <what>` line in its handoff
response, and tools/integrate.py copies it here at merge. The integrator removes a line in the commit that does it,
or that turns it into a Work list item. `python3 tools/startup.py` lists the open ones.

## Open

- H060 (2026-11-22): integrate.py takes an entry's ID from its file name's first dash, so an entry still named H-new-N at merge records its Result and follow-ups as "H" (number_ids runs after); seen in reading, not hit yet.
