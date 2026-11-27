"""Runtime audit of op fields sent to Model.apply vs actually read by handlers.

When SERVE_FIELD_AUDIT=<path> is set, Model.apply wraps each op in AuditedDict, which records
every key accessed via [], get(), in, pop(), setdefault(), or whole-dict iteration/views
(keys/values/items/__iter__), and preserves tracking across copy(). Each op appends a JSON
line {"type": ..., "sent": [...], "read": [...]} to that file.

CLI: python3 worker/field_audit.py <audit.jsonl> [...]
Exits 0 if every sent key (other than id and type) was read at least once for its op type;
exits 1 and prints the unread keys per op type otherwise.
"""
import json
import sys

ALWAYS_READ = frozenset({"id", "type"})


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


def append_record(path, op_type, sent_keys, read_keys):
    """Append one JSONL audit record for an applied op."""
    record = {"type": op_type, "sent": list(sent_keys), "read": list(read_keys)}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def unread_fields(paths):
    """Return {op_type: [unread_key, ...]} across all JSONL audit files in paths."""
    sent_by_type = {}
    read_by_type = {}
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                op_type = rec["type"]
                sent_by_type.setdefault(op_type, set()).update(rec["sent"])
                read_by_type.setdefault(op_type, set()).update(rec["read"])
    unread = {}
    for op_type in sorted(sent_by_type):
        diff = sorted(sent_by_type[op_type] - read_by_type.get(op_type, set()) - ALWAYS_READ)
        if diff:
            unread[op_type] = diff
    return unread


def format_report(unread):
    """Format unread {op_type: [key, ...]} for printing."""
    return "\n".join(f"  {op_type}: {', '.join(keys)}" for op_type, keys in sorted(unread.items()))


def main(argv=None):
    paths = list(sys.argv[1:] if argv is None else argv)
    if not paths:
        print("usage: field_audit.py <audit.jsonl> [...]", file=sys.stderr)
        return 2
    unread = unread_fields(paths)
    if not unread:
        return 0
    print("FIELD AUDIT FAIL: op field(s) sent but never read:")
    print(format_report(unread))
    return 1


if __name__ == "__main__":
    sys.exit(main())
