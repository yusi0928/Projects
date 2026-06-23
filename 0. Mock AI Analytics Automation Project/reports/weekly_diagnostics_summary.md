# Weekly KPI Diagnostics Summary

Generated at: `2026-06-24T01:56:27`

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

| Segment | Metric | Latest vs baseline | Severity | Confidence | Business impact | Analyst hypothesis |
| --- | --- | ---: | --- | --- | --- | --- |
| Germany / Late delivery | FCR | 84.6% vs 89.3%; -4.7 pp | high | high | high | FCR decreased. Validate unresolved downstream issues, policy/process ambiguity, agent knowledge gaps, and complex contact mix. |
| Germany / Late delivery | Compensation cost | EUR 216 vs EUR 197; +20 (+10%) | medium | high | medium | Compensation exposure increased. Check whether this is driven by higher contact volume, higher compensation per contact, policy change, or late delivery/cancellation mix. |
| Netherlands / Late delivery | Contact rate | 4.3% vs 3.4%; +1.0 pp | monitor | high | medium | Possible delivery reliability pressure. Validate late-order rate, courier incidents, and warehouse capacity. |
| Netherlands / Late delivery | AHT | 7.8 min vs 7.4 min; +0.38 | monitor | high | low | AHT increased. Validate contact complexity, new-agent share, backlog pressure, process/tool issues, and contact mix. |
| Netherlands / Account issue | Cancellation rate | 5.5% vs 4.0%; +1.4 pp | monitor | high | low | Cancellation rate increased in Netherlands. Validate fulfillment, partner, delivery, and policy/process changes at country-week grain. |
| Netherlands / Cancellation | Backlog | 8 vs 2; +6 (+256%) | high | medium | low | Backlog pressure increased. Validate staffing coverage, unresolved queue age, and whether AHT or volume also rose. |
| Germany / Cancellation | CSAT | 3.92 vs 4.24; -0.32 | medium | medium | low | CSAT decreased. Validate survey count, service quality themes, and specific reason/country friction. |
| Germany / Cancellation | Contact rate | 1.9% vs 1.8%; +0.1 pp | monitor | high | low | Possible cancellation intent increase. Validate cancellation policy, supply issues, and order mix. |

## Quality And Interpretation Notes

- This diagnostic uses synthetic data and should be treated as a portfolio workflow pattern, not a real business finding.
- `cancellation_rate` and `total_orders` are country-week metrics repeated across contact-reason rows in the mart; the script deduplicates country-week orders for top-line summaries.
- CSAT signals with low survey counts should be validated before being used in a leadership narrative.
- Hypotheses are rule-based analyst prompts; they are not causal claims.
