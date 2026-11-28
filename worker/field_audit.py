"""Runtime audit of op fields sent to Model.apply vs actually read by handlers.

When SERVE_FIELD_AUDIT=<path> is set, Model.apply wraps each op in AuditedDict, which records
every key accessed via [], get(), in, pop(), setdefault(), or whole-dict iteration/views
(keys/values/items/__iter__), and preserves tracking across copy(). Each op appends a JSON
line {"type": ..., "sent": [...], "read": [...], "failed": bool} to that file.

CLI: python3 worker/field_audit.py <audit.jsonl> [...]
Exits 0 if every sent key (other than id, type, and matching UNREAD_WHEN entries) was read in
every non-failed run that sent it (failed runs are skipped because a rejected op stops reading
at its error, by design); exits 1 and prints each unread (op_type, field) with run count and an
example of sent keys otherwise.
"""
import json
import sys

ALWAYS_READ = frozenset({"id", "type"})

# {(op_type, field): (when_key or None, "<when it is unread, and why that is fine (or 'SUSPECTED BUG: ...')>")}
UNREAD_WHEN = {
    ("move", "targets"): (
        "cut",
        "when 'cut' is set, op_move dispatches to move_cut which reads op['cut'] "
        "instead of op['targets'] (move_tool sends targets: []).",
    ),
}


class AuditedDict(dict):
    """dict subclass that records which keys are read without altering dict behaviour."""

    def __init__(self, mapping=(), _read=None, **kwargs):
        super().__init__(mapping, **kwargs)
        self._read = set() if _read is None else _read

    def __getitem__(self, key):
        self._read.add(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._read.add(key)
        return super().get(key, default)

    def __contains__(self, key):
        self._read.add(key)
        return super().__contains__(key)

    def pop(self, key, *args):
        self._read.add(key)
        return super().pop(key, *args)

    def setdefault(self, key, default=None):
        self._read.add(key)
        return super().setdefault(key, default)

    def _mark_all(self):
        self._read.update(dict.keys(self))

    def keys(self):
        self._mark_all()
        return super().keys()

    def values(self):
        self._mark_all()
        return super().values()

    def items(self):
        self._mark_all()
        return super().items()

    def __iter__(self):
        self._mark_all()
        return super().__iter__()

    def copy(self):
        clone = AuditedDict.__new__(AuditedDict)
        dict.update(clone, dict.items(self))
        clone._read = self._read
        return clone

    def __copy__(self):
        return self.copy()

    def read_keys(self):
        return sorted(self._read)


def append_record(path, op_type, sent_keys, read_keys, failed=False):
    """Append one JSONL audit record for an applied op."""
    record = {"type": op_type, "sent": list(sent_keys), "read": list(read_keys), "failed": bool(failed)}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def unread_fields(paths, allow=None):
    """Return {op_type: {field: {"count": n, "example": [...]}}} for per-run unread fields.

    Skips failed runs because a rejected op stops reading at its error, by design.
    """
    if allow is None:
        allow = UNREAD_WHEN
    unread = {}
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("failed"):
                    continue
                op_type = rec["type"]
                sent = set(rec["sent"])
                read = set(rec["read"])
                for field in sorted(sent - read - ALWAYS_READ):
                    allow_entry = allow.get((op_type, field))
                    if allow_entry is not None:
                        when_key = allow_entry[0] if isinstance(allow_entry, tuple) else None
                        if when_key is None or when_key in sent:
                            continue
                    by_field = unread.setdefault(op_type, {})
                    entry = by_field.get(field)
                    if entry is None:
                        by_field[field] = {"count": 1, "example": sorted(rec["sent"])}
                    else:
                        entry["count"] += 1
    return unread


def format_report(unread):
    """Format unread {op_type: {field: {"count": n, "example": [...]}}} for printing."""
    lines = []
    for op_type in sorted(unread):
        for field, info in sorted(unread[op_type].items()):
            ex = ", ".join(info["example"])
            lines.append(f"  {op_type}.{field} ({info['count']} run(s), example sent: [{ex}])")
    return "\n".join(lines)


def main(argv=None):
    paths = list(sys.argv[1:] if argv is None else argv)
    if not paths:
        print("usage: field_audit.py <audit.jsonl> [...]", file=sys.stderr)
        return 2
    unread = unread_fields(paths)
    if not unread:
        return 0
    print("FIELD AUDIT FAIL: op field(s) sent but not read in one or more runs:")
    print(format_report(unread))
    return 1


if __name__ == "__main__":
    sys.exit(main())
