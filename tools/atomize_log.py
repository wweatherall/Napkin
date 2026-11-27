#!/usr/bin/env python3
"""Convert ruling rows in 03_Past_Decisions/decision-log.md and decision-archive.md into
03_Past_Decisions/rulings/<ID>.md files via sort_decision_log.tidy, and verify every cell came through."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sort_decision_log as s


def atomize(root):
    live_path = os.path.join(root, s.LIVE)
    arch_path = os.path.join(root, s.ARCHIVE)
    rulings_dir = os.path.join(root, s.RULINGS_DIR)
    live = open(live_path, encoding="utf-8").read()
    archive = open(arch_path, encoding="utf-8").read()

    before_rows = {}
    for src_name, text in ((s.LIVE, live), (s.ARCHIVE, archive)):
        dets = s.details_sections(text)
        for _, sec, g, row_str, ident in s._ruling_rows_in(text):
            c = s.cells(row_str)
            before_rows[ident] = (sec, c, dets.get(ident))

    l2, a2 = s.tidy(live, archive, rulings_dir=rulings_dir)
    open(live_path, "w", encoding="utf-8").write(l2)
    open(arch_path, "w", encoding="utf-8").write(a2)

    files_after = set(s.folder_ids(rulings_dir))
    before_ids = set(before_rows)
    if before_ids and before_ids - files_after:
        raise SystemExit(f"missing ruling files: {sorted(before_ids - files_after)}")

    # Verify every cell's text appears in its file
    checked = 0
    for ident, (sec, cells_list, det_lines) in sorted(before_rows.items()):
        fpath = os.path.join(rulings_dir, f"{ident}.md")
        content = open(fpath, encoding="utf-8").read()
        for idx, cell in enumerate(cells_list):
            if sec == "## Principles" and idx == 3:
                continue   # Explains is generated
            text_val = s.strip_details_note(cell)
            if sec == "## Superseded decisions" and idx == 5 and "; " in text_val:
                for part in text_val.split("; "):
                    if part and part not in content:
                        raise SystemExit(f"{ident}: missing '{part}' in {fpath}")
                continue
            if text_val and text_val not in content:
                raise SystemExit(f"{ident}: missing cell text '{text_val}' in {fpath}")
        if det_lines:
            det_body = "\n".join(det_lines[1:]).strip()
            if det_body and det_body not in content:
                raise SystemExit(f"{ident}: missing Details text in {fpath}")
        checked += 1

    probs = s.check_files(l2, a2, rulings_dir=rulings_dir)
    if probs:
        raise SystemExit("check failed after atomize:\n" + "\n".join(probs))

    n_p = sum(1 for ident, (sec, _, _) in before_rows.items() if sec == "## Principles")
    n_d = sum(1 for ident, (sec, _, _) in before_rows.items() if sec == "## Decisions")
    n_s = sum(1 for ident, (sec, _, _) in before_rows.items() if sec == "## Superseded decisions")
    n_det = sum(1 for _, (_, _, d) in before_rows.items() if d)
    print(f"atomized {checked} rulings ({n_p} principles, {n_d} active/tentative decisions, {n_s} superseded decisions, {n_det} with details); {len(files_after)} files in {s.RULINGS_DIR}, verified {checked}/{checked} cells+details")


if __name__ == "__main__":
    root = os.path.dirname(HERE)
    atomize(root)
