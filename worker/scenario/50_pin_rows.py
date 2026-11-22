"""6. move the whole pin-hole row up 64 (T76)."""
from scenario.context import ok, only

requires = ()

def run(ctx):
    FIX = ctx.FIX
    PIN = ctx.PIN
    fix_with = ctx.fix_with
    step = ctx.step

    # 6. move the whole pin-hole row up 64
    MOVE_PINS = {"id": "s6", "type": "move", "targets": [], "cut": {"body": "left", "op": "p_pin"}, "vector": [0, 0, 64], "copy": False}
    step("move the pin-hole row up 64", FIX + [MOVE_PINS], lambda st, a, b: [
        ok(st, 1), only(a, b, {"left", "right"}),
        ("same volume (still five holes)", b["boards"]["left"]["vol"] == a["boards"]["left"]["vol"], b["boards"]["left"]["vol"]),
        ("the mirror's holes still match", b["boards"]["right"]["vol"] == b["boards"]["left"]["vol"], b["boards"]["right"]["vol"])])

    # 7. retype the pin count right after making it (an amend of a fixture op)
    step("retype the pin row as 8 copies", fix_with("pins", count=8), lambda st, a, b: [
        ("accepted", all(e["status"] == "ok" for e in st), [e for e in st if e["status"] != "ok"]),
        ("nine holes in the left side", abs(b["boards"]["left"]["vol"] - (18 * 400 * 720 - 9 * PIN)) < 0.1, b["boards"]["left"]["vol"]),
        ("and in the right", b["boards"]["right"]["vol"] == b["boards"]["left"]["vol"], b["boards"]["right"]["vol"])])

    # 8. a move that would take the holes off the board is refused, and leaves the model alone
    OFF = {"id": "s8", "type": "move", "targets": [], "cut": {"body": "left", "op": "p_pin"}, "vector": [0, 5000, 0], "copy": False}
    step("move the pins off the board (refused)", FIX + [OFF], lambda st, a, b: [
        ("refused", st[-1]["status"] == "failed", st[-1]), only(a, b, set())])
