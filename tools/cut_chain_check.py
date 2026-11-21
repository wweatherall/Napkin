# Q18: does this FreeCAD slow down along a chain of Part::Cut features?
import FreeCAD as App, Part, time
V = App.Vector
d = App.newDocument("chain")
tip = d.addObject("Part::Box", "Board"); tip.Length = 1200; tip.Width = 600; tip.Height = 18
per = []
for k in range(24):
    b = d.addObject("Part::Box", "Hole"); b.Length = b.Width = 20; b.Height = 18
    b.Placement.Base = V(50 + (k % 8) * 140, 50 + (k // 8) * 140, 0)
    c = d.addObject("Part::Cut", "Cut"); c.Base = tip; c.Tool = b; tip = c
    t = time.perf_counter(); d.recompute(); per.append((time.perf_counter() - t) * 1000)
print(f"RESULT FreeCAD {'.'.join(App.Version()[:3])}: 1st cut {per[0]:.0f} ms, 12th {per[11]:.0f} ms, 24th {per[23]:.0f} ms")
print("RESULT (the dev build Claude tested: 1st 9 ms, 24th 739 ms)")
