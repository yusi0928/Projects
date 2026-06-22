# Weekly KPI Diagnostics Summary

Generated at: `2026-06-22T21:54:13`

## Diagnostic Frame

- Source mart: `data/marts/mart_weekly_cs_kpi_by_country_reason.csv`
- Latest week: `2026-04-20`
- Baseline: previous 4 weeks (2026-03-23, 2026-03-30, 2026-04-06, 2026-04-13)
- Grain: weekly country/contact-reason KPI mart.
- Purpose: identify KPI movements that deserve analyst validation before AI-assisted WBR narration.

## Executive Snapshot

| Metric | Latest | Baseline | Change | Read |
| --- | ---: | ---: | ---: | --- |
| Contact volume | 354 | 351 | +3 (+1%) | up |
| AHT | 7.6 min | 8.2 min | -0.59 | better |
| FCR | 89.7% | 92.5% | -2.8 pp | worse |
| CSAT | 4.11 | 3.99 | +0.12 | better |
| Backlog | 123 | 127 | -4 (-3%) | better |
| Compensation cost | EUR 996 | EUR 1,204 | -209 (-17%) | better |
| Cancellation rate | 4.4% | 4.4% | -0.1 pp | better |
| Contact rate | 10.1% | 10.4% | -0.3 pp | better |

## Top Diagnostic Signals

| Segment | Metric | Latest vs baseline | Severity | Analyst hypothesis |
| --- | --- | ---: | --- | --- |
| Poland / Account issue | CSAT | 3.00 vs 4.50; -1.50 | high | Customer sentiment weakened. Validate response count, complaint themes, and whether FCR or AHT also deteriorated. |
| Austria / Payment issue | CSAT | 3.67 vs 4.62; -0.96 | high | Customer sentiment weakened. Validate response count, complaint themes, and whether FCR or AHT also deteriorated. |
| United Kingdom / Cancellation | CSAT | 3.50 vs 4.27; -0.77 | high | Customer sentiment weakened. Validate response count, complaint themes, and whether FCR or AHT also deteriorated. |
| United Kingdom / Cancellation | FCR | 85.7% vs 100.0%; -14.3 pp | high | Resolution quality weakened. Validate reopen reasons, policy ambiguity, and agent coaching opportunities. |
| Netherlands / Payment issue | CSAT | 3.33 vs 4.00; -0.67 | high | Customer sentiment weakened. Validate response count, complaint themes, and whether FCR or AHT also deteriorated. |
| Netherlands / Late delivery | FCR | 82.1% vs 93.8%; -11.6 pp | high | Resolution quality weakened. Validate reopen reasons, policy ambiguity, and agent coaching opportunities. |
| Poland / Late delivery | FCR | 72.7% vs 84.0%; -11.3 pp | high | Resolution quality weakened. Validate reopen reasons, policy ambiguity, and agent coaching opportunities. |
| Germany / Payment issue | FCR | 85.7% vs 96.4%; -10.7 pp | high | Resolution quality weakened. Validate reopen reasons, policy ambiguity, and agent coaching opportunities. |

## Quality And Interpretation Notes

- This diagnostic uses synthetic data and should be treated as a portfolio workflow pattern, not a real business finding.
- `cancellation_rate` and `total_orders` are country-week metrics repeated across contact-reason rows in the mart; the script deduplicates country-week orders for top-line summaries.
- CSAT signals with low survey counts should be validated before being used in a leadership narrative.
- Hypotheses are rule-based analyst prompts; they are not causal claims.
