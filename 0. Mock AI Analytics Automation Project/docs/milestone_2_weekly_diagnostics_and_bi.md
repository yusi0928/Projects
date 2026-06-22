# Milestone 2: Weekly Diagnostics And HTML Dashboard

## Goal

Turn the governed weekly KPI mart from Milestone 1 into a practical weekly business review workflow with a reproducible local HTML dashboard.

The workflow answers:

- What changed in the latest complete week?
- Which country and contact-reason segments deserve analyst review?
- Which movements are likely operational risks versus positive improvements?
- What should be validated before any AI-assisted leadership narrative is written?

## Visualization Surface

The final visualization is `dashboard/index.html`.

The dashboard uses static HTML and inline SVG charts so it can be opened locally without external BI tools or a web server.

Dashboard sections:

- KPI cards: contact volume, AHT, FCR, CSAT, backlog, compensation cost, cancellation rate, and contact rate.
- Trend charts: contact volume, AHT, FCR, and CSAT over weekly history.
- Exception chart: top country/contact-reason signals by impact score.
- Analyst queue: segment-level signals with latest value, baseline value, change, severity, and validation prompt.

## Generated Outputs

Run:

```bash
python3 scripts/run_weekly_diagnostics.py
```

The script writes:

| Output | Purpose |
| --- | --- |
| `analysis/weekly_kpi_diagnostics.csv` | Segment-level KPI movement diagnostics |
| `analysis/weekly_country_summary.csv` | Latest-week country rollup |
| `analysis/weekly_kpi_summary.json` | Structured payload used by the dashboard generator |
| `reports/weekly_diagnostics_summary.md` | Analyst-readable weekly summary |
| `dashboard/index.html` | Final local HTML dashboard |

## Diagnostic Method

The script compares the latest complete week with the average of the previous four weeks.

Current default:

- Latest week: `2026-04-20`
- Baseline weeks: `2026-03-23`, `2026-03-30`, `2026-04-06`, `2026-04-13`
- Grain: `week_start + country_code + contact_reason_id`

Signals are ranked by:

1. Worse movements first.
2. Severity: high, medium, monitor.
3. Impact score.

The generated hypotheses are rule-based prompts for analyst validation. They are not causal claims.

## Resume Positioning

Suggested project bullet:

Built a reproducible weekly CS operations diagnostics workflow on top of a governed KPI mart, generating KPI movement analysis, exception ranking, analyst validation prompts, and a static HTML dashboard for portfolio presentation.
