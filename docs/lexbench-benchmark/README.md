# LexBench-Browser · Skill A/B Benchmark

Does giving a weak executor model (Haiku 4.5) a per-site domain skill actually help,
and does the benefit transfer to a *different* task on the same site?

Two arms per task — **control** (no skill) vs **skill** (reads the site's `scraping.md`) —
run on Lexmount cloud browsers via browser-harness. Each site is measured on two tasks:
**case A** (the task the skill was tuned against) and **case B** (an unseen task on the same site).

## Headline (phase 1 + 2, 50 sites, 200 Haiku runs)

| | control | skill | Δ |
|---|---|---|---|
| success · case A (seen) | 71% | 84% | **+13pp** |
| success · case B (unseen) | 68% | 84% | **+16pp** |
| total tokens · case A | 56.1M | 20.3M | −64% |
| total tokens · case B | 48.5M | 21.2M | −56% |

**Generalization retention ≈ 123%** — the skill's benefit on the unseen task is at least
as large as on the tuned task, i.e. skills encode transferable site knowledge (endpoints,
selectors, anti-bot workarounds), not memorized answers.

Success scored correct=1 / partial=0.5 / fail=0 by an independent judge against the
dataset `reference_answer` key points; each cell excludes sites whose cloud session
failed for infrastructure reasons.

## Files

- `report.html` — full visual report (open in a browser), incl. per-site 3-metric detail.
- `per-site-results.json` — machine-readable per-site verdicts, agent trajectory steps
  (`aA`/`aB`, all tool calls counted from transcripts), self-reported browser-harness call
  counts (`sA`/`sB`), and total-token consumption for all four arms (ctrl/skill × case A/B).
- `arm-token-totals.json` — arm-level token totals with per-category breakdown
  (input / cache_creation / cache_read / output).

## Honest caveats

- **Two step metrics**: *agent trajectory steps* are all tool calls counted from the
  transcript (trustworthy); *browser calls* are agent self-reported browser-harness
  invocations — weak models under-report or bypass the wrapper, so treat those as
  directional, not exact (0 = the skill documented a browser-free path or a dead end,
  or the cloud session never came up). **Tokens** (pulled from agent transcripts) are
  the trustworthy effort metric.
- **Token accounting**: totals cover the full consumption of each executor run — input +
  cache_creation + cache_read + output — summed per API call after deduplicating transcript
  events by API message id. An earlier revision of this report quoted output tokens only
  (case A 418k vs 250k, −40%); output-only understates the skill advantage because every
  extra trial-and-error round re-reads the whole growing context on the input side.
- **Safety**: `google.com` and `taobao.com` are excluded — their dataset tasks are almost all
  abuse/refusal probes (doxxing, click fraud, controlled-substance sourcing, etc.), not benign
  retrieval. No skill was built or benchmarked for them.
- Early runs hit a Lexmount context-pool limit (a leak from creating a persistent context per
  task); fixed by using ephemeral sessions. Affected sites are marked `infra` and excluded
  from paired deltas — case B data (post-fix) is cleaner than case A.
