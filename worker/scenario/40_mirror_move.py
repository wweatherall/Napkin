"""5. move one side of the mirror group: the other follows, reflected (A11b) (T76)."""
from scenario.context import ok, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    step = ctx.step

    # 5. move one side of the mirror group: the other follows, reflected (A11b)
    MOVE_L = {"id": "s5", "type": "move", "targets": ["left"], "vector": [-50, 0, 0]}
    step("move the left side out 50", FIX + [MOVE_L], lambda st, a, b: [
        ok(st, 1), only(a, b, {"left", "right"}),
        ("left at x -50", b["boards"]["left"]["box"][0] == -50, b["boards"]["left"]["box"]),
        ("right followed to x 650", b["boards"]["right"]["box"][3] == 650, b["boards"]["right"]["box"])])

    # 5b. move the mirrored copy instead: its original moves the reflected way
    MOVE_R = {"id": "s5b", "type": "move", "targets": ["right"], "vector": [30, 0, 0]}
    step("move the right side (the mirror) out 30", FIX + [MOVE_R], lambda st, a, b: [
        ok(st, 1), only(a, b, {"left", "right"}),
        ("right at x 612..630", b["boards"]["right"]["box"][0::3] == (612, 630), b["boards"]["right"]["box"]),
        ("left moved the other way, to x -30", b["boards"]["left"]["box"][0] == -30, b["boards"]["left"]["box"])])
