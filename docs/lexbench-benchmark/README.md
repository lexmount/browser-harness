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
| output tokens · case A | 418k | 250k | −40% |
| output tokens · case B | 520k | 288k | −45% |

**Generalization retention ≈ 123%** — the skill's benefit on the unseen task is at least
as large as on the tuned task, i.e. skills encode transferable site knowledge (endpoints,
selectors, anti-bot workarounds), not memorized answers.

Success scored correct=1 / partial=0.5 / fail=0 by an independent judge against the
dataset `reference_answer` key points; each cell excludes sites whose cloud session
failed for infrastructure reasons.

## Files

- `report.html` — full visual report (open in a browser), incl. per-site 3-metric detail.
- `per-site-results.json` — machine-readable per-site verdicts, self-reported steps, and
  output-token totals for all four arms (ctrl/skill × case A/B).
- `arm-token-totals.json` — arm-level aggregate token totals as reported by the harness.

## Honest caveats

- **Steps** are agent self-reported browser-harness call counts — weak models under-report
  or bypass the wrapper, so treat step counts as directional, not exact. **Tokens** (pulled
  from agent transcripts) are the trustworthy effort metric.
- **Safety**: `google.com` and `taobao.com` are excluded — their dataset tasks are almost all
  abuse/refusal probes (doxxing, click fraud, controlled-substance sourcing, etc.), not benign
  retrieval. No skill was built or benchmarked for them.
- Early runs hit a Lexmount context-pool limit (a leak from creating a persistent context per
  task); fixed by using ephemeral sessions. Affected sites are marked `infra` and excluded
  from paired deltas — case B data (post-fix) is cleaner than case A.
