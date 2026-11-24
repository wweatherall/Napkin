### H144 — T129: Improve `tools/usage.py holes` diagnostics (line-range overlap, full transcript sizes, phase & tail-turn burn)

Author: Gemini (integrator, gemini-birch-1124-0740) | Date: 2026-11-24 | Status: open | For: either

References: T129, T126, T117.

Touches: tools/usage.py, tools/test_usage.py.

Why: Analyzing H136's actual turn-by-turn transcript showed that `tools/usage.py holes` currently produces noisy false positives while missing the real token sinks:
1. `_extract_tool_target()` leaves JSON-encoded outer quotes on AGY `args` strings (printing `Re-read presenter.gd" 3x`).
2. `analyze_transcript()` counts `read_file`/`view_file` calls by path alone, flagging disjoint line-range slices (`[1-120]`, `[480-560]`) as "re-reads" even though sliced reading is normal and desired.
3. AGY's compact `transcript.jsonl` truncates `GENERIC` tool outputs to ~4k chars (~1.0k est tokens), making `Top Tool Outputs` flat (`1.0k` across every row) instead of showing real sizes from sibling `transcript_full.jsonl`.
4. With ~94% cache hit rates, the biggest real burn in H136 was **turn count × accumulated context** — specifically 11 post-test bookkeeping turns at 88k–100k context (~47% of total input tokens) and 10 unbatched single-tool lookup turns at 51k–70k context — none of which `holes` currently surfaces.

Today (checked 2026-11-24):
- `tools/usage.py`:
  - `_extract_tool_target(tinput)` (lines 996–1016): picks the first non-empty key (`file_path`, `Path`, `CommandLine`, etc.) and converts via `str(val)` without stripping JSON-quoted AGY strings.
  - `analyze_transcript(path)` (lines 1019–1148): parses AGY (`PLANNER_RESPONSE` + `GENERIC`) and Claude (`message.usage` + `tool_use`/`tool_result`) rows, counts `file_reads[target] += 1` without line ranges, computes `chars // 4` directly from `path` (never checking sibling `transcript_full.jsonl`), and returns `turns`, token totals, `ctx_start`/`ctx_median`/`ctx_peak`, `flags`, `top_tool_outputs`, and `repeated_reads`.
  - `cmd_holes(args)` (lines 1793–1861): prints the summary, `Flags:`, `Top Tool Outputs:`, and `Repeated File Reads:` (or raw JSON with `--json`).
- `tools/test_usage.py`: unittest suite run automatically by `tools/featuretest.sh`, with `test_analyze_claude_transcript` (line 193) and `test_analyze_agy_transcript` (line 240).

Request:
1. **Clean AGY target strings** in `_extract_tool_target`: strip matching outer JSON quotes (e.g. `json.loads` when a string starts and ends with `"`, falling back cleanly) so paths and basenames never carry stray `"` characters.
2. **Line-range-aware repeated reads** in `analyze_transcript`:
   - Extract optional `(start, end)` line ranges for `read_file`/`view_file`/`Read` calls (`StartLine`/`EndLine` in AGY; `offset`/`limit` in Claude; full-file reads treated as `(1, inf)`).
   - Group reads by normalized file path and only count a file as a **repeated read** (in `repeated_reads` and `flags`) when at least two reads **overlap** in line range (e.g. two full-file reads, or `[1-250]` and `[1-120]`). Disjoint slices (`[1-120]` and `[480-560]`, or `[1-160]` and `[161-320]`) must NOT be flagged as repeated reads.
   - Include `overlap_reads` (or accurate overlapping count) and keep `repeated_reads` schema backwards-compatible (`file`, `count`, `est_tokens`, plus optional `overlapping_ranges` if helpful).
3. **True tool output sizes via sibling `transcript_full.jsonl`**:
   - When `path` is an AGY `transcript.jsonl` and a readable sibling `transcript_full.jsonl` exists in the same directory, read `GENERIC` row character sizes from `transcript_full.jsonl` (aligned by row/tool order; fall back gracefully to `transcript.jsonl` if absent, unreadable, or mismatched) so `top_tool_outputs` and `Large <tool> output` flags reflect actual untruncated sizes rather than the ~1.0k compact cap. Keep reading token usage / tool calls cleanly without breaking single-file synthetic test fixtures where only `transcript.jsonl` exists.
4. **Phase & turn-cost breakdown** in `analyze_transcript` and `cmd_holes`:
   - Classify each turn with tokens into one of four sequential phases:
     - `startup`: turns through the job claim (`job.py take` or `startup.py`, or turn 1 if neither appears)
     - `explore`: turns after `startup` up to (not including) the first file edit (`edit_file`/`write_file`/`Edit`/`Write`)
     - `code+test`: from the first file edit through the last edit or test run (`job.py test`, `quicktest.sh`, `featuretest.sh`, `pytest`, `unittest`)
     - `post-test tail`: turns strictly after the final edit/test run (bookkeeping, handoff, `job.py done`, summary)
   - Return a `phases` list/dict in `analyze_transcript` (turns, total prompt tokens = `input + cache_read + cache_create`, output tokens, share of total prompt tokens) and print a compact `Phases:` table in `cmd_holes`.
   - Add actionable flags for real turn×context waste:
     - **Post-test tail:** flag when `post-test tail` has `>= 5` turns AND accounts for `>= 20%` of total prompt tokens (showing turns, tokens, and `%`).
     - **Unbatched lookup streak:** flag when `explore` has a streak of `>= 4` consecutive turns that each make only 1 read/search tool call while context is `>= 40k` tokens.
     - **Duplicate immediate command:** flag when two consecutive turns run the exact same shell command (e.g. `job.py take` failing in sandbox then retried).
5. Rules (with purpose, P44):
   - Keep `tools/usage.py` stdlib-only (no third-party imports, matching T126) and fail-open on missing/malformed `transcript_full.jsonl` so existing tests and sandboxed calls never crash.
   - Keep existing `analyze_transcript` return keys (`path`, `turns`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens`, `cache_hit_pct`, `ctx_start`, `ctx_median`, `ctx_peak`, `flags`, `top_tool_outputs`, `repeated_reads`) intact so `--json` callers and existing tests keep working.

Checks (new, named) in `tools/test_usage.py`:
1. Quoted AGY tool target strings (`"\"/path/to/presenter.gd\""`) are unquoted cleanly in `top_tool_outputs` and `repeated_reads`.
2. Disjoint `read_file` line ranges (`[1-120]` + `[480-560]`, `[1-160]` + `[161-320]`) are NOT flagged as repeated reads, while overlapping ranges (`[1-250]` + `[1-120]`) and repeated full-file reads ARE flagged.
3. When sibling `transcript_full.jsonl` exists beside `transcript.jsonl`, `top_tool_outputs` uses its untruncated `GENERIC` sizes; when absent, it falls back cleanly to `transcript.jsonl`.
4. Phase breakdown (`startup`, `explore`, `code+test`, `post-test tail`) plus flags for a long post-test tail, an unbatched high-context exploration streak, and a back-to-back duplicate command all trigger accurately on synthetic AGY transcripts and stay silent on clean lean transcripts.

Reading path: `tools/usage.py` (`_extract_tool_target`, `analyze_transcript`, `cmd_holes`, lines 996–1148 and 1793–1862) → `tools/test_usage.py` (`test_analyze_claude_transcript`, `test_analyze_agy_transcript`, lines 193–288).

Run `python3 -m unittest tools/test_usage.py` while building, then `python3 tools/job.py test`. End your response with `Follow-up:` lines for leftovers and a `Result:` line.
