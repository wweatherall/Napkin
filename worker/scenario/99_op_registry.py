"""The op registry: Model's op types are its op_<type> methods, its mixins every top-level *Actions class
(model.action_mixins). Pins today's fourteen types; a helper like move_cut is not an op."""
from model import Model, action_mixins

requires = ()

TYPES = {"line", "circle", "rect", "push_pull", "mirror", "make_component", "move", "set_material", "detach", "make_unique",
         "make_assembly", "turn_grain", "property_edit", "hide", "delete"}
MIXINS = {"LineActions", "CircleActions", "AssemblyActions", "DeleteActions", "MirrorActions", "MoveActions", "PaintActions", "PushActions",
          "VisibilityActions"}


def run(ctx):
    ctx.check("op registry: the op types are the fourteen op_ methods", set(Model.HANDLERS) == TYPES,
              sorted(set(Model.HANDLERS) ^ TYPES))
    ctx.check("op registry: every *Actions mixin joins Model", {c.__name__ for c in action_mixins()} == MIXINS
              and all(c in Model.__mro__ for c in action_mixins()), [c.__name__ for c in Model.__mro__])
    ctx.step("op registry: a helper's name is not an op type", ctx.FIX + [{"id": "mc", "type": "move_cut"}],
             lambda st, a, b: [("rejected as unknown", st[-1]["status"] != "ok" and "unknown op type" in
                                st[-1].get("message", ""), st[-1])])
