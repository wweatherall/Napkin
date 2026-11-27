#!/usr/bin/env python3
"""Check tools/protocol_map.py extraction, --check rules, fallback builder, and pre-commit hook (H169)."""
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import protocol_map as pm

ROOT = Path(__file__).resolve().parent.parent
RESULTS = []
VERBOSE = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]


def check(name, condition, detail=""):
    RESULTS.append(bool(condition))
    if not condition or VERBOSE:
        print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  {detail}"))


def run(root, *args):
    return subprocess.run(args, cwd=root, text=True, capture_output=True)


# 1. Real repository passes --check
real = run(ROOT, sys.executable, "tools/protocol_map.py", "--check")
check("real docs/protocol.md passes --check", real.returncode == 0, real.stderr)


# 2. Throwaway repository tests covering every check and fallback
MINI_SERVE = '''"""Minimal serve.py for testing."""
PROTOCOL_VERSION = 7

def helper_dict(seq):
    return {"ok": True, "cmd": "alpha", "seq": seq, "extra": 1}

def opaque_builder(req):
    return build_dynamic(req)

def serve(port):
    def send(conn, obj):
        pass

    def notify():
        send(None, {"ok": True, "cmd": "ping", "ts": 1})

    def handle(conn, line):
        req = {}
        cmd = req.get("cmd")
        seq = req.get("seq")
        if cmd == "hello":
            send(conn, {"ok": True, "cmd": "hello", "seq": seq, "protocol": PROTOCOL_VERSION})
            return None
        if cmd == "alpha":
            resp = helper_dict(seq)
            _ = req.get("flag")
        elif cmd == "beta":
            resp = opaque_builder(req)
            _ = req["item"]
        send(conn, resp)
        return None
'''

MINI_GD = '''extends Node

func _on_alpha() -> void:
\tpass
'''

MINI_DOC = f"""# Protocol

Sources: [worker/serve.py](../worker/serve.py):`serve.handle`, `helper_dict`; [viewport/main.gd](../viewport/main.gd):`_on_alpha`.

## Commands and events

{pm.START}

stale

{pm.END}

### `hello`

```json
{{"cmd":"hello"}}
{{"ok":true,"cmd":"hello","seq":null,"protocol":7}}
```

### `alpha`

```json
{{"cmd":"alpha","flag":true,"seq":1}}
{{"ok":true,"cmd":"alpha","seq":1,"extra":1}}
```

### `beta`

```json
{{"cmd":"beta","item":"x"}}
```

### `ping`

```json
{{"ok":true,"cmd":"ping","ts":1}}
```

Producer/consumer: [worker/serve.py](../worker/serve.py):`serve.notify`; [viewport/main.gd](../viewport/main.gd):`_on_alpha`.
"""

with TemporaryDirectory(prefix="proto-map-test-") as folder:
    root = Path(folder)
    for d in ("worker", "viewport", "docs", "tools", ".githooks"):
        (root / d).mkdir(parents=True)

    (root / "worker/serve.py").write_text(MINI_SERVE)
    (root / "viewport/main.gd").write_text(MINI_GD)
    doc = root / "docs/protocol.md"
    doc.write_text(MINI_DOC)
    shutil.copy(ROOT / "tools/protocol_map.py", root / "tools/protocol_map.py")
    shutil.copy(ROOT / ".githooks/pre-commit", root / ".githooks/pre-commit")

    # Stale section fails
    stale = run(root, sys.executable, "tools/protocol_map.py", "--check")
    check("--check fails on stale section", stale.returncode == 1 and "out of date" in stale.stderr, stale.stderr)

    # Rebuild is idempotent and preserves surrounding text
    r1 = run(root, sys.executable, "tools/protocol_map.py")
    t1 = doc.read_text()
    r2 = run(root, sys.executable, "tools/protocol_map.py")
    t2 = doc.read_text()
    check(
        "rebuild is idempotent and preserves surrounding text",
        r1.returncode == 0 and r2.returncode == 0 and t1 == t2 and t1.startswith("# Protocol\n"),
        t1,
    )

    # Same-file helper dict and opaque builder fallback
    check(
        "same-file helper dict keys extracted and opaque helper listed without dropping cmd",
        "| `alpha` |" in t1 and "`extra`" in t1 and "| `beta` |" in t1 and "reply: built by `opaque_builder`" in t1,
        t1,
    )

    clean = run(root, sys.executable, "tools/protocol_map.py", "--check")
    check("--check passes on rebuilt throwaway doc", clean.returncode == 0, clean.stderr)

    # Missing ### section for code command
    saved = doc.read_text()
    doc.write_text(saved.replace("### `ping`\n", "### `renamed_ping`\n"))
    sec_fail = run(root, sys.executable, "tools/protocol_map.py", "--check")
    check(
        "--check fails on missing code section and extra doc section",
        sec_fail.returncode == 1 and "`ping`" in sec_fail.stderr and "`renamed_ping`" in sec_fail.stderr,
        sec_fail.stderr,
    )
    doc.write_text(saved)

    # Missing file:function in Sources / Producer/consumer
    doc.write_text(saved.replace("`_on_alpha`", "`_missing_fn`"))
    ref_fail = run(root, sys.executable, "tools/protocol_map.py", "--check")
    check(
        "--check fails on missing .gd function reference",
        ref_fail.returncode == 1 and "_missing_fn" in ref_fail.stderr,
        ref_fail.stderr,
    )
    doc.write_text(saved)

    doc.write_text(saved.replace("`serve.notify`", "`serve.no_such_nested`"))
    pyref_fail = run(root, sys.executable, "tools/protocol_map.py", "--check")
    check(
        "--check fails on missing nested .py function reference",
        pyref_fail.returncode == 1 and "serve.no_such_nested" in pyref_fail.stderr,
        pyref_fail.stderr,
    )
    doc.write_text(saved)

    # Invalid JSON example
    doc.write_text(saved.replace('{"cmd":"hello"}', '{"cmd":"hello"'))
    json_fail = run(root, sys.executable, "tools/protocol_map.py", "--check")
    check(
        "--check fails on unparseable JSON example",
        json_fail.returncode == 1 and "invalid JSON" in json_fail.stderr,
        json_fail.stderr,
    )
    doc.write_text(saved)

    # Extra key not in code
    doc.write_text(saved.replace('{"cmd":"alpha","flag":true,"seq":1}', '{"cmd":"alpha","bogus":1}'))
    key_fail = run(root, sys.executable, "tools/protocol_map.py", "--check")
    check(
        "--check fails when example key is not in code",
        key_fail.returncode == 1 and "bogus" in key_fail.stderr,
        key_fail.stderr,
    )
    doc.write_text(saved)

    # Wrong hello protocol version
    doc.write_text(saved.replace('"protocol":7', '"protocol":3'))
    ver_fail = run(root, sys.executable, "tools/protocol_map.py", "--check")
    check(
        "--check fails when hello protocol differs from PROTOCOL_VERSION",
        ver_fail.returncode == 1 and "protocol=3" in ver_fail.stderr,
        ver_fail.stderr,
    )
    doc.write_text(saved)

    # Pre-commit hook: rebuilds & stages docs/protocol.md, refuses bad doc
    run(root, "git", "init")
    run(root, "git", "config", "user.email", "test@example.invalid")
    run(root, "git", "config", "user.name", "Protocol Map Test")
    run(root, "git", "add", ".")
    c1 = run(root, "git", "-c", "core.hooksPath=.githooks", "commit", "-m", "init")
    check("pre-commit succeeds on valid protocol doc", c1.returncode == 0, c1.stdout + c1.stderr)

    (root / "worker/serve.py").write_text(MINI_SERVE.replace('"extra": 1', '"extra": 1, "added": 2'))
    run(root, "git", "add", "worker/serve.py")
    c2 = run(root, "git", "-c", "core.hooksPath=.githooks", "commit", "-m", "update serve")
    check(
        "pre-commit rebuilds and stages docs/protocol.md",
        c2.returncode == 0 and "`added`" in doc.read_text() and run(root, "git", "status", "--porcelain").stdout.strip() == "",
        c2.stdout + c2.stderr,
    )

    doc.write_text(doc.read_text().replace('"protocol":7', '"protocol":99'))
    run(root, "git", "add", "docs/protocol.md")
    c3 = run(root, "git", "-c", "core.hooksPath=.githooks", "commit", "-m", "bad protocol version")
    check(
        "pre-commit refuses commit when protocol_map --check fails",
        c3.returncode != 0 and "protocol=99" in c3.stderr,
        c3.stdout + c3.stderr,
    )

print(f"PROTOCOL MAP TESTS: {sum(RESULTS)} passed, {len(RESULTS) - sum(RESULTS)} failed")
raise SystemExit(0 if all(RESULTS) else 1)
