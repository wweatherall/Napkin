#!/usr/bin/env python3
"""The hopper's settings file (P78): read, checked value by value, and never able to stop the hopper."""
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.pop("HOPPER_SETTINGS", None)
import hopper_settings as hs

RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    if not ok or VERBOSE:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {detail}"))


tmp = tempfile.mkdtemp(prefix="hopper-settings-")


def write(text):
    path = os.path.join(tmp, "s.toml")
    with open(path, "w") as f:
        f.write(text)
    return path


s, problems = hs.read(hs.PATH)
check("the shipped file reads with no problems", problems == [], problems)
check("the shipped file holds the built-in values (its comment says so)", s == hs.DEFAULTS, s)

s, problems = hs.read("")
check("no file named: the built-in settings, no problem", s == hs.DEFAULTS and problems == [])
s, problems = hs.read(os.path.join(tmp, "missing.toml"))
check("a missing file: the built-in settings, one problem", s == hs.DEFAULTS and len(problems) == 1, problems)

s, problems = hs.read(write("[quota_floor]\ngemini = 0.10\ncodex = \n"))
check("invalid TOML: the built-in settings, and the problem says it isn't valid TOML",
      s == hs.DEFAULTS and "isn't valid TOML" in problems[0], problems)

s, problems = hs.read(write('[quota_floor]\ngemini = "10%"\nclaude = 0.30\n'))
check("a floor in quotes: that one falls back, the others are read",
      s["quota_floor"]["gemini"] == 0.10 and s["quota_floor"]["claude"] == 0.30, s["quota_floor"])
check("... and the problem shows the example form", any("like 0.10" in p for p in problems), problems)
s, problems = hs.read(write("[quota_floor]\ncodex = 10\n"))
check("a floor over 1 (10 for 10%) is refused", s["quota_floor"]["codex"] == 0.10 and problems, problems)

s, problems = hs.read(write('[routes]\neither = ["codex", "claude:opus"]\ncodex = ["sol"]\n'))
check("a route is read as (agent, model)", s["routes"]["either"] == [("codex", None), ("claude", "opus")], s["routes"])
check("an unknown agent in a route: that route falls back, with a problem",
      s["routes"]["codex"] == hs.DEFAULTS["routes"]["codex"] and any("'sol'" in p for p in problems), problems)

s, problems = hs.read(write('[models]\ncodex = "gpt-6.2-astra"\n[quotas]\nx = 1\n'))
check("a model is read", s["models"]["codex"] == "gpt-6.2-astra", s["models"])
check("a misspelt section is reported", any("[quotas]" in p for p in problems), problems)

os.environ["HOPPER_SETTINGS"] = write("[quota_floor]\ngemini = bad\n")
err = io.StringIO()
hs.load(out=err); hs.load(out=err)
check("load reports a problem once, not every poll", err.getvalue().count("hopper settings:") == 1, err.getvalue())

os.environ["HOPPER_SETTINGS"] = write('[routes]\neither = ["claude:haiku"]\n[quota_floor]\nclaude = 0.5\n')
import job
check("the hopper routes by the file", job.route_for("either", {}) == ("claude", "haiku"))
import launch
os.environ["HOPPER_SETTINGS"] = write('[models]\ncodex = "gpt-6.2-astra"\n')
check("the launcher's default model comes from the file", launch.default_model("codex") == "gpt-6.2-astra")
os.environ["HOPPER_SETTINGS"] = ""
check("with no file, the launcher keeps the built-in model", launch.default_model("codex") == "gpt-6.2-sol")

print(f"HOPPER SETTINGS TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
sys.exit(0 if all(RESULTS) else 1)
