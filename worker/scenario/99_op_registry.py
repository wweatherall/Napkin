"""The op registry: Model's op types are its op_<type> methods, its mixins every top-level *Actions class
(model.action_mixins). Pins today's nineteen types; a helper like move_cut is not an op."""
from model import Model, action_mixins
from scenario.context import ok

requires = ()

TYPES = {"arc", "line", "circle", "polygon", "rect", "new_board", "push_pull", "resize_stock", "mirror", "make_component", "move", "set_material", "detach", "make_unique",
         "make_assembly", "turn_grain", "property_edit", "fit", "unfit", "hide", "delete"}
MIXINS = {"ArcActions", "LineActions", "CircleActions", "PolygonActions", "AssemblyActions", "DeleteActions", "MirrorActions", "MoveActions", "PaintActions", "PushActions",
          "VisibilityActions"}


def run(ctx):
    ctx.check("op registry: the op types are the twenty-one op_ methods", set(Model.HANDLERS) == TYPES,
              sorted(set(Model.HANDLERS) ^ TYPES))
    ctx.check("op registry: every *Actions mixin joins Model", {c.__name__ for c in action_mixins()} == MIXINS
              and all(c in Model.__mro__ for c in action_mixins()), [c.__name__ for c in Model.__mro__])
    ctx.step("op registry: a helper's name is not an op type", ctx.FIX + [{"id": "mc", "type": "move_cut"}],
             lambda st, a, b: [("rejected as unknown", st[-1]["status"] != "ok" and "unknown op type" in
                                st[-1].get("message", ""), st[-1])])


    plane = dict(origin=[1000, 1000, 0], normal=[0, 0, 1])
    profiles = [
        dict(id="profile_rect", type="rect", plane=plane, size=[100, 50]),
        dict(id="profile_circle", type="circle", plane=plane, radius=25),
        dict(id="profile_polygon", type="polygon", plane=plane, radius=25, sides=5),
        dict(id="profile_line", type="line", plane=plane, end=[1100, 1000, 0]),
        dict(id="profile_arc", type="arc", plane=plane, mid=[1050, 1040, 0], end=[1100, 1000, 0]),
    ]
    ids = [op["id"] for op in profiles]
    ops = ctx.FIX + profiles
    model = ctx.S.model
    ctx.S.sync(ops)
    origins = {i: model.drawing(i).Placement.Base for i in ids}
    move = dict(id="move_profiles", type="move", targets=ids, vector=[50, 0, 20], selection=True)
    ctx.S.sync(ops + [move])
    ctx.check("Move translates all five native drawing types", ok(ctx.S.status(), 1)[1]
              and all(tuple(model.drawing(i).Placement.Base - origins[i]) == (50, 0, 20) for i in ids),
              ctx.S.status()[-1])
    delete = dict(id="delete_profiles", type="delete", targets=ids)
    ctx.S.sync(ops + [move, delete])
    ctx.check("Delete removes all five native drawing types in one op", ok(ctx.S.status(), 1)[1]
              and all(model.drawing(i) is None for i in ids), ctx.S.status()[-1])
    ctx.S.sync(ops + [move])
    ctx.check("Undo restores native drawings at their moved placements",
              all(tuple(model.drawing(i).Placement.Base - origins[i]) == (50, 0, 20) for i in ids))
    ctx.S.sync(ops)
    ctx.check("Undo restores each native drawing's original placement",
              all(model.drawing(i).Placement.Base == origins[i] for i in ids))
    ctx.S.sync(ctx.FIX)


    base = [1000, 1000, 0]
    b, c = [1100, 1000, 0], [1100, 1100, 0]
    chain = [
        dict(id="edge_a", type="line", plane=plane, end=b),
        dict(id="edge_b", type="line", plane=dict(plane, origin=b), end=c),
        dict(id="edge_c", type="line", plane=dict(plane, origin=c), end=base, outline=[base, b, c]),
    ]
    ops = ctx.FIX + chain
    ctx.S.sync(ops)
    ctx.check("A closed line chain has a native derived outline", model.rect_obj("edge_c") is not None)
    ctx.S.sync(ops + [dict(id="move_edge", type="move", targets=["edge_a"], vector=[0, 0, 50])])
    ctx.check("Moving an edge removes the stale derived outline", model.rect_obj("edge_c") is None)
    ctx.S.sync(ops)
    ctx.check("Undo restores the outline along with its edge", model.rect_obj("edge_c") is not None)
    ctx.S.sync(ctx.FIX)
