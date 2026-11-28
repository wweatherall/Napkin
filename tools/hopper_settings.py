#!/usr/bin/env python3
"""The hopper's settings (P78): read tools/hopper_settings.toml, checked value by value against the built-in defaults.

  python3 tools/hopper_settings.py      print the settings in use, and any problem with the file

A missing file, a TOML mistake or a bad value never stops the hopper: each problem is reported once and that value
falls back to its default below (which are the values the file ships with). HOPPER_SETTINGS names another file;
set it to "" to use only the defaults (the tests do, so William's edits can't change their answers)."""
import copy
import os
import sys

try:
    import tomllib
except ImportError:          # Python before 3.11: defaults only
    tomllib = None

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "hopper_settings.toml")
AGENTS = ("gemini", "codex", "claude")
DEFAULTS = {
    "quota_floor": {"gemini": 0.10, "codex": 0.10, "claude": 0.25},
    "quota": {"gemini_fresh_minutes": 30},
    "routes": {"either": [("gemini", None), ("codex", None), ("claude", "sonnet")],
               "codex": [("codex", None), ("claude", "opus")],
               "gemini": [("gemini", None)],
               "claude": [("claude", None)]},
    "models": {"gemini": "gemini-4-hydrogen-medium", "codex": "gpt-6.2-sol", "claude": "sonnet", "integrator": "opus"},
}
_reported = set()


def _route(items):
    """["gemini", "claude:opus"] -> [("gemini", None), ("claude", "opus")]; ValueError on anything else."""
    if not isinstance(items, list) or not items:
        raise ValueError("should be a list like [\"gemini\", \"claude:sonnet\"]")
    out = []
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{item!r} should be in double quotes")
        agent, _, model = item.partition(":")
        if agent not in AGENTS:
            raise ValueError(f"{agent!r} isn't an agent (use {', '.join(AGENTS)})")
        out.append((agent, model or None))
    return out


def read(path=None):
    """(settings, [problems]): the file's values where valid, the defaults everywhere else."""
    path = os.environ.get("HOPPER_SETTINGS", PATH) if path is None else path
    s = copy.deepcopy(DEFAULTS)
    if not path:
        return s, []
    if tomllib is None:
        return s, ["this Python has no tomllib: using the built-in settings"]
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError:
        return s, [f"{os.path.basename(path)} is missing: using the built-in settings"]
    except tomllib.TOMLDecodeError as e:
        return s, [f"{os.path.basename(path)} isn't valid TOML ({e}): using the built-in settings"]
    problems = []
    for name, value in raw.get("quota_floor", {}).items():
        if name not in AGENTS:
            problems.append(f"[quota_floor] {name}: not an agent (use {', '.join(AGENTS)})")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            problems.append(f"[quota_floor] {name} = {value!r}: should be a bare number from 0 to 1, like 0.10")
        else:
            s["quota_floor"][name] = float(value)
    minutes = raw.get("quota", {}).get("gemini_fresh_minutes", s["quota"]["gemini_fresh_minutes"])
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes <= 0:
        problems.append(f"[quota] gemini_fresh_minutes = {minutes!r}: should be a bare number of minutes, like 30")
    else:
        s["quota"]["gemini_fresh_minutes"] = minutes
    for name, items in raw.get("routes", {}).items():
        try:
            s["routes"][name] = _route(items)
        except ValueError as e:
            problems.append(f"[routes] {name}: {e}")
    for name, model in raw.get("models", {}).items():
        if name not in AGENTS + ("integrator",):
            problems.append(f"[models] {name}: not an agent")
        elif not isinstance(model, str) or not model:
            problems.append(f"[models] {name} = {model!r}: should be a model name in double quotes")
        else:
            s["models"][name] = model
    for section in raw:
        if section not in DEFAULTS:
            problems.append(f"[{section}]: not a section the hopper reads ({', '.join(DEFAULTS)})")
    return s, problems


def load(out=None):
    """The settings in use; each new problem is printed once (to out, default stderr) so the hopper's window shows it."""
    s, problems = read()
    for p in problems:
        if p not in _reported:
            _reported.add(p)
            print(f"hopper settings: {p}", file=out or sys.stderr, flush=True)
    return s


def main():
    s, problems = read()
    for p in problems:
        print("problem: " + p)
    print("quota floors: " + ", ".join(f"{a} {v:.0%}" for a, v in s["quota_floor"].items()))
    print(f"a Gemini reading counts for {s['quota']['gemini_fresh_minutes']} min")
    for name, route in s["routes"].items():
        print(f"For: {name}: " + " then ".join(a + (f" ({m})" if m else f" ({s['models'][a]})") for a, m in route))
    print("models: " + ", ".join(f"{a} {m}" for a, m in s["models"].items()))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
