#!/usr/bin/env python3
"""Small transcript fixtures for H216. No local agent logs are required."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from reading_cost import Call, Repository, classify_job, measure, parse, report, spans

ROOT = Path("/project/Napkin")
BRANCH = "/project/.worktrees/Napkin/h216"
JOB = "H216"


class Files:
    root = ROOT
    old_roots = ()

    def line_count(self, rev, path):
        assert rev == "merge"
        return {"worker/build.py": (8, False), "tools/test_build.py": (9, False),
                "docs/guide.md": (4, False), "tests/data.json": (6, True)}.get(path, (None, False))


def result(agent, rows, path=None):
    with TemporaryDirectory() as directory:
        path = Path(directory) / (path or f"{agent}.jsonl")
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return parse(path, agent)


def analyze(*transcripts):
    return measure([spans(t, JOB, {}) for t in transcripts], Files(), "merge", str(ROOT))


def claude_turn(id, tokens, *tools):
    return {"type": "assistant", "cwd": str(ROOT), "message": {
        "id": id, "model": "claude-fixture",
        "usage": {"input_tokens": tokens, "cache_read_input_tokens": 2, "cache_creation_input_tokens": 1,
                  "output_tokens": 1},
        "content": [{"type": "tool_use", "id": tid, "name": name, "input": args}
                    for tid, name, args in tools]}}


def test_claude_ranges_cache_and_duplicate_message_blocks():
    first = claude_turn("a", 10, ("a1", "Read", {"file_path": "worker/build.py", "offset": 2, "limit": 4}))
    rows = [
        first,
        first,
        claude_turn("b", 20, ("b1", "Read", {"file_path": f"{BRANCH}/worker/build.py", "offset": 4}),
                    ("b2", "Grep", {"pattern": "hello"})),
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "b2", "content": "a:1:hello\nb:2:hello\n"}]}},
        claude_turn("c", 30, ("c1", "Edit", {"file_path": "worker/build.py"})),
        claude_turn("d", 40, ("d1", "unrecognized_tool", {})),
    ]
    got = analyze(result("claude", rows))
    assert got["files_read"] == ["worker/build.py"], got
    assert got["reads"]["code"] == {"files": 1, "unique": 7, "repeated": 2}, got
    assert got["search_output_lines"] == 2, got
    assert (got["tokens_before_first_edit"], got["tokens_total"]) == (72, 116), got
    assert got["calls"] == {"read": 2, "search": 1, "edit": 1, "other": 1}, got


def gemini_turn(tokens, *tools):
    return {"type": "PLANNER_RESPONSE", "model": "gemini-fixture", "input_tokens": tokens,
            "cache_read_tokens": 1, "output_tokens": 1,
            "tool_calls": [{"name": name, "args": args} for name, args in tools]}


def generic(content):
    return {"type": "GENERIC", "content": "Created At: recorded\nCommand exited with code 0.\n\nCommand output:\n" + content}


def take(agent, job):
    return f"took {job} (new): branch {agent}/{job.lower()}-test, worktree /project/.worktrees/Napkin/{job.lower()}"


def test_gemini_shell_and_second_claim():
    rows = [
        gemini_turn(2, ("run_command", {"CommandLine": "python3 tools/GET_A_JOB.py --as gemini"})),
        generic(take("gemini", JOB)),
        gemini_turn(10, ("read_file", {"Path": json.dumps(f"{BRANCH}/docs/guide.md"),
                                       "StartLine": "2", "EndLine": "99"})),
        generic("guide"),
        gemini_turn(20, ("run_command", {"CommandLine": json.dumps(
            "cd /project/.worktrees/Napkin/h216 && sed -n '1,2p' docs/guide.md && head -n 3 tests/data.json")})),
        generic("one\ntwo\n"),
        gemini_turn(30, ("run_command", {"CommandLine": "rg -n guide docs | head -3"})),
        generic("doc:1:guide\ndoc:2:guide\n"),
        gemini_turn(40, ("write_file", {"Path": "docs/guide.md"})),
        generic("written"),
        gemini_turn(50, ("unrecognized_tool", {})),
        generic("ignored"),
        gemini_turn(60, ("run_command", {"CommandLine": "python3 tools/GET_A_JOB.py --as gemini"})),
        generic(take("gemini", "H217")),
        gemini_turn(70, ("read_file", {"Path": "tools/test_build.py"})),
        generic("test"),
    ]
    transcript = result("gemini", rows)
    assert [call.match[0] for _, call in transcript.claims] == [JOB, "H217"]
    got = analyze(transcript)
    assert got["files_read"] == ["docs/guide.md", "tests/data.json"], got
    assert got["reads"]["docs"] == {"files": 1, "unique": 4, "repeated": 1}, got
    assert got["reads"]["tests"] == {"files": 1, "unique": 3, "repeated": 0}, got
    assert got["current_file_fallbacks"] == ["tests/data.json"], got
    assert got["search_output_lines"] == 2, got
    assert (got["tokens_before_first_edit"], got["tokens_total"]) == (112, 164), got
    second = measure([spans(transcript, "H217", {})], Files(), "merge", str(ROOT))
    assert second["files_read"] == ["tools/test_build.py"] and second["tokens_total"] == 134, second


def codex_row(kind, when, **payload):
    return {"type": kind, "timestamp": when, "payload": payload}


def codex_tokens(when, tokens):
    return codex_row("event_msg", when, type="token_count",
                     info={"total_token_usage": {"total_tokens": tokens}})


def codex_call(when, id, name, **args):
    return codex_row("response_item", when, type="function_call", name=name, call_id=id,
                     arguments=json.dumps(args))


def test_codex_legacy_rollout_cumulative_tokens():
    rows = [
        codex_row("session_meta", 1, id="id-from-record", cwd=str(ROOT)),
        codex_row("turn_context", 2, model="codex-fixture"),
        codex_tokens(3, 10),
        codex_call(4, "a", "exec_command", cmd="cat worker/build.py"),
        codex_tokens(5, 36),
        codex_call(6, "b", "exec_command", cmd="nl -ba worker/build.py | sed -n '3,5p'", workdir=BRANCH),
        codex_call(7, "c", "exec_command", cmd="rg -n foo worker"),
        codex_row("response_item", 8, type="function_call_output", call_id="c",
                  output="Chunk ID: xyz\nWall time: 0 seconds\nOutput:\nworker/a.py:1:foo\n"),
        codex_tokens(9, 47),
        codex_row("response_item", 10, type="custom_tool_call", name="apply_patch", input="*** Begin Patch"),
        codex_tokens(11, 99),
        codex_call(12, "d", "mystery"),
    ]
    transcript = result("codex", rows)
    assert transcript.session == "id-from-record"
    got = analyze(transcript)
    assert got["files_read"] == ["worker/build.py"], got
    assert got["reads"]["code"] == {"files": 1, "unique": 8, "repeated": 3}, got
    assert got["search_output_lines"] == 1, got
    assert (got["tokens_before_first_edit"], got["tokens_total"]) == (47, 99), got
    assert got["calls"]["other"] == 1, got


def modern_command(when, start, command, output=""):
    return codex_row("event_msg", when, type="item_completed", started_at_ms=start * 1000, item={
        "type": "CommandExecution", "command": ["/bin/zsh", "-lc", command],
        "cwd": f"file://{BRANCH}", "aggregated_output": output, "exit_code": 0,
    })


def test_codex_structured_batch_and_multi_session():
    rows = [
        codex_row("session_meta", 1, id="real-session", cwd=str(ROOT)),
        codex_tokens(2, 20),
        codex_row("response_item", 3, type="custom_tool_call", name="exec", input="await actualCommands()"),
        modern_command(8, 6, "head -5 worker/build.py"),
        modern_command(9, 5, "sed -n '3,4p;8p' worker/build.py"),
        codex_row("token_usage_record", 10, thread_token_usage={"total_tokens": 101}),
        codex_tokens(11, 101),
        modern_command(13, 12, "python3 - <<'PY'\nfrom pathlib import Path\nPath('foo').write_text('bar')\nPY"),
        codex_tokens(14, 110),
    ]
    resume = result("codex", [
        codex_row("session_meta", 15, id="second-session", cwd=str(ROOT)),
        codex_tokens(16, 5),
        codex_call(17, "z", "exec_command", cmd="tail -n +4 worker/build.py"),
    ])
    got = analyze(result("codex", rows), resume)
    assert got["reads"]["code"] == {"files": 1, "unique": 8, "repeated": 5}, got
    assert (got["tokens_before_first_edit"], got["tokens_total"]) == (101, 115), got
    assert got["calls"] == {"read": 3, "search": 0, "edit": 1, "other": 0}, got


def test_combined_search_results_and_historical_checkout():
    call = Call("Bash", {"command": "cd /sites/fretchup-h216 && sed -n 2,4p worker/build.py; "
                                  "rg -n hello worker; git status"})
    call.result("sliced line\nanother line\nworker/build.py:4:hello\nOn branch main\n")
    got = measure([[call]], Files(), "merge", str(ROOT))
    assert got["files_read"] == ["worker/build.py"], got
    assert got["reads"]["code"]["unique"] == 3, got
    assert got["search_output_lines"] == 1 and got["searches_with_unattributed_output"] == 1, got


def test_missing_and_failed_reads_are_distinguishable():
    call = Call("Read", {"file_path": "worker/build.py"})
    call.result("No such file", failed=True)
    missing = Call("Read", {"file_path": "worker/missing.py"})
    external = Call("Read", {"file_path": "/outside/worker/build.py"})
    got = measure([[call, missing, external]], Files(), "merge", str(ROOT))
    assert got["files_read"] == [] and got["tokens_total"] is None, got
    assert got["unresolved_read_paths"] == 1, got
    assert got["first_edit_observed"] is False and got["tokens_before_first_edit"] is None, got


def test_merge_diff_uses_first_parent_and_job_kind():
    with TemporaryDirectory() as directory:
        from subprocess import run

        def git(*args):
            return run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.com",
                        *args], cwd=directory, check=True, capture_output=True)

        root = Path(directory)
        git("init", "-b", "main")
        git("commit", "--allow-empty", "-m", "base")
        git("checkout", "-b", "codex/h216-test")
        (root / "worker").mkdir()
        path = root / "worker" / "build.py"
        path.write_text("first\nlast", encoding="utf-8")
        git("add", "worker/build.py")
        git("commit", "-m", "worker change")
        git("checkout", "main")
        git("merge", "--no-ff", "codex/h216-test", "-m", "Merge codex/h216-test")
        path.write_text("current version", encoding="utf-8")
        repository = Repository(root)
        commit, stamp, agent, files = repository.diff(JOB, "", {})
        assert stamp and agent == "codex" and files == {"worker/build.py": 2}, files
        assert repository.line_count(commit, "worker/build.py") == (2, False)
        assert classify_job(files) == "worker op"
        assert classify_job({**files, "viewport/tool.gd": 4}) == "mixed"
        assert classify_job({"tools/script.py": 4, "tests/cases.json": 3}) == "tools/process"
        assert classify_job({"docs/guide.md": 4}) == "docs only"


def test_report_lists_missing_and_handles_zero_denominators():
    output = StringIO()
    with redirect_stdout(output):
        report({"jobs": [{"job": JOB, "missing_transcript": "recorded session or transcript unavailable"}]})
    assert "0/1 jobs measured" in output.getvalue() and JOB in output.getvalue()


if __name__ == "__main__":
    import traceback

    tests = [(name, case) for name, case in list(globals().items()) if name.startswith("test_")]
    failed = 0
    for name, case in tests:
        try:
            case()
        except Exception:
            print(f"FAIL {name}")
            traceback.print_exc()
            failed += 1
    print(f"READING COST TESTS: {len(tests) - failed} passed, {failed} failed")
    raise SystemExit(bool(failed))
