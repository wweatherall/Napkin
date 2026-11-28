### H216 — Reading cost per job: what each agent read before and while doing its job, from the saved transcripts (T175)

Author: Claude (integrator, integrator-opus) | Date: 2026-11-28 | Status: answered | For: Codex | Item: T175

References: T175 (ChatGPT's review, 2026-11-28: tell "better documentation" — agents find what they need faster —
from "better architecture" — they need less in the first place); William, 2026-11-28: "put it on the board"; T117 (the
usage ledger); `comitatus/09_Tools/MEASURE_TOKEN_USE.py` (`holes`, `discover_transcript`, `analyze_transcript`,
`list_agy_transcripts`, `load_codex_sessions`); C06, C07.

Today: `MEASURE_TOKEN_USE.py holes <job>` finds a job's transcript from the ledger (`.git/shopsketch-usage.jsonl`,
`latest_records_by_job`; `backfill` fills it) through `discover_transcript`, which knows Claude
(`~/.claude/projects/**/<session>.jsonl`) and Gemini (`~/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/
transcript.jsonl`) but not Codex (`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, `load_codex_sessions` reads their
token and quota events only). `analyze_transcript` gives phases, token totals and the biggest tool outputs; nothing counts
what was read. On hand (2026-11-28): the project started 2026-11-20; about 130 Gemini and 120 Codex transcripts, about
12 Claude ones (older Claude ones are gone); 211 archived jobs in `docs/handoff-archive.md`. The script lives in the
comitatus repository, outside this repo's job branches, so the new code goes in this repo's tools/ and imports it (as
`tools/job.py` `_usage_tool` finds it); moving it into comitatus later is a separate step.

Touches: tools/reading_cost.py (new), tools/test_reading_cost.py (new), tests/reading_cost.json (new, generated).
The integrator adds its line to the tools README at merge.

Request:
1. For one job, find its transcript for any of the three agents (reuse `discover_transcript` for Claude and Gemini; add
   Codex by the session id the ledger or the job queue (`.git/napkin-jobs.json` entry `session`) records, matching the
   rollout's `session_meta` id) and measure, from its tool calls:
   - source files read (distinct paths, repo-relative, worktree prefix stripped so `.worktrees/Napkin/h214/tools/x.py`
     and `tools/x.py` are one file), split into code, tests, docs (`*.md`, `03_Past_Decisions/`) and other;
   - lines read: unique (file, line) pairs and repeated ones (the same lines read again), from the ranges each read
     asked for (a whole-file read counts the file's line count at the job's merge commit, or now if that's gone);
     searches (`grep`, `rg`) count their output lines as read, kept separate;
   - tokens before the first edit (the first file write or edit tool call), and total;
   - files the job changed (from its merge commit: `git show --stat`), and lines changed.
   Agents call their tools differently (Claude `Read`/`Edit`/`Bash`, Gemini `read_file`/`run_command`, Codex
   `exec_command`/`apply_patch`, shell `cat`/`sed -n`/`head`): map each to "read a range", "search", "edit" or "other"
   in one table at the top of the file, so a new tool name is one line.
2. `python3 tools/reading_cost.py --all` measures every archived job it can find a transcript for and writes
   `tests/reading_cost.json`: per job, its agent, model, merge date, kind and the numbers above. Kind: from the files
   changed (worker op, viewport tool, tools/process, docs only, mixed), so like is compared with like. A job with no
   transcript is listed with the reason, not left out silently.
3. `--report` prints, for each kind, the jobs in date order with their numbers and a median per day, so a trend (or none)
   shows; and flags the jobs that read the most docs relative to code (documentation doing the work) or the most code per
   line changed (architecture making them read). Say in your response what the numbers show and how far to trust them.
4. Read-only on the transcripts: never write into `~/.claude`, `~/.gemini` or `~/.codex`.

What can fail:
- A job ran in more than one session (returned and resumed, or stacked): count every session the queue recorded for
  it, and say so in its row.
- A Gemini transcript holds two jobs (a worker that took a second job): split at the second `GET_A_JOB` call and say so.

Checks:
- `tools/test_reading_cost.py` (summary line `READING COST TESTS: N passed, M failed`): a small fake transcript of each of
  the three formats gives the expected files, unique and repeated lines, tokens before the first edit; a worktree path
  and a repo path count as one file; an unknown tool name counts as "other", not an error.
- Run it for real, commit `tests/reading_cost.json`, paste the report into your response.
- `tools/TEST_BEFORE_MERGING.sh` passes.

#### Response — Codex, 2026-11-28

Branch `codex/h216-reading-cost-per-job` · implementation `f1b732c`.

`python3 tools/reading_cost.py H211` matched the H211 row in the committed snapshot.
`--all` measured 134 of 211 archived jobs, including 10 jobs with multiple sessions, and listed reasons for the 77 missing
transcripts. The fixture suite covers all three agents, legacy and structured Codex records, repeated ranges and path
aliases, a two-job Gemini session, a job across sessions, and first-parent Git diffs. Eight fixtures passed.
The merge gate passed (QUICK 439 passed, 0 failed).

Viewport jobs went from 2,537 unique lines per job on November 22 (6 jobs) to 578 on November 26 (2 jobs), then
back up to 2,171 on November 28 (3 jobs). Worker jobs also fell and rebounded, and tools/process jobs varied from
789 to 2,597 across the daily medians. The snapshot shows no sustained decline. H078 leads on docs/code
(146/21) with a small code denominator. H096 leads on code/changed lines (4,218/169). These ratios identify
jobs to review. Establishing that documentation or architecture caused either result requires comparable jobs,
because the mix of agents and job sizes changes day to day.

The numbers cover requested file ranges that can be resolved, output lines from identifiable searches, and recorded
token usage including cached input. Shell wrappers, truncated output and files absent at both merge and measurement
limit coverage. The change counts come from the first-parent Git diff, including bookkeeping. H098 was stacked with
H093 and has no separately attributable merge diff.

Changed from the brief: historical jobs without a ledger or queue session can also match by a successful claim
recorded by the tool itself, so recoverable transcripts survive queue pruning.
Changed from the brief: the commit hook regenerated `ARCHITECTURE.md` for the new tool.
Changed from the brief: the commit hook regenerated `docs/dependency-map.md` for the new module.
Architecture: `tools/reading_cost.py` owns read normalization, job attribution and the `tests/reading_cost.json` snapshot.
Architecture: `tools/reading_cost.py` uses comitatus's `MEASURE_TOKEN_USE.py` for ledger and archive readers and
Claude/Gemini transcript discovery. Codex rollout matching uses the saved session metadata ID.
For the integrator: add the `reading_cost.py <H0NN>` / `--all` / `--report` entry in `tools/README.md`.

<details>
<summary>Full reading-cost report</summary>

```text
Reading cost: 134/211 jobs measured, 77 missing transcripts
Reads use requested ranges; search lines are separate. Tokens include cached input and output.
Day medians use the measured jobs with each metric. Δ lines are added + deleted.
Search counts are lower bounds when search results share a combined tool output.

worker op (8)
Date        Job / agent            Files  Unique  Repeat  Search  Pre-edit tokens  Total tokens  Δ files  Δ lines
2026-11-22  H087 gemini             13   2,882       1      60          572,583     2,351,028        9      481
2026-11-22  H090 gemini             22   2,631     280      24          461,845     3,557,604       10      742
2026-11-22  H095 gemini             15   2,666       3       0          620,234     1,787,845        7      162
            median (3)              15   2,666       3      24          572,583     2,351,028        9      481
2026-11-26  H151 gemini              8   1,184       0      99          419,317     1,620,462        6      230
2026-11-26  H155 gemini              5     518       8     147          191,996     1,491,981        6      203
            median (2)             6.5     851       4     123        305,656.5   1,556,221.5        6    216.5
2026-11-27  H173 gemini             14   3,280       4     254        1,112,023     9,864,709       19    2,135
2026-11-27  H184+ gemini             7     909     375     151           91,157     1,978,452        7      234
2026-11-27  H194 gemini              9   1,232       1      75          321,587     1,419,134       10      280
            median (3)               9   1,232       4     151          321,587     1,978,452       10      280

viewport tool (28)
Date        Job / agent            Files  Unique  Repeat  Search  Pre-edit tokens  Total tokens  Δ files  Δ lines
2026-11-22  H071 codex              19   2,610     809      48          350,871     4,415,218       12      297
2026-11-22  H072 claude             11   1,689       1     144          555,142     3,014,974       11      205
2026-11-22  H075 codex              16   2,464     369     337          303,847     1,698,911        9      217
2026-11-22  H079 codex              20   4,829   2,855     348          483,234     3,489,378       11      713
2026-11-22  H083 codex              23   3,219     745     282          647,853     7,326,331       21      742
2026-11-22  H102 gemini             14   1,525       0       1          315,992     1,980,315        7      852
            median (6)            17.5   2,537     557     213        417,052.5     3,252,176       11      505
2026-11-23  H096 gemini             20   6,007     133      41        2,469,643     5,002,040       10      169
2026-11-23  H103 gemini             22   6,308       0      78          802,568     7,369,511       15      748
2026-11-23  H107 codex              11   2,706     776     190          307,465     1,773,606       12      763
2026-11-23  H108 codex              10   1,266       0     224          406,933     2,056,053       10      710
2026-11-23  H109 gemini             15   2,933       6      85          272,205     2,007,674       17      398
2026-11-23  H110 codex              21   2,171       0     296          306,389     3,207,793       14      529
2026-11-23  H111 codex              17   1,758       9     298          312,715     2,584,674       11      507
2026-11-23  H112 codex              19   1,716      23     156          418,215     2,652,262       11      223
2026-11-23  H113 codex              18   1,822       1     249          311,109     3,910,826       17      378
2026-11-23  H114 gemini             15   2,091       0      73          283,980     1,883,281       15      204
            median (10)           17.5   2,131     3.5     173          311,912     2,618,468       13    452.5
2026-11-24  H136 gemini             17   2,533       6      92        1,038,955     2,063,663       10      265
2026-11-24  H137 gemini              8   1,305       6      22          262,895     1,097,553        7      233
2026-11-24  H138+ gemini             9   1,746     941     112          274,063     3,671,320        8      517
            median (3)               9   1,746       6      92          274,063     2,063,663        8      265
2026-11-26  H148 claude              3     277       0      12          371,478     1,096,525        7      115
2026-11-26  H149 claude              9     878       0       7          321,510       655,024       10       91
            median (2)               6   577.5       0     9.5          346,494     875,774.5      8.5      103
2026-11-27  H177 gemini              6   1,387       2     145          546,985     2,403,940       11      829
2026-11-27  H181 gemini              5   1,062     344     115          233,436     1,631,823        9      622
2026-11-27  H187 gemini              5     837       0      89          191,619       892,427       10      412
2026-11-27  H188 gemini              5     971       0      91          281,333     1,321,799        9      776
            median (4)               5 1,016.5       1     103        257,384.5     1,476,811      9.5      699
2026-11-28  H202 codex              24   2,171       2      45          520,557     3,196,817        9      470
2026-11-28  H209 codex              21   1,568     118      93          240,519     3,205,513       10      141
2026-11-28  H210 codex              17   2,188     108     454          302,134     2,667,605       11      273
            median (3)              21   2,171     108      93          302,134     3,196,817       10      273

tools/process (52)
Date        Job / agent            Files  Unique  Repeat  Search  Pre-edit tokens  Total tokens  Δ files  Δ lines
2026-11-22  H053 claude              7     560       4     127          587,980     1,355,726       10      328
2026-11-22  H054 claude              7     756       0       0          389,244     1,135,724        8      610
2026-11-22  H055 claude              7     621       0      24          453,896       759,926        9      171
2026-11-22  H060 claude              8     840       1      25          573,752     1,309,527       12      323
2026-11-22  H061 claude              6     971      19       3          560,810     1,624,500       11      261
2026-11-22  H068 claude             11   1,800     405      60        1,026,123     3,655,457       10      307
2026-11-22  H073 claude              8     956      94      44          531,328     3,542,127       11      301
2026-11-22  H076 codex               8   1,402     113      76          229,861     1,991,543        9      156
2026-11-22  H077 codex               8   1,874     551      16          300,276     2,523,224        6      368
2026-11-22  H080 codex              12   1,520     159     152          294,055     1,964,410        6      157
2026-11-22  H081 codex              19   1,324     272     125          272,361     2,531,459       12      334
2026-11-22  H088 gemini             13   3,705     196       0          446,884     1,324,307        9      319
2026-11-22  H091 gemini             10   2,057       0       0          367,304       930,289        7      225
2026-11-22  H099 gemini             13   3,537     118      21          381,800     2,089,673        6      203
            median (14)              8   1,363   103.5    24.5          418,064     1,794,455        9      304
2026-11-23  H104 gemini             10   3,857     294      55          678,721     3,979,462       11      568
2026-11-23  H105 gemini             11   2,597       6      95          680,163     2,227,957        8      349
2026-11-23  H115 codex               6     891      91      52          219,986     1,802,483       10      304
2026-11-23  H119 codex              13   1,949     559      34          349,604     2,729,154       10      464
2026-11-23  H120 codex               9   1,058     239     132          224,095     2,369,033       11      395
2026-11-23  H123 gemini             13  13,129     131      44          433,838     1,212,885       12      258
2026-11-23  H124 gemini              5   3,157      16       0          226,577     1,439,590       10      315
            median (7)              10   2,597     131      52          349,604     2,227,957       10      349
2026-11-24  H140 gemini             14   2,598      54      68          470,578     3,781,157       10    3,031
2026-11-24  H142 gemini              6   2,209      94       0          294,792     1,445,696        9      278
2026-11-24  H144 gemini              3     522       0       2          127,808       702,810        7      846
2026-11-24  H146 gemini              7   2,540       0      16          423,884     2,267,290        8      348
2026-11-24  H147 gemini             15     627       0      99          172,164       543,124       17      127
            median (5)               7   2,209       0      16          294,792     1,445,696        9      348
2026-11-26  H152 gemini             21   2,655       3     101          749,352     4,910,786      242    4,067
2026-11-26  H153 gemini             24   5,210      51      78        1,506,546     4,951,269      204    2,816
2026-11-26  H154 gemini             34   2,219      23      58          877,590     4,780,944       67      947
2026-11-26  H156 gemini             15   2,471      35     118        1,334,708     4,223,170       13      397
2026-11-26  H157 gemini             14   2,876      24      90          942,000     2,290,894       80      567
2026-11-26  H158 gemini             11   1,192      79       5          222,390     1,237,448       12      377
2026-11-26  H159 gemini              8     810       6     146          192,923     1,360,304       13      365
2026-11-26  H160 gemini              8     974       0      65          307,532     1,905,870       14      589
2026-11-26  H162 gemini              5     474       6      30          355,595     1,349,850       15    3,713
            median (9)              14   2,219      23      78          749,352     2,290,894       15      589
2026-11-27  H163 gemini              9   1,770       6      16          467,160     1,781,296       12      480
2026-11-27  H164 gemini              8   1,239       2      42          332,093     1,667,384       13      371
2026-11-27  H166 gemini             18   2,538      61     197          421,165    11,816,531       87    1,379
2026-11-27  H168 gemini              7   1,117       1     173          550,009     2,990,907       10      547
2026-11-27  H174+ gemini            12   1,931       0     905          373,089     3,787,958       12    1,396
2026-11-27  H175 gemini             15   3,101       7     166        1,445,429     7,193,684       17      663
2026-11-27  H180 gemini             11   1,978       2     138          550,305     2,304,548       12      474
2026-11-27  H185 gemini             12   3,767      25      32          715,041     4,939,617       13      914
2026-11-27  H186 gemini              1      37      30       0           36,383       451,898       13      210
2026-11-27  H190 gemini              4   1,143       6      52          924,962     2,804,550        6      258
2026-11-27  H196 gemini              8   1,255       1      91          316,419     2,512,508       12      527
2026-11-27  H197 gemini             12   1,854       2     290          996,721     3,378,194       13      651
2026-11-27  H203+ gemini            11   2,124       6     254          617,682     2,901,637       11      633
2026-11-27  H205 gemini             12   1,769      16      75          909,676     3,100,959       14      593
2026-11-27  H207 gemini              7   2,707      12     258          975,912     5,088,837       11      987
            median (15)             11   1,854       6     138          550,305     2,990,907       12      593
2026-11-28  H214 gemini              5     424       0      35          385,976     2,097,112       10   17,249
2026-11-28  H215 gemini              6   1,154       0      42          255,885     2,151,553       13    5,699
            median (2)             5.5     789       0    38.5        320,930.5   2,124,332.5     11.5   11,474

docs only (6)
Date        Job / agent            Files  Unique  Repeat  Search  Pre-edit tokens  Total tokens  Δ files  Δ lines
2026-11-22  H070 claude              3     144      64      64          512,038     1,667,315        8      264
2026-11-22  H078 claude              4     167      50      35          478,828     2,046,565        7      331
            median (2)             3.5   155.5      57    49.5          495,433     1,856,940      7.5    297.5
2026-11-27  H179 gemini             11   1,910       6      73          562,408     1,184,474        9      246
2026-11-27  H193 gemini             20   2,151       6      92          357,263     1,482,937        6      256
2026-11-27  H195 codex              12     621       0     423          353,704     2,050,570        5      130
2026-11-27  H206 codex              12     880       0      38          852,898     3,555,129        5      102
            median (4)              12   1,395       3    82.5        459,835.5   1,766,753.5      5.5      188

mixed (39)
Date        Job / agent            Files  Unique  Repeat  Search  Pre-edit tokens  Total tokens  Δ files  Δ lines
2026-11-22  H052 gemini             42  10,588     194      42        2,946,413     9,643,699       26    1,434
2026-11-22  H057 claude              7     154      10     121          540,387     1,969,714       18      287
2026-11-22  H069+ claude + codex    25   5,972     611      84          644,954    14,372,074        8      192
            median (3)              25   5,972     194      84          644,954     9,643,699       18      287
2026-11-23  H085 codex              33   3,157     190     129          938,323     6,820,020       24    1,008
2026-11-23  H086 codex              28   3,185     235     178          349,849     3,909,785        8      384
2026-11-23  H093+ codex             21   4,161   3,827     526          324,271    11,486,403       14    1,285
2026-11-23  H094 codex              20   2,467     216      94          320,856     2,734,226       10      349
2026-11-23  H097 gemini             12   2,513       1       0          129,616     2,076,865       10    1,954
2026-11-23  H121 codex              25   2,545     281     257          212,399     2,949,581       10      288
            median (6)              23   2,851   225.5   153.5        322,563.5     3,429,683       10      696
2026-11-24  H125 gemini             10   2,128       0      61          358,201     2,717,857       17      552
2026-11-24  H126 gemini             12   3,380       0       0          613,444     2,978,372       14      514
2026-11-24  H127+ gemini + claude    14   2,226      59     260          575,317     4,039,441       12      606
2026-11-24  H128+ gemini            19   3,135   3,173      43          977,251     3,201,498       15      630
2026-11-24  H129+ gemini            19   2,695     377     231          448,162     6,080,361       15      407
2026-11-24  H139 gemini             10   3,244      82       5          444,590     1,970,303       15      511
2026-11-24  H141 gemini             13   2,088       3     150          444,920     2,681,112       14      484
            median (7)              13   2,695      59      61          448,162     2,978,372       15      514
2026-11-25  H130 claude             23   3,501     650     280          548,808     3,197,669       23      651
            median (1)              23   3,501     650     280          548,808     3,197,669       23      651
2026-11-26  H150 gemini             12   1,767       0     157          494,752     2,948,252       11      620
            median (1)              12   1,767       0     157          494,752     2,948,252       11      620
2026-11-27  H161 gemini             13   1,769       0     106          149,587     4,446,950       15      432
2026-11-27  H165 gemini             11   1,223       0       0          404,581     1,489,418       13      561
2026-11-27  H167 gemini             13     718      60      40           34,764     5,644,734       64      912
2026-11-27  H169 gemini             15   1,947     136      51          593,839     2,588,730       12    1,420
2026-11-27  H170 gemini             13   1,030       0     247          332,665     1,545,393       13      186
2026-11-27  H171 gemini             17   2,480       6     257          786,086     3,368,581       21      435
2026-11-27  H172 gemini              8   1,021       2      65          357,371       929,025        9      145
2026-11-27  H176 gemini              8   1,098       0      19          280,927     1,103,319       15      184
2026-11-27  H178 gemini              7     561       0      40          161,778     1,170,924       12      386
2026-11-27  H182 gemini              6     834       0      56          147,742     1,041,683        8      161
2026-11-27  H183 gemini             17   1,467       0     133          295,808     1,775,070       21      244
2026-11-27  H189 gemini             17   1,926       6      30          297,211     2,136,959       14      626
2026-11-27  H191 gemini             19   2,346       8      87          878,426     3,070,778       13      553
2026-11-27  H192 gemini             23   2,734     116      34          975,603     3,015,042       18      602
2026-11-27  H198 gemini             14   1,487      49     328          873,784     3,647,467       15      285
2026-11-27  H199 gemini             42   4,399      68     412        2,886,059    22,133,041       85    4,553
2026-11-27  H200 gemini             21   2,561      13     346          867,243     3,694,861       28      245
2026-11-27  H204 gemini             13   1,139      59      20          760,344     4,990,145       97    5,560
            median (18)           13.5   1,477       6    60.5          380,976     2,801,886       15    433.5
2026-11-28  H201+ gemini + codex    38   5,929   2,445     948        2,499,758    25,433,161       28    1,142
2026-11-28  H208 codex              28   2,357     372     362          111,583     6,409,306       22      398
2026-11-28  H211 codex              57   6,575     977     603          223,578    13,304,548       34      839
            median (3)              38   5,929     977     603          223,578    13,304,548       28      839

unknown (1)
Date        Job / agent            Files  Unique  Repeat  Search  Pre-edit tokens  Total tokens  Δ files  Δ lines
2026-11-23  H098 gemini             17   4,993       0       2          889,724     5,287,865        –        –
            median (1)              17   4,993       0       2          889,724     5,287,865        –        –

+ multiple sessions, * shared transcript split at claim, ? recorded session unavailable
Highest docs / code (unique lines; both present)
  H078      6.95  (146 / 21)
  H070      2.51  (103 / 41)
  H162      2.26  (219 / 97)
  H069      1.68  (3,281 / 1,956)
  H148      1.50  (166 / 111)
Highest code / changed line (unique code lines; changes present)
  H096     24.96  (4,218 / 169)
  H095     11.23  (1,819 / 162)
  H069     10.19  (1,956 / 192)
  H099     10.01  (2,032 / 203)
  H088      6.76  (2,156 / 319)

Missing transcript
no ledger entry, queue session or transcript claim: H001, H002, H003, H004, H005, H006, H007, H008, H009, H010, H011, H012, H013, H014, H015, H016, H018, H019, H020, H021, H022, H023, H024, H025, H026, H027, H028, H029, H030, H031, H032, H033, H034, H035, H036, H037, H038, H039, H040, H041, H042, H043, H044, H045, H046, H047, H048, H049, H050, H051, H056, H058, H059, H065, H066, H074, H082, H084, H089, H092, H100, H101, H106, H116, H117, H118, H131, H132, H133, H134, H135, H143, H145
recorded session or transcript unavailable: H062, H063, H064, H122
```

</details>

Result: f1b732c; 8 reading-cost fixtures and the full merge gate including QUICK 439 passed, 0 failed; added a read-only transcript analyzer and archived reading-cost snapshot for T175.
