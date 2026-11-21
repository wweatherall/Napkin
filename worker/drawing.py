"""Compose a shop drawing (A3, third-angle) from the worker's outputs.

usage: python3 drawing.py OUTDIR [oplog.json]
reads  OUTDIR/views.json, bodies.json, status.json
writes OUTDIR/drawing.svg, drawing.pdf, drawing.png, cutlist.csv
"""
import csv
import json
import os
import re
import sys
from collections import OrderedDict

try:
    import cairosvg
except ImportError:
    cairosvg = None

out = sys.argv[1]
oplog = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
views = json.load(open(os.path.join(out, "views.json")))
bodies = json.load(open(os.path.join(out, "bodies.json")))
status = json.load(open(os.path.join(out, "status.json")))

W, H = 420, 297          # A3 landscape, mm
SCALE = 0.1              # 1:10
ISO_SCALE = 0.07
LINE = 0.35              # visible-line weight on paper, mm


def extents(svg):
    d = " ".join(re.findall(r'd="([^"]*)"', svg))
    nums = [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", d)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), max(xs), min(ys), max(ys)


def place(svg, cx, cy, s):
    """Put a TechDraw view (model mm, centred) at paper point (cx, cy) with scale s."""
    svg = re.sub(r'stroke-width="[^"]*"', f'stroke-width="{LINE / s:.3f}"', svg)
    return f'<g transform="translate({cx:.2f},{cy:.2f}) scale({s})">{svg}</g>'


def paper_box(svg, cx, cy, s):
    x0, x1, y0, y1 = extents(svg)
    return cx + x0 * s, cx + x1 * s, cy + y0 * s, cy + y1 * s


def fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def dim_h(x0, x1, y, text, ext_from=None):
    """Horizontal dimension at paper height y; extension lines up/down to ext_from."""
    parts = []
    if ext_from is not None:
        for x in (x0, x1):
            parts.append(f'<line x1="{x}" y1="{ext_from}" x2="{x}" y2="{y + (1.5 if y > ext_from else -1.5)}" class="ext"/>')
    parts.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" class="dim" marker-start="url(#a)" marker-end="url(#a)"/>')
    parts.append(f'<text x="{(x0 + x1) / 2}" y="{y - 1.2}" class="dt" text-anchor="middle">{text}</text>')
    return "".join(parts)


def dim_v(y0, y1, x, text, ext_from=None):
    parts = []
    if ext_from is not None:
        for y in (y0, y1):
            parts.append(f'<line x1="{ext_from}" y1="{y}" x2="{x + (1.5 if x > ext_from else -1.5)}" y2="{y}" class="ext"/>')
    parts.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" class="dim" marker-start="url(#a)" marker-end="url(#a)"/>')
    xm, ym = x - 1.2, (y0 + y1) / 2
    parts.append(f'<text x="{xm}" y="{ym}" class="dt" text-anchor="middle" transform="rotate(-90 {xm} {ym})">{text}</text>')
    return "".join(parts)


# overall model extents (mm)
bx = [b["world_bbox"] for b in bodies]
X0, Y0, Z0 = min(b[0] for b in bx), min(b[1] for b in bx), min(b[2] for b in bx)
X1, Y1, Z1 = max(b[3] for b in bx), max(b[4] for b in bx), max(b[5] for b in bx)
L, D, Ht = X1 - X0, Y1 - Y0, Z1 - Z0

# layout (third angle: top above front, right side to the right of front)
front_c = (130, 175)
top_c = (130, 175 - (Ht / 2 + D / 2) * SCALE - 22)
right_c = (130 + (L / 2 + D / 2) * SCALE + 22, 175)
iso_c = (335, 75)

g = []
g.append(place(views["Front"], *front_c, SCALE))
g.append(place(views["Top"], *top_c, SCALE))
g.append(place(views["Right"], *right_c, SCALE))
g.append(place(views["Iso"], *iso_c, ISO_SCALE))

fx0, fx1, fy0, fy1 = paper_box(views["Front"], *front_c, SCALE)
tx0, tx1, ty0, ty1 = paper_box(views["Top"], *top_c, SCALE)
rx0, rx1, ry0, ry1 = paper_box(views["Right"], *right_c, SCALE)

# dimensions
g.append(dim_h(fx0, fx1, fy1 + 9, fmt(L), ext_from=fy0))
g.append(dim_v(fy0, fy1, fx0 - 9, fmt(Ht), ext_from=fx0))
g.append(dim_v(ty0, ty1, tx0 - 9, fmt(D), ext_from=tx0))
g.append(dim_h(rx0, rx1, ry1 + 9, fmt(D), ext_from=ry1))

# seat height (top of legs) and leg positions, from the bodies themselves
legs = [b for b in bodies if b["component"] == "Leg"]
if legs:
    leg_top = max(b["world_bbox"][5] for b in legs)
    y_leg_top = fy1 - (leg_top - Z0) * SCALE
    g.append(dim_v(y_leg_top, fy1, fx1 + 9, fmt(leg_top - Z0), ext_from=fx1))
    lx = sorted(b["world_bbox"][0] for b in legs)
    g.append(dim_h(fx0, fx0 + (lx[0] - X0) * SCALE, fy1 + 17, fmt(lx[0] - X0), ext_from=fy1))

labels = [("FRONT", front_c, fy1 + 25), ("TOP", top_c, ty0 - 4), ("RIGHT", right_c, ry1 + 17)]
for name, (cx, _), y in labels:
    g.append(f'<text x="{cx}" y="{y}" class="vl" text-anchor="middle">{name}</text>')
g.append(f'<text x="{iso_c[0]}" y="{iso_c[1] + 42}" class="vl" text-anchor="middle">ISOMETRIC (NTS)</text>')

# cut list: group identical boards (component, size, material)
groups = OrderedDict()
for b in bodies:
    key = (b["component"] or b["id"], tuple(b["size"]), b["material"])
    groups.setdefault(key, []).append(b["id"])
rows = []
for (name, size, mat), ids in groups.items():
    t, w, ln = size
    rows.append({"part": name, "qty": len(ids), "thickness": t, "width": w, "length": ln,
                 "material": mat or "-", "ids": " ".join(ids)})
with open(os.path.join(out, "cutlist.csv"), "w", newline="") as f:
    wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    wtr.writeheader(); wtr.writerows(rows)

tx, ty = 262, 150
cols = [("PART", 0), ("QTY", 34), ("T", 48), ("W", 62), ("L", 78), ("MATERIAL", 96)]
g.append(f'<text x="{tx}" y="{ty - 6}" class="vl">CUT LIST (mm, finished size)</text>')
for name, dx in cols:
    g.append(f'<text x="{tx + dx}" y="{ty}" class="th">{name}</text>')
g.append(f'<line x1="{tx}" y1="{ty + 1.5}" x2="{tx + 148}" y2="{ty + 1.5}" class="thin"/>')
for i, r in enumerate(rows):
    y = ty + 6 + i * 5
    vals = [r["part"], r["qty"], fmt(r["thickness"]), fmt(r["width"]), fmt(r["length"]), r["material"]]
    for (name, dx), v in zip(cols, vals):
        g.append(f'<text x="{tx + dx}" y="{y}" class="td">{v}</text>')

# replay status box
ops = status["ops"]
ok = sum(1 for o in ops if o["status"] == "ok")
sy = ty + 12 + len(rows) * 5
g.append(f'<text x="{tx}" y="{sy}" class="vl">REPLAY</text>')
g.append(f'<text x="{tx}" y="{sy + 5}" class="td">{ok}/{len(ops)} ops ok, {status["total_ms"]} ms</text>')
for i, o in enumerate([o for o in ops if o["status"] != "ok"][:3]):
    g.append(f'<text x="{tx}" y="{sy + 10 + i * 4.5}" class="err">FAILED {o["id"]}: {o["message"][:70]}</text>')

# title block
title = oplog.get("name", "Untitled")
tb = f'''
<rect x="262" y="252" width="148" height="35" class="thin"/>
<line x1="262" y1="266" x2="410" y2="266" class="thin"/>
<line x1="336" y1="266" x2="336" y2="287" class="thin"/>
<text x="266" y="262" class="tt">{title}</text>
<text x="266" y="273" class="td">SCALE 1:10 (A3)</text>
<text x="266" y="279" class="td">THIRD-ANGLE PROJECTION</text>
<text x="266" y="285" class="td">UNITS: mm</text>
<text x="340" y="273" class="td">SOURCE: {status["oplog"]}</text>
<text x="340" y="279" class="td">GENERATED FROM OP LOG</text>
<text x="340" y="285" class="td">FreeCAD headless replay</text>
'''

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">
<defs>
 <marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
  <path d="M 0 2 L 5 5 L 0 8" fill="none" stroke="#000" stroke-width="1.2"/></marker>
 <style>
  .dim {{ stroke:#000; stroke-width:0.18; fill:none }}
  .ext {{ stroke:#000; stroke-width:0.13; fill:none }}
  .thin {{ stroke:#000; stroke-width:0.25; fill:none }}
  text {{ font-family: 'DejaVu Sans', Helvetica, sans-serif; fill:#000 }}
  .dt {{ font-size:2.6px }}
  .vl {{ font-size:3.2px; font-weight:bold; letter-spacing:0.3px }}
  .th {{ font-size:2.6px; font-weight:bold }}
  .td {{ font-size:2.6px }}
  .tt {{ font-size:5px; font-weight:bold }}
  .err {{ font-size:2.4px; fill:#b00020 }}
 </style>
</defs>
<rect width="{W}" height="{H}" fill="#fff"/>
<rect x="10" y="10" width="{W - 20}" height="{H - 20}" fill="none" stroke="#000" stroke-width="0.5"/>
{"".join(g)}
{tb}
</svg>'''

with open(os.path.join(out, "drawing.svg"), "w") as f:
    f.write(svg)
if cairosvg:
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=os.path.join(out, "drawing.pdf"))
    cairosvg.svg2png(bytestring=svg.encode(), write_to=os.path.join(out, "drawing.png"), output_width=2400)
print("DRAWING: wrote drawing.svg/.pdf/.png and cutlist.csv")
