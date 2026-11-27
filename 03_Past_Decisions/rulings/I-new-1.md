# I-new-1 — Before a Polygon gesture the measurements box is the side count: a number typed there s...

Status: Active | Subject: Drawing tools | Principles: G03 | Date: 2026-11-26
Replaces / replaced by: Replaces I72
Where in the code: viewport/tools/polygon_tool.gd (click, typed)

Before a Polygon gesture the measurements box is the side count: a number typed there sets the sides with Return, or at the centre click if not entered (8 or 8s; outside 3-64 is dropped); the radius still starts from an empty box. During a gesture 8s + Return sets the sides and a plain number is the radius.

Why: William, 2026-11-26: bug, 'it doesn't let you type in the number of sides (click polygon tool, type number, click center point, click outside point, see hexagon)'; the box says Sides before the click.
