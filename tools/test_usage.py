#!/usr/bin/env python3
"""Unit tests for tools/usage.py (stdlib-only, synthetic temp files only).

Summary line: USAGE TESTS: N passed, M failed."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import job
import usage


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _agy_transcript_path(brain_dir, conv_id):
    return os.path.join(brain_dir, conv_id, ".system_generated", "logs", "transcript.jsonl")


class TestQuotaBurn(unittest.TestCase):
    def test_simple_burn(self):
        samples = [
            (100.0, {"gemini-5h": 0.90}),
            (150.0, {"gemini-5h": 0.87}),
            (200.0, {"gemini-5h": 0.82}),
        ]
        burn, n = usage.compute_bucket_burn(samples, "gemini-5h", 100.0, 200.0)
        self.assertAlmostEqual(burn, 0.08, places=5)
        self.assertEqual(n, 3)

    def test_ignores_small_polling_jitter(self):
        samples = [
            (100.0, {"gemini-weekly": 0.9000}),
            (115.0, {"gemini-weekly": 0.9003}),
            (130.0, {"gemini-weekly": 0.9000}),
            (145.0, {"gemini-weekly": 0.9003}),
            (160.0, {"gemini-weekly": 0.9000}),
        ]
        burn, _ = usage.compute_bucket_burn(samples, "gemini-weekly", 100.0, 160.0)
        self.assertAlmostEqual(burn, 0.0, places=5)

    def test_handles_mid_job_quota_reset(self):
        samples = [
            (100.0, {"claude-5h": 0.20}),
            (150.0, {"claude-5h": 0.15}),
            (200.0, {"claude-5h": 1.00}),
            (250.0, {"claude-5h": 0.97}),
        ]
        burn, _ = usage.compute_bucket_burn(samples, "claude-5h", 100.0, 250.0)
        self.assertAlmostEqual(burn, 0.08, places=5)

    def test_filters_transient_upward_spike_glitch(self):
        samples = [
            (100.0, {"gemini-weekly": 0.46}),
            (115.0, {"gemini-weekly": 0.45}),
            (130.0, {"gemini-weekly": 1.00}),
            (145.0, {"gemini-weekly": 1.00}),
            (160.0, {"gemini-weekly": 0.45}),
            (175.0, {"gemini-weekly": 0.44}),
        ]
        burn, _ = usage.compute_bucket_burn(samples, "gemini-weekly", 100.0, 175.0)
        self.assertAlmostEqual(burn, 0.02, places=5)

    def test_filters_transient_downward_rebound_dip(self):
        # 0.761 -> 0.751 -> 0.757 -> 0.756: 0.751 is a brief downward glitch
        samples = [
            (100.0, {"gemini-5h": 0.761}),
            (115.0, {"gemini-5h": 0.751}),
            (130.0, {"gemini-5h": 0.757}),
            (145.0, {"gemini-5h": 0.756}),
        ]
        burn, n = usage.compute_bucket_burn(samples, "gemini-5h", 100.0, 145.0)
        self.assertAlmostEqual(burn, 0.005, places=5)
        self.assertEqual(n, 3)

        # Deeper dip (> RESET_JUMP_THRESHOLD) must not trigger a bogus quota reset
        deep_dip = [
            (100.0, {"gemini-5h": 0.761}),
            (115.0, {"gemini-5h": 0.700}),
            (130.0, {"gemini-5h": 0.757}),
            (145.0, {"gemini-5h": 0.756}),
        ]
        burn2, n2 = usage.compute_bucket_burn(deep_dip, "gemini-5h", 100.0, 145.0)
        self.assertAlmostEqual(burn2, 0.005, places=5)
        self.assertEqual(n2, 3)

    def test_respects_next_event_s_clamp(self):
        # Short window [100, 120]; next session starts at 130 and burns quota by 150.
        samples = [
            (95.0, {"gemini-5h": 0.90}),
            (105.0, {"gemini-5h": 0.89}),
            (150.0, {"gemini-5h": 0.80}),  # belongs to next session (after next_event_s=130)
        ]
        burn_unclamped, _ = usage.compute_bucket_burn(samples, "gemini-5h", 100.0, 120.0, pad_after=60.0)
        self.assertAlmostEqual(burn_unclamped, 0.10, places=5)

        burn_clamped, _ = usage.compute_bucket_burn(
            samples, "gemini-5h", 100.0, 120.0, pad_after=60.0, next_event_s=130.0
        )
        self.assertAlmostEqual(burn_clamped, 0.01, places=5)


class TestConcurrency(unittest.TestCase):
    def test_solo_vs_shared_workers(self):
        all_jobs = {
            "H001": {"agent": "gemini", "taken": 100.0, "done": 200.0},
            "H002": {"agent": "gemini", "taken": 150.0, "done": 250.0},
            "H003": {"agent": "claude", "taken": 150.0, "done": 250.0},
            "H004": {"agent": "gemini", "taken": 300.0, "done": 400.0},
        }
        mode1, ov1 = usage.detect_concurrency(all_jobs, "H001", "gemini", 100.0, 200.0)
        self.assertEqual(mode1, "shared-worker")
        self.assertEqual(ov1, ["H002"])

        mode3, ov3 = usage.detect_concurrency(all_jobs, "H003", "claude", 150.0, 250.0)
        self.assertEqual(mode3, "solo")
        self.assertEqual(ov3, [])

        mode4, ov4 = usage.detect_concurrency(all_jobs, "H004", "gemini", 300.0, 400.0)
        self.assertEqual(mode4, "solo")
        self.assertEqual(ov4, [])

    def test_gemini_integrator_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            tpath = _agy_transcript_path(tmp, "int-uuid-1")
            _write_jsonl(tpath, [
                {"type": "USER_INPUT", "created_at": "2026-11-24T01:00:00Z", "content": "You are the integrator"},
                {
                    "type": "PLANNER_RESPONSE",
                    "created_at": "2026-11-24T01:05:00Z",
                    "model": "gemini-4-neon-medium",
                    "input_tokens": 8000,
                    "cache_read_tokens": 0,
                    "output_tokens": 200,
                    "tool_calls": [
                        {"name": "run_command", "args": {"CommandLine": "python3 tools/integrator.py take gemini-cedar-1124-0100"}}
                    ],
                },
            ])
            t_overlap_start = usage.parse_iso_ts("2026-11-24T01:00:00Z")
            t_overlap_end = usage.parse_iso_ts("2026-11-24T01:10:00Z")
            t_solo_start = usage.parse_iso_ts("2026-11-24T02:00:00Z")
            t_solo_end = usage.parse_iso_ts("2026-11-24T02:10:00Z")

            all_jobs = {
                "H140": {"agent": "gemini", "taken": t_overlap_start, "done": t_overlap_end},
                "H141": {"agent": "gemini", "taken": t_solo_start, "done": t_solo_end},
            }
            mode_ov, _ = usage.detect_concurrency(
                all_jobs, "H140", "gemini", t_overlap_start, t_overlap_end, agy_brain=tmp
            )
            self.assertEqual(mode_ov, "shared-int")

            mode_solo, _ = usage.detect_concurrency(
                all_jobs, "H141", "gemini", t_solo_start, t_solo_end, agy_brain=tmp
            )
            self.assertEqual(mode_solo, "solo")


class TestBriefMeta(unittest.TestCase):
    def test_parse_brief(self):
        text = """### H109 — Sample job

Touches: viewport/document.gd, viewport/main.gd (only `_on_rejected`), viewport/test_document.gd

What can fail:
- something breaks

Reading path: main.gd -> document.gd

Response — Claude, 2026-11-23:
All done.
"""
        meta = usage.parse_brief_meta(text)
        self.assertEqual(meta["touches_count"], 3)
        self.assertTrue(meta["has_reading_path"])
        self.assertTrue(meta["has_what_can_fail"])
        self.assertGreater(meta["brief_words"], 15)
        self.assertGreater(meta["response_words"], 0)


class TestTranscriptHolesAndDiscovery(unittest.TestCase):
    def test_analyze_claude_transcript(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            path = f.name
            rows = [
                {
                    "message": {
                        "usage": {
                            "input_tokens": 500,
                            "output_tokens": 200,
                            "cache_read_input_tokens": 10000,
                            "cache_creation_input_tokens": 2000,
                        },
                        "content": [
                            {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/repo/ARCHITECTURE.md"}},
                            {"type": "tool_result", "tool_use_id": "t1", "content": "x" * 24000},
                        ],
                    }
                },
                {
                    "message": {
                        "usage": {
                            "input_tokens": 600,
                            "output_tokens": 300,
                            "cache_read_input_tokens": 18000,
                            "cache_creation_input_tokens": 1000,
                        },
                        "content": [
                            {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "/repo/ARCHITECTURE.md"}},
                            {"type": "tool_result", "tool_use_id": "t2", "content": "x" * 24000},
                        ],
                    }
                },
            ]
            for r in rows:
                f.write(json.dumps(r) + "\n")
        try:
            res = usage.analyze_transcript(path)
            self.assertEqual(res["turns"], 2)
            self.assertEqual(res["input_tokens"], 1100)
            self.assertEqual(res["output_tokens"], 500)
            self.assertEqual(res["cache_read_tokens"], 28000)
            self.assertEqual(len(res["repeated_reads"]), 1)
            self.assertEqual(res["repeated_reads"][0]["count"], 2)
            self.assertTrue(any("ARCHITECTURE.md" in fl for fl in res["flags"]))
        finally:
            os.unlink(path)

    def test_analyze_agy_transcript(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            path = f.name
            rows = [
                {"type": "USER_INPUT", "created_at": "2026-11-24T01:00:00Z", "content": "<USER_REQUEST>Check the board</USER_REQUEST>"},
                {
                    "type": "PLANNER_RESPONSE",
                    "created_at": "2026-11-24T01:00:05Z",
                    "model": "gemini-4-neon-medium",
                    "input_tokens": 12000,
                    "cache_read_tokens": 0,
                    "output_tokens": 300,
                    "tool_calls": [
                        {"name": "read_file", "args": {"Path": "/repo/BOARD.md"}},
                    ],
                },
                {"type": "GENERIC", "created_at": "2026-11-24T01:00:06Z", "content": "b" * 20000},
                {
                    "type": "PLANNER_RESPONSE",
                    "created_at": "2026-11-24T01:00:10Z",
                    "model": "gemini-4-neon-medium",
                    "input_tokens": 2000,
                    "cache_read_tokens": 15000,
                    "output_tokens": 400,
                    "tool_calls": [
                        {"name": "read_file", "args": {"Path": "/repo/BOARD.md"}},
                    ],
                },
                {"type": "GENERIC", "created_at": "2026-11-24T01:00:11Z", "content": "b" * 20000},
            ]
            for r in rows:
                f.write(json.dumps(r) + "\n")
        try:
            res = usage.analyze_transcript(path)
            self.assertEqual(res["turns"], 2)
            self.assertEqual(res["input_tokens"], 14000)
            self.assertEqual(res["cache_read_tokens"], 15000)
            self.assertEqual(res["output_tokens"], 700)
            self.assertEqual(res["ctx_start"], 12000)
            self.assertEqual(res["ctx_peak"], 17000)
            self.assertAlmostEqual(res["cache_hit_pct"], round(15000 / 29000 * 100.0, 1))
            self.assertEqual(len(res["repeated_reads"]), 1)
            self.assertEqual(res["repeated_reads"][0]["count"], 2)
            self.assertEqual(res["repeated_reads"][0]["file"], "/repo/BOARD.md")
            self.assertTrue(any("BOARD.md" in fl for fl in res["flags"]))
            self.assertEqual(res["top_tool_outputs"][0]["tool"], "read_file")
        finally:
            os.unlink(path)

    def test_discover_agy_transcript_by_session_name_uuid_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            uuid1 = "11111111-2222-3333-4444-555555555555"
            p1 = _agy_transcript_path(tmp, uuid1)
            _write_jsonl(p1, [
                {
                    "type": "PLANNER_RESPONSE",
                    "created_at": "2026-11-24T01:00:05Z",
                    "model": "gemini-4-neon-medium",
                    "input_tokens": 5000,
                    "cache_read_tokens": 1000,
                    "output_tokens": 100,
                    "tool_calls": [
                        {"name": "run_command", "args": {"CommandLine": "python3 tools/job.py take --as gemini --session gemini-cedar-1124-0100"}}
                    ],
                }
            ])

            # Locate by fretchup session name
            found, kind = usage.discover_transcript(
                {"agent": "gemini", "session": "gemini-cedar-1124-0100", "job": "H140"}, agy_brain=tmp
            )
            self.assertEqual(found, p1)
            self.assertEqual(kind, "agy")

            # Locate by direct UUID
            found2, kind2 = usage.discover_transcript(
                {"agent": "gemini", "session": uuid1, "job": "H140"}, agy_brain=tmp
            )
            self.assertEqual(found2, p1)
            self.assertEqual(kind2, "agy")

            # Missing brain dir -> fail-open (None, None)
            found3, kind3 = usage.discover_transcript(
                {"agent": "gemini", "session": "gemini-cedar-1124-0100", "job": "H140"},
                agy_brain=os.path.join(tmp, "does-not-exist"),
            )
            self.assertIsNone(found3)
            self.assertIsNone(kind3)


class TestOrientBenchAndOverhead(unittest.TestCase):
    def test_orient_turn2_after_warmup(self):
        with tempfile.TemporaryDirectory() as tmp:
            brain = os.path.join(tmp, "brain")
            agy_dir = os.path.join(tmp, "agy-mon")
            claude_dir = os.path.join(tmp, "claude-mon")
            repo = os.path.join(tmp, "repo")
            os.makedirs(os.path.join(repo, ".git"), exist_ok=True)

            # Synthetic transcript like b0ee70ee: turn 1 is stray warm-up, turn 2 is integrator startup
            tpath = _agy_transcript_path(brain, "b0ee70ee-0000-0000-0000-000000000000")
            _write_jsonl(tpath, [
                {"type": "USER_INPUT", "created_at": "2026-11-24T00:50:00Z", "content": "<USER_REQUEST>hi agy</USER_REQUEST>"},
                {
                    "type": "PLANNER_RESPONSE",
                    "created_at": "2026-11-24T00:50:05Z",
                    "model": "gemini-4-neon-medium",
                    "input_tokens": 5000,
                    "cache_read_tokens": 0,
                    "output_tokens": 50,
                    "tool_calls": [],
                },
                {"type": "USER_INPUT", "created_at": "2026-11-24T00:54:00Z", "content": "<USER_REQUEST>hello you are the integrator</USER_REQUEST>"},
                {
                    "type": "PLANNER_RESPONSE",
                    "created_at": "2026-11-24T00:54:05Z",
                    "model": "gemini-4-neon-medium",
                    "input_tokens": 11000,
                    "cache_read_tokens": 4000,
                    "output_tokens": 250,
                    "tool_calls": [
                        {"name": "run_command", "args": {"CommandLine": "python3 tools/startup.py --role integrator"}}
                    ],
                },
                {
                    "type": "PLANNER_RESPONSE",
                    "created_at": "2026-11-24T00:54:20Z",
                    "model": "gemini-4-neon-medium",
                    "input_tokens": 2000,
                    "cache_read_tokens": 18000,
                    "output_tokens": 350,
                    "tool_calls": [
                        {"name": "run_command", "args": {"CommandLine": "python3 tools/integrator.py take gemini-birch-1124-0054"}}
                    ],
                },
                {"type": "USER_INPUT", "created_at": "2026-11-24T00:55:00Z", "content": "<USER_REQUEST>now merge H125</USER_REQUEST>"},
            ])

            # Quota history around turn 2 [00:54:00, 00:54:20], plus later burn after 00:55:00
            _write_jsonl(os.path.join(agy_dir, "history.jsonl"), [
                {"ts": usage.parse_iso_ts("2026-11-24T00:53:50Z"), "buckets": {"gemini-5h": 0.900}},
                {"ts": usage.parse_iso_ts("2026-11-24T00:54:25Z"), "buckets": {"gemini-5h": 0.892}},
                {"ts": usage.parse_iso_ts("2026-11-24T00:55:10Z"), "buckets": {"gemini-5h": 0.850}},
            ])

            # JSON output
            buf_json = io.StringIO()
            with redirect_stdout(buf_json):
                rc = usage.main([
                    "--repo", repo,
                    "--claude-dir", claude_dir,
                    "--agy-dir", agy_dir,
                    "--agy-brain", brain,
                    "orient", "--json",
                ])
            self.assertEqual(rc, 0)
            payload = json.loads(buf_json.getvalue())
            self.assertEqual(len(payload["orientations"]), 1)
            o = payload["orientations"][0]
            self.assertEqual(o["session"], "gemini-birch-1124-0054")
            self.assertEqual(o["turn_index"], 2)
            self.assertEqual(o["warmup_turns"], 1)
            self.assertEqual(o["planner_calls"], 2)
            self.assertEqual(o["input_tokens"], 13000)
            self.assertEqual(o["cache_read_tokens"], 22000)
            self.assertEqual(o["total_prompt_tokens"], 35000)
            self.assertEqual(o["output_tokens"], 600)
            self.assertEqual(o["peak_context"], 20000)
            self.assertAlmostEqual(o["meas_5h"], 0.008, places=5)
            self.assertEqual(o["model_display"], "Gemini 4 Neon (Med)")

            # Table output
            buf_tbl = io.StringIO()
            with redirect_stdout(buf_tbl):
                rc2 = usage.main([
                    "--repo", repo,
                    "--claude-dir", claude_dir,
                    "--agy-dir", agy_dir,
                    "--agy-brain", brain,
                    "orient",
                ])
            self.assertEqual(rc2, 0)
            tbl = buf_tbl.getvalue()
            self.assertIn("gemini-birch-1124-0054", tbl)
            self.assertIn("T2 (+1w)", tbl)
            self.assertIn("0.80%", tbl)

            # Bench output
            buf_bench = io.StringIO()
            with redirect_stdout(buf_bench):
                rc3 = usage.main([
                    "--repo", repo,
                    "--claude-dir", claude_dir,
                    "--agy-dir", agy_dir,
                    "--agy-brain", brain,
                    "--ledger", os.path.join(tmp, "ledger.jsonl"),
                    "bench",
                ])
            self.assertEqual(rc3, 0)
            self.assertIn("Recent Integrator Orientations", buf_bench.getvalue())
            self.assertIn("Calibration", buf_bench.getvalue())

            # Overhead output (Gemini side only, Claude absent -> skips cleanly)
            buf_ov = io.StringIO()
            with redirect_stdout(buf_ov):
                rc4 = usage.main([
                    "--repo", repo,
                    "--claude-dir", claude_dir,
                    "--agy-dir", agy_dir,
                    "--agy-brain", brain,
                    "overhead",
                ])
            self.assertEqual(rc4, 0)
            self.assertIn("Gemini Overhead", buf_ov.getvalue())
            self.assertIn("integrator", buf_ov.getvalue())

    def test_job_default_usage_tool_points_to_vendored_script(self):
        self.assertTrue(job.USAGE_TOOL.endswith(os.path.join("tools", "usage.py")))
        self.assertTrue(os.path.isfile(job.USAGE_TOOL))


class TestVizHelpers(unittest.TestCase):
    def test_bar_and_sparkline(self):
        c = usage.make_styler(False)
        bar = usage.render_bar(0.05, 0.10, 10, c)
        self.assertEqual(bar, "█████░░░░░")
        spark = usage.render_sparkline([0.0, 0.05, 0.10], c)
        self.assertEqual(len(spark), 3)
        rows = usage.render_4row_chart([0.01, 0.05, 0.10], c)
        self.assertEqual(len(rows), 4)


def run_all():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    buf = io.StringIO()
    result = unittest.TextTestRunner(stream=buf, verbosity=1).run(suite)
    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    if failed:
        sys.stderr.write(buf.getvalue())
    print(f"USAGE TESTS: {total - failed} passed, {failed} failed", flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_all())
