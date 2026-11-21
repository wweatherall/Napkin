"""Shop Sketch's wood library (T15, M03): one table, written out as FreeCAD material cards (.FCMat) where FreeCAD
looks for user materials, and as materials.json for the viewport.

Numbers: USDA Forest Products Laboratory, Wood Handbook, Centennial ed. (GTR-190, 2010), chapter 5 (Kretschmann):
Table 5-3a (12 % moisture content: specific gravity, modulus of elasticity, side hardness), Table 5-1 (elastic
ratios) and Table 5-2 (Poisson's ratios). A US federal publication. The 2021 edition (GTR-282) could not be fetched
when this was written (server error); recheck against it.
  Density at 12 % MC = specific gravity x 1.12 x 1000 kg/m^3 (the table's specific gravity is oven-dry weight over
  volume at 12 % MC). E_L = the table's MOE x 1.1 (Table 5-1, footnote a: the bending MOE includes shear deflection).
  Orthotropic axes: X = along the grain (L), Y = radial (R), Z = tangential (T).
Textures: ambientCG (https://ambientcg.com), CC0. Colour maps at 1K; size_mm = the asset's stated real size.
End grain: <key>_end.jpg, a band of rings cropped from ambientCG TreeEnd002 (oak, ash), TreeEnd004 (other
hardwoods) or TreeEnd005 (softwoods), tinted to the species. The band runs across the board's width; the viewport
mirrors it at each repeat so the seams meet (END_SIZE_MM wide, about 18 cm of a 45 cm log).
"""
import json
import os
import shutil
import uuid

# key: (name, handbook row, SG, MOE MPa, side hardness N, (ET/EL, ER/EL, GLR/EL, GLT/EL, GRT/EL), (muLR, muLT, muRT),
#       texture, grain along the texture's "u" or "v", texture size mm, average colour of the texture)
SPECIES = {
    "white-oak": ("White Oak", "Oak, white", 0.68, 12300, 6000, (0.072, 0.163, 0.086, None, None), (0.369, 0.428, 0.618),
                  "Wood022", "u", 600, (0.809, 0.668, 0.456)),
    "red-oak": ("Red Oak", "Oak, northern red (ratios: Oak, red)", 0.63, 12500, 5700, (0.082, 0.154, 0.089, 0.081, None),
                (0.350, 0.448, 0.560), "Wood050", "u", 800, (0.835, 0.636, 0.493)),
    "hard-maple": ("Hard Maple", "Maple, sugar", 0.63, 12600, 6400, (0.065, 0.132, 0.111, 0.063, None), (0.424, 0.476, 0.774),
                   "Wood095", "u", 600, (0.803, 0.613, 0.434)),
    "black-cherry": ("Black Cherry", "Cherry, black", 0.50, 10300, 4200, (0.086, 0.197, 0.147, 0.097, None),
                     (0.392, 0.428, 0.695), "Wood023", "u", 600, (0.671, 0.439, 0.197)),
    "black-walnut": ("Black Walnut", "Walnut, black", 0.55, 11600, 4500, (0.056, 0.106, 0.085, 0.062, 0.021),
                     (0.495, 0.632, 0.718), "Wood026", "u", 600, (0.408, 0.222, 0.091)),
    "white-ash": ("White Ash", "Ash, white", 0.60, 12000, 5900, (0.080, 0.125, 0.109, 0.077, None), (0.371, 0.440, 0.684),
                  "Wood048", "u", 800, (0.690, 0.563, 0.397)),
    "yellow-birch": ("Yellow Birch", "Birch, yellow", 0.62, 13900, 5600, (0.050, 0.078, 0.074, 0.068, 0.017),
                     (0.426, 0.451, 0.697), "Wood068", "u", 400, (0.676, 0.540, 0.424)),
    "poplar": ("Poplar (Yellow-poplar)", "Yellow-poplar", 0.42, 10900, 2400, (0.043, 0.092, 0.075, 0.069, 0.011),
               (0.318, 0.392, 0.703), "Wood058", "v", 400, (0.628, 0.475, 0.357)),
    "basswood": ("Basswood", "Basswood, American", 0.37, 10100, 1800, (0.027, 0.066, 0.056, 0.046, None),
                 (0.364, 0.406, 0.912), "Wood017", "u", 600, (0.696, 0.611, 0.482)),
    "douglas-fir": ("Douglas Fir", "Douglas-fir, Coast", 0.48, 13400, 3200, (0.050, 0.068, 0.064, 0.078, 0.007),
                    (0.292, 0.449, 0.390), "Wood052", "u", 800, (0.830, 0.494, 0.300)),
    "eastern-white-pine": ("Eastern White Pine", "Pine, eastern white (no elastic ratios in Table 5-1)", 0.35, 8500, 1700,
                           None, None, "Wood096", "v", 500, (0.705, 0.617, 0.520)),
    "southern-yellow-pine": ("Southern Yellow Pine (Loblolly)", "Pine, loblolly", 0.51, 12300, 3100,
                             (0.078, 0.113, 0.082, 0.081, 0.013), (0.328, 0.292, 0.382), "Wood092", "v", 800,
                             (0.689, 0.451, 0.248)),
}

END_SIZE_MM = 175

M_FATHER = "9cdda8b6-b606-4778-8f13-3934d8668e67"
M_DENSITY = "454661e5-265b-4320-8e6f-fcf6223ac3af"
M_ISO = "f6f9e48c-b116-4e82-ad7f-3659a9219c50"
M_ORTHO = "b19ccc6b-a431-418e-91c2-0ac8c649d146"
M_HARDNESS = "3d1a6141-d032-4d82-8bb5-a8f339fff8ad"
M_TEXTURE = "bbdcc65b-67ca-489c-bd5c-a36e33d1c160"
WOOD_PARENT = "1850ac4a-0df2-43cd-9934-e59e95b9526f"     # FreeCAD's own "Wood" card
SOURCE = "USDA FPL Wood Handbook GTR-190 (2010), ch. 5, Tables 5-1, 5-2, 5-3a, 12% MC"


def material_uuid(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "shopsketch:material:" + key))


def card_text(key, texture_path):
    name, row, sg, moe, hard, ratios, mu, tex, grain, size, col = SPECIES[key]
    el = moe * 1.1
    lines = ["---", "# Written by Shop Sketch (worker/materials.py); edits here are overwritten.", "General:",
             f'  UUID: "{material_uuid(key)}"', f'  Name: "{name}"', '  Author: "Shop Sketch"',
             f'  License: "Values: US federal work (public domain). Texture: ambientCG {tex}, CC0."',
             f'  Description: "{row}. {SOURCE}. Orthotropic axes: X along the grain (L), Y radial (R), Z tangential (T)."',
             "Inherits:", "  Wood:", f'    UUID: "{WOOD_PARENT}"',
             "Models:", "  Father:", f"    UUID: '{M_FATHER}'", '    Father: "Wood"',
             "  Density:", f"    UUID: '{M_DENSITY}'", f'    Density: "{round(sg * 1120)} kg/m^3"',
             "  Hardness:", f"    UUID: '{M_HARDNESS}'", f'    Hardness: "{hard}"', '    HardnessUnits: "Janka side hardness, N"']
    if ratios:
        et, er, glr, glt, grt = ratios
        mlr, mlt, mrt = mu
        lines += ["  OrthotropicLinearElastic:", f"    UUID: '{M_ORTHO}'",
                  f'    YoungsModulusX: "{el:.0f} MPa"', f'    YoungsModulusY: "{el * er:.0f} MPa"',
                  f'    YoungsModulusZ: "{el * et:.0f} MPa"',
                  f'    PoissonRatioXY: "{mlr}"', f'    PoissonRatioXZ: "{mlt}"', f'    PoissonRatioYZ: "{mrt}"',
                  f'    ShearModulusXY: "{el * glr:.0f} MPa"']
        if glt is not None:
            lines.append(f'    ShearModulusXZ: "{el * glt:.0f} MPa"')
        if grt is not None:
            lines.append(f'    ShearModulusYZ: "{el * grt:.0f} MPa"')
    else:
        lines += ["  IsotropicLinearElastic:", f"    UUID: '{M_ISO}'", f'    YoungsModulus: "{el:.0f} MPa"']
    lines += ["AppearanceModels:", "  TextureRendering:", f"    UUID: '{M_TEXTURE}'",
              f'    DiffuseColor: "({col[0]:.4f}, {col[1]:.4f}, {col[2]:.4f}, 1.0)"',
              f'    TexturePath: "{texture_path}"', f'    TextureScaling: "{size / 1000:.3f}"']
    return "\n".join(lines) + "\n"


def library():
    """What the viewport needs: name, uuid, colour, texture, which way its grain runs, its real size."""
    return [{"key": k, "name": v[0], "uuid": material_uuid(k), "color": list(v[10]), "texture": v[7] + ".jpg",
             "grain": v[8], "size_mm": v[9], "end_texture": k + "_end.jpg", "end_size_mm": END_SIZE_MM}
            for k, v in SPECIES.items()]


def install(user_dir, textures_src):
    """Write the cards (and copy the textures) into FreeCAD's user material folder, under "Shop Sketch".
    Returns the number of files changed (0 when everything is already current)."""
    dest = os.path.join(user_dir, "Shop Sketch")
    tdest = os.path.join(dest, "textures")
    os.makedirs(tdest, exist_ok=True)
    changed = 0
    for k, v in SPECIES.items():
        tpath = os.path.join(tdest, v[7] + ".jpg")
        for name in (v[7] + ".jpg", k + "_end.jpg"):          # end grain too, for renders (Blender)
            src, dst = os.path.join(textures_src, name), os.path.join(tdest, name)
            if os.path.exists(src) and (not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src)):
                shutil.copyfile(src, dst)
                changed += 1
        text = card_text(k, tpath)
        cpath = os.path.join(dest, v[0] + ".FCMat")
        if not os.path.exists(cpath) or open(cpath, encoding="utf-8").read() != text:
            with open(cpath, "w", encoding="utf-8") as f:
                f.write(text)
            changed += 1
    return changed


def write_library(path):
    with open(path, "w") as f:
        json.dump(library(), f, indent=1)
