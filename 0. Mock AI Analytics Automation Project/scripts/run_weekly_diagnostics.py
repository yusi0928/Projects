from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
import csv
import json
import math


ROOT = Path(__file__).resolve().parents[1]
MART_PATH = ROOT / "data" / "marts" / "mart_weekly_cs_kpi_by_country_reason.csv"
ANALYSIS_DIR = ROOT / "analysis"
REPORTS_DIR = ROOT / "reports"
DASHBOARD_DIR = ROOT / "dashboard"

DIAGNOSTICS_PATH = ANALYSIS_DIR / "weekly_kpi_diagnostics.csv"
SUMMARY_JSON_PATH = ANALYSIS_DIR / "weekly_kpi_summary.json"
COUNTRY_SUMMARY_PATH = ANALYSIS_DIR / "weekly_country_summary.csv"
REPORT_PATH = REPORTS_DIR / "weekly_diagnostics_summary.md"
DASHBOARD_PATH = DASHBOARD_DIR / "index.html"

BASELINE_WEEKS = 4

METRICS = [
    "contact_volume",
    "avg_aht_minutes",
    "fcr_rate",
    "avg_csat",
    "backlog_end_of_week",
    "compensation_cost",
    "cancellation_rate",
    "contact_rate",
]

METRIC_LABELS = {
    "contact_volume": "Contact volume",
    "avg_aht_minutes": "AHT",
    "fcr_rate": "FCR",
    "avg_csat": "CSAT",
    "backlog_end_of_week": "Backlog",
    "compensation_cost": "Compensation cost",
    "cancellation_rate": "Cancellation rate",
    "contact_rate": "Contact rate",
}

RATE_METRICS = {"fcr_rate", "cancellation_rate", "contact_rate"}
LOWER_IS_BETTER = {
    "avg_aht_minutes",
    "backlog_end_of_week",
    "compensation_cost",
    "cancellation_rate",
    "contact_rate",
}
HIGHER_IS_BETTER = {"fcr_rate", "avg_csat"}


def parse_float(value):
    if value is None or value == "":
        return None
    return float(value)


def format_value(metric, value):
    if value is None:
        return "n/a"
    if metric in RATE_METRICS:
        return f"{value * 100:.1f}%"
    if metric == "compensation_cost":
        return f"EUR {value:,.0f}"
    if metric == "avg_csat":
        return f"{value:.2f}"
    if metric == "avg_aht_minutes":
        return f"{value:.1f} min"
    return f"{value:,.0f}"


def format_change(metric, change, pct_change):
    if change is None:
        return "n/a"
    if metric in RATE_METRICS:
        return f"{change * 100:+.1f} pp"
    if metric in {"avg_aht_minutes", "avg_csat"}:
        return f"{change:+.2f}"
    if pct_change is None:
        return f"{change:+,.0f}"
    return f"{change:+,.0f} ({pct_change:+.0%})"


def read_mart():
    if not MART_PATH.exists():
        raise FileNotFoundError(
            f"{MART_PATH} does not exist. Run scripts/build_sqlite_stack.py first."
        )
    with MART_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            clean = dict(row)
            for metric in METRICS:
                clean[metric] = parse_float(row.get(metric))
            clean["csat_responses"] = parse_float(row.get("csat_responses")) or 0
            clean["total_orders"] = parse_float(row.get("total_orders")) or 0
            clean["cancelled_orders"] = parse_float(row.get("cancelled_orders")) or 0
            clean["active_agents"] = parse_float(row.get("active_agents")) or 0
            clean["available_minutes"] = parse_float(row.get("available_minutes")) or 0
            rows.append(clean)
    return rows


def mean(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def weighted_mean(pairs):
    numerator = 0
    denominator = 0
    for value, weight in pairs:
        if value is None or weight is None or weight <= 0:
            continue
        numerator += value * weight
        denominator += weight
    if denominator == 0:
        return None
    return numerator / denominator


def aggregate_week(rows, week):
    week_rows = [r for r in rows if r["week_start"] == week]
    country_week = {}
    for row in week_rows:
        country_week[(row["week_start"], row["country_code"])] = row
    total_orders = sum(r["total_orders"] for r in country_week.values())
    cancelled_orders = sum(r["cancelled_orders"] for r in country_week.values())
    contact_volume = sum(r["contact_volume"] or 0 for r in week_rows)
    return {
        "week_start": week,
        "contact_volume": contact_volume,
        "avg_aht_minutes": weighted_mean(
            (r["avg_aht_minutes"], r["contact_volume"]) for r in week_rows
        ),
        "fcr_rate": weighted_mean((r["fcr_rate"], r["contact_volume"]) for r in week_rows),
        "avg_csat": weighted_mean((r["avg_csat"], r["csat_responses"]) for r in week_rows),
        "csat_responses": sum(r["csat_responses"] for r in week_rows),
        "backlog_end_of_week": sum(r["backlog_end_of_week"] or 0 for r in week_rows),
        "compensation_cost": sum(r["compensation_cost"] or 0 for r in week_rows),
        "total_orders": total_orders,
        "cancelled_orders": cancelled_orders,
        "cancellation_rate": cancelled_orders / total_orders if total_orders else None,
        "contact_rate": contact_volume / total_orders if total_orders else None,
    }


def aggregate_country(rows, week):
    grouped = defaultdict(list)
    for row in rows:
        if row["week_start"] == week:
            grouped[(row["country_name"], row["country_code"])].append(row)
    summaries = []
    for (country_name, country_code), items in grouped.items():
        total_orders = max(r["total_orders"] for r in items)
        cancelled_orders = max(r["cancelled_orders"] for r in items)
        contact_volume = sum(r["contact_volume"] or 0 for r in items)
        summaries.append(
            {
                "country_name": country_name,
                "country_code": country_code,
                "contact_volume": contact_volume,
                "avg_aht_minutes": weighted_mean(
                    (r["avg_aht_minutes"], r["contact_volume"]) for r in items
                ),
                "fcr_rate": weighted_mean((r["fcr_rate"], r["contact_volume"]) for r in items),
                "avg_csat": weighted_mean((r["avg_csat"], r["csat_responses"]) for r in items),
                "backlog_end_of_week": sum(r["backlog_end_of_week"] or 0 for r in items),
                "compensation_cost": sum(r["compensation_cost"] or 0 for r in items),
                "total_orders": total_orders,
                "cancelled_orders": cancelled_orders,
                "cancellation_rate": cancelled_orders / total_orders if total_orders else None,
                "contact_rate": contact_volume / total_orders if total_orders else None,
            }
        )
    return summaries


def segment_key(row):
    return row["country_code"], row["contact_reason_id"]


def score_change(metric, current, baseline, abs_change, pct_change):
    if current is None or baseline is None or abs_change is None:
        return 0
    if metric in {"contact_volume", "backlog_end_of_week"}:
        return abs(abs_change)
    if metric == "compensation_cost":
        return abs(abs_change) / 10
    if metric in RATE_METRICS:
        return abs(abs_change) * 100
    if metric == "avg_csat":
        return abs(abs_change) * 20
    if metric == "avg_aht_minutes":
        return abs(abs_change) * max(current, baseline, 1)
    return abs(pct_change or 0) * 10


def severity(metric, abs_change, pct_change):
    if abs_change is None:
        return "monitor"
    magnitude = abs(abs_change)
    pct = abs(pct_change or 0)
    if metric in RATE_METRICS:
        if magnitude >= 0.04:
            return "high"
        if magnitude >= 0.02:
            return "medium"
        return "monitor"
    if metric == "avg_csat":
        if magnitude >= 0.35:
            return "high"
        if magnitude >= 0.2:
            return "medium"
        return "monitor"
    if metric == "avg_aht_minutes":
        if magnitude >= 1.5:
            return "high"
        if magnitude >= 0.75:
            return "medium"
        return "monitor"
    if pct >= 0.4 or magnitude >= 20:
        return "high"
    if pct >= 0.2 or magnitude >= 10:
        return "medium"
    return "monitor"


def direction(metric, abs_change):
    if abs_change is None or abs(abs_change) < 0.00001:
        return "flat"
    if metric in LOWER_IS_BETTER:
        return "worse" if abs_change > 0 else "better"
    if metric in HIGHER_IS_BETTER:
        return "better" if abs_change > 0 else "worse"
    return "up" if abs_change > 0 else "down"


def hypothesis_for(row, neighbor_signals):
    metric = row["metric"]
    reason = row["contact_reason_name"].lower()
    country = row["country_name"]
    if metric in {"contact_volume", "contact_rate"} and row["direction"] in {"up", "worse"}:
        if "delivery" in reason:
            return "Likely delivery reliability pressure. Validate against late-order rate, courier incidents, and warehouse capacity."
        if "payment" in reason:
            return "Likely payment journey friction. Validate with payment failure logs and checkout release calendar."
        if "cancellation" in reason:
            return "Likely cancellation intent increase. Validate against cancellation policy, supply issues, and order mix."
        return "Likely demand or operational friction in this contact reason. Validate with reason-level ticket samples and upstream events."
    if metric == "compensation_cost" and row["direction"] == "worse":
        return "Compensation exposure increased. Validate refund and voucher drivers, policy exceptions, and duplicate compensation controls."
    if metric == "backlog_end_of_week" and row["direction"] == "worse":
        return "Backlog pressure increased. Validate staffing coverage, unresolved queue age, and whether AHT or volume also rose."
    if metric == "avg_aht_minutes" and row["direction"] == "worse":
        return "Contacts became more complex or slower to resolve. Validate escalation share, agent tenure, macros, and tooling issues."
    if metric == "fcr_rate" and row["direction"] == "worse":
        return "Resolution quality weakened. Validate reopen reasons, policy ambiguity, and agent coaching opportunities."
    if metric == "avg_csat" and row["direction"] == "worse":
        return "Customer sentiment weakened. Validate response count, complaint themes, and whether FCR or AHT also deteriorated."
    if metric == "cancellation_rate" and row["direction"] == "worse":
        return f"Cancellation rate rose in {country}. Validate product availability, delivery promises, and country-level demand mix."
    if row["direction"] == "better":
        return "Improvement signal. Validate whether it is operationally real, mix-driven, or affected by low sample size."
    return "Monitor signal. Validate sample size and compare with adjacent weeks before escalating."


def build_diagnostics(rows, latest_week, baseline_weeks):
    grouped = defaultdict(list)
    latest_by_segment = {}
    for row in rows:
        grouped[segment_key(row)].append(row)
        if row["week_start"] == latest_week:
            latest_by_segment[segment_key(row)] = row

    diagnostics = []
    for key, current_row in latest_by_segment.items():
        baseline_rows = [r for r in grouped[key] if r["week_start"] in baseline_weeks]
        if len(baseline_rows) < 2:
            continue
        for metric in METRICS:
            current = current_row[metric]
            baseline = mean(r[metric] for r in baseline_rows)
            if current is None or baseline is None:
                continue
            abs_change = current - baseline
            pct_change = abs_change / baseline if baseline else None
            diag = {
                "week_start": latest_week,
                "baseline_weeks": ", ".join(baseline_weeks),
                "country_name": current_row["country_name"],
                "country_code": current_row["country_code"],
                "contact_reason_name": current_row["contact_reason_name"],
                "contact_reason_id": current_row["contact_reason_id"],
                "metric": metric,
                "metric_label": METRIC_LABELS[metric],
                "current_value": current,
                "baseline_value": baseline,
                "abs_change": abs_change,
                "pct_change": pct_change,
                "direction": direction(metric, abs_change),
                "severity": severity(metric, abs_change, pct_change),
                "impact_score": score_change(metric, current, baseline, abs_change, pct_change),
                "csat_responses": current_row["csat_responses"],
                "contact_volume": current_row["contact_volume"],
            }
            diag_context = dict(current_row)
            diag_context.update(diag)
            diag["hypothesis"] = hypothesis_for(diag_context, {})
            diagnostics.append(diag)

    severity_rank = {"high": 0, "medium": 1, "monitor": 2}
    diagnostics.sort(
        key=lambda d: (
            d["direction"] != "worse",
            severity_rank.get(d["severity"], 3),
            -d["impact_score"],
        )
    )
    return diagnostics


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def series_for_metric(rows, metric):
    weeks = sorted({r["week_start"] for r in rows})
    return [aggregate_week(rows, week)[metric] for week in weeks], weeks


def svg_line_chart(rows, metric, width=760, height=280):
    values, weeks = series_for_metric(rows, metric)
    pairs = [(w, v) for w, v in zip(weeks, values) if v is not None]
    if not pairs:
        return ""
    weeks = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    margin = {"top": 24, "right": 24, "bottom": 46, "left": 64}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    min_v = min(values)
    max_v = max(values)
    if math.isclose(min_v, max_v):
        min_v -= 1
        max_v += 1

    def x(i):
        if len(values) == 1:
            return margin["left"] + plot_w / 2
        return margin["left"] + i * plot_w / (len(values) - 1)

    def y(v):
        return margin["top"] + (max_v - v) * plot_h / (max_v - min_v)

    points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
    y_ticks = [min_v + (max_v - min_v) * i / 4 for i in range(5)]
    tick_lines = []
    for tick in y_ticks:
        ty = y(tick)
        tick_lines.append(
            f'<line x1="{margin["left"]}" y1="{ty:.1f}" x2="{width - margin["right"]}" y2="{ty:.1f}" stroke="#e5e7eb" />'
        )
        tick_lines.append(
            f'<text x="{margin["left"] - 10}" y="{ty + 4:.1f}" text-anchor="end" font-size="11" fill="#475569">{escape(format_value(metric, tick))}</text>'
        )
    x_labels = []
    for i, week in enumerate(weeks):
        if i in {0, len(weeks) - 1} or i % 4 == 0:
            x_labels.append(
                f'<text x="{x(i):.1f}" y="{height - 16}" text-anchor="middle" font-size="11" fill="#475569">{escape(week[5:])}</text>'
            )
    circles = "\n".join(
        f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5" fill="#2563eb" />'
        for i, v in enumerate(values)
    )
    return f"""
<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(METRIC_LABELS[metric])} trend">
  <rect width="{width}" height="{height}" fill="#ffffff" />
  {''.join(tick_lines)}
  <polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
  {circles}
  <line x1="{margin["left"]}" y1="{height - margin["bottom"]}" x2="{width - margin["right"]}" y2="{height - margin["bottom"]}" stroke="#94a3b8" />
  {''.join(x_labels)}
</svg>"""


def svg_bar_chart(rows, width=760, height=320):
    items = rows[:8]
    if not items:
        return ""
    margin = {"top": 20, "right": 120, "bottom": 24, "left": 210}
    plot_w = width - margin["left"] - margin["right"]
    bar_h = 22
    gap = 10
    max_score = max(item["impact_score"] for item in items) or 1
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Top weekly KPI anomalies">']
    parts.append(f'<rect width="{width}" height="{height}" fill="#ffffff" />')
    for i, item in enumerate(items):
        y = margin["top"] + i * (bar_h + gap)
        bar_w = item["impact_score"] / max_score * plot_w
        label = f"{item['country_code']} | {item['contact_reason_name']} | {item['metric_label']}"
        color = "#dc2626" if item["direction"] == "worse" else "#2563eb"
        parts.append(
            f'<text x="{margin["left"] - 12}" y="{y + 16}" text-anchor="end" font-size="12" fill="#0f172a">{escape(label)}</text>'
        )
        parts.append(
            f'<rect x="{margin["left"]}" y="{y}" width="{bar_w:.1f}" height="{bar_h}" rx="3" fill="{color}" opacity="0.88" />'
        )
        parts.append(
            f'<text x="{margin["left"] + bar_w + 8:.1f}" y="{y + 16}" font-size="12" fill="#334155">{escape(format_change(item["metric"], item["abs_change"], item["pct_change"]))}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def build_summary(rows, diagnostics, latest_week, baseline_weeks):
    weekly = [aggregate_week(rows, week) for week in sorted({r["week_start"] for r in rows})]
    latest = aggregate_week(rows, latest_week)
    baseline = {
        metric: mean(aggregate_week(rows, week)[metric] for week in baseline_weeks)
        for metric in METRICS
    }
    headline_changes = []
    for metric in METRICS:
        current = latest[metric]
        base = baseline[metric]
        if current is None or base is None:
            continue
        abs_change = current - base
        pct_change = abs_change / base if base else None
        headline_changes.append(
            {
                "metric": metric,
                "metric_label": METRIC_LABELS[metric],
                "current_value": current,
                "baseline_value": base,
                "abs_change": abs_change,
                "pct_change": pct_change,
                "direction": direction(metric, abs_change),
                "formatted_current": format_value(metric, current),
                "formatted_baseline": format_value(metric, base),
                "formatted_change": format_change(metric, abs_change, pct_change),
            }
        )
    high_signals = [d for d in diagnostics if d["severity"] == "high"]
    summary = {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_mart": str(MART_PATH.relative_to(ROOT)),
        "latest_week": latest_week,
        "baseline_weeks": baseline_weeks,
        "weekly_series": weekly,
        "headline_changes": headline_changes,
        "top_signals": diagnostics[:10],
        "high_signal_count": len(high_signals),
        "method": "Latest complete week compared with the average of the previous four weeks at country and contact-reason grain.",
    }
    return summary


def write_report(summary):
    lines = [
        "# Weekly KPI Diagnostics Summary",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "## Diagnostic Frame",
        "",
        f"- Source mart: `{summary['source_mart']}`",
        f"- Latest week: `{summary['latest_week']}`",
        f"- Baseline: previous {len(summary['baseline_weeks'])} weeks ({', '.join(summary['baseline_weeks'])})",
        "- Grain: weekly country/contact-reason KPI mart.",
        "- Purpose: identify KPI movements that deserve analyst validation before AI-assisted WBR narration.",
        "",
        "## Executive Snapshot",
        "",
        "| Metric | Latest | Baseline | Change | Read |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for item in summary["headline_changes"]:
        lines.append(
            f"| {item['metric_label']} | {item['formatted_current']} | {item['formatted_baseline']} | {item['formatted_change']} | {item['direction']} |"
        )
    lines.extend(
        [
            "",
            "## Top Diagnostic Signals",
            "",
            "| Segment | Metric | Latest vs baseline | Severity | Analyst hypothesis |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for item in summary["top_signals"][:8]:
        segment = f"{item['country_name']} / {item['contact_reason_name']}"
        change = format_change(item["metric"], item["abs_change"], item["pct_change"])
        latest = format_value(item["metric"], item["current_value"])
        baseline = format_value(item["metric"], item["baseline_value"])
        lines.append(
            f"| {segment} | {item['metric_label']} | {latest} vs {baseline}; {change} | {item['severity']} | {item['hypothesis']} |"
        )
    lines.extend(
        [
            "",
            "## Quality And Interpretation Notes",
            "",
            "- This diagnostic uses synthetic data and should be treated as a portfolio workflow pattern, not a real business finding.",
            "- `cancellation_rate` and `total_orders` are country-week metrics repeated across contact-reason rows in the mart; the script deduplicates country-week orders for top-line summaries.",
            "- CSAT signals with low survey counts should be validated before being used in a leadership narrative.",
            "- Hypotheses are rule-based analyst prompts; they are not causal claims.",
        ]
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_dashboard(summary):
    trend_cards = [
        ("contact_volume", "Demand"),
        ("avg_aht_minutes", "Efficiency"),
        ("fcr_rate", "Resolution quality"),
        ("avg_csat", "Customer sentiment"),
    ]
    metric_cards = []
    for item in summary["headline_changes"]:
        cls = "good" if item["direction"] == "better" else "bad" if item["direction"] == "worse" else "neutral"
        metric_cards.append(
            f"""
            <section class="kpi {cls}">
              <span>{escape(item['metric_label'])}</span>
              <strong>{escape(item['formatted_current'])}</strong>
              <small>{escape(item['formatted_change'])} vs baseline</small>
            </section>"""
        )
    trend_sections = []
    for metric, role in trend_cards:
        trend_sections.append(
            f"""
            <section class="panel chart-panel">
              <div class="panel-heading">
                <span>{escape(role)}</span>
                <h2>{escape(METRIC_LABELS[metric])} trend</h2>
              </div>
              {svg_line_chart_from_summary(summary, metric)}
            </section>"""
        )
    signal_rows = []
    for item in summary["top_signals"][:12]:
        signal_rows.append(
            f"""
            <tr>
              <td>{escape(item['country_name'])}</td>
              <td>{escape(item['contact_reason_name'])}</td>
              <td>{escape(item['metric_label'])}</td>
              <td>{escape(format_value(item['metric'], item['current_value']))}</td>
              <td>{escape(format_value(item['metric'], item['baseline_value']))}</td>
              <td>{escape(format_change(item['metric'], item['abs_change'], item['pct_change']))}</td>
              <td><span class="pill {escape(item['severity'])}">{escape(item['severity'])}</span></td>
            </tr>"""
        )
    payload = json.dumps(
        {
            "latest_week": summary["latest_week"],
            "baseline_weeks": summary["baseline_weeks"],
            "top_signals": summary["top_signals"][:20],
        },
        default=str,
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Analytics Weekly Diagnostics Dashboard</title>
  <style>
    :root {{
      --ink: #0f172a;
      --muted: #475569;
      --line: #dbe3ef;
      --soft: #f8fafc;
      --blue: #2563eb;
      --gold: #b7791f;
      --pink: #be185d;
      --olive: #4d7c0f;
      --bad: #dc2626;
      --good: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #ffffff;
    }}
    header {{
      padding: 28px clamp(18px, 4vw, 56px) 18px;
      border-bottom: 1px solid var(--line);
    }}
    header p {{ max-width: 880px; color: var(--muted); line-height: 1.55; margin: 8px 0 0; }}
    h1 {{ margin: 0; font-size: clamp(26px, 4vw, 42px); letter-spacing: 0; }}
    main {{ padding: 24px clamp(18px, 4vw, 56px) 48px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; color: var(--muted); font-size: 14px; }}
    .meta span {{ border: 1px solid var(--line); border-radius: 6px; padding: 6px 9px; background: var(--soft); }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .kpi {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; min-height: 112px; }}
    .kpi span {{ color: var(--muted); font-size: 13px; }}
    .kpi strong {{ display: block; margin-top: 10px; font-size: 26px; letter-spacing: 0; }}
    .kpi small {{ display: block; margin-top: 8px; color: var(--muted); }}
    .kpi.bad strong {{ color: var(--bad); }}
    .kpi.good strong {{ color: var(--good); }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .panel {{ border: 1px solid var(--line); border-radius: 8px; padding: 16px; overflow: hidden; }}
    .panel.wide {{ grid-column: 1 / -1; }}
    .panel-heading {{ margin-bottom: 12px; }}
    .panel-heading span {{ color: var(--gold); font-weight: 700; font-size: 12px; text-transform: uppercase; }}
    .panel-heading h2 {{ margin: 3px 0 0; font-size: 18px; letter-spacing: 0; }}
    svg {{ width: 100%; height: auto; display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .pill {{ display: inline-flex; border-radius: 999px; padding: 3px 8px; font-size: 12px; border: 1px solid var(--line); }}
    .pill.high {{ color: #991b1b; border-color: #fecaca; background: #fff1f2; }}
    .pill.medium {{ color: #92400e; border-color: #fed7aa; background: #fff7ed; }}
    .pill.monitor {{ color: #334155; background: var(--soft); }}
    .note {{ color: var(--muted); line-height: 1.55; }}
    @media (max-width: 900px) {{
      .kpi-grid, .grid {{ grid-template-columns: 1fr; }}
      table {{ font-size: 13px; }}
      th:nth-child(5), td:nth-child(5) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Weekly CS KPI Diagnostics</h1>
    <p>Latest complete week compared with a four-week baseline. The dashboard highlights operational signals that an analyst should validate before turning them into an AI-assisted weekly business review.</p>
    <div class="meta">
      <span>Latest week: {escape(summary['latest_week'])}</span>
      <span>Baseline: {escape(', '.join(summary['baseline_weeks']))}</span>
      <span>Source: data/marts/mart_weekly_cs_kpi_by_country_reason.csv</span>
    </div>
  </header>
  <main>
    <section class="kpi-grid">
      {''.join(metric_cards)}
    </section>
    <section class="grid">
      {''.join(trend_sections)}
      <section class="panel wide">
        <div class="panel-heading">
          <span>Exception review</span>
          <h2>Top country and contact-reason signals</h2>
        </div>
        {svg_bar_chart(summary['top_signals'])}
      </section>
      <section class="panel wide">
        <div class="panel-heading">
          <span>Analyst queue</span>
          <h2>Signals to validate</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Country</th>
              <th>Reason</th>
              <th>Metric</th>
              <th>Latest</th>
              <th>Baseline</th>
              <th>Change</th>
              <th>Severity</th>
            </tr>
          </thead>
          <tbody>{''.join(signal_rows)}</tbody>
        </table>
      </section>
      <section class="panel wide note">
        <strong>Method note.</strong> Signals are generated with deterministic rules from synthetic data. They are designed to support analyst validation, not to claim causality. CSAT movements with low response counts and country-week order metrics repeated across reason rows require extra care.
      </section>
    </section>
  </main>
  <script type="application/json" id="dashboard-data">{escape(payload)}</script>
</body>
</html>
"""
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")


def svg_line_chart_from_summary(summary, metric):
    rows = []
    for item in summary["weekly_series"]:
        rows.append(
            {
                "week_start": item["week_start"],
                "country_code": "ALL",
                "country_name": "All",
                "contact_reason_id": "all",
                "contact_reason_name": "All",
                **{m: item.get(m) for m in METRICS},
                "csat_responses": item.get("csat_responses", 0),
                "total_orders": item.get("total_orders", 0),
                "cancelled_orders": item.get("cancelled_orders", 0),
            }
        )
    return svg_line_chart(rows, metric)


def main():
    rows = read_mart()
    weeks = sorted({r["week_start"] for r in rows})
    if len(weeks) <= BASELINE_WEEKS:
        raise SystemExit("Not enough weekly history to run diagnostics.")

    latest_week = weeks[-1]
    baseline_weeks = weeks[-(BASELINE_WEEKS + 1) : -1]
    diagnostics = build_diagnostics(rows, latest_week, baseline_weeks)
    country_summary = aggregate_country(rows, latest_week)
    country_summary.sort(key=lambda r: r["contact_volume"], reverse=True)
    summary = build_summary(rows, diagnostics, latest_week, baseline_weeks)

    write_csv(
        DIAGNOSTICS_PATH,
        diagnostics,
        [
            "week_start",
            "baseline_weeks",
            "country_name",
            "country_code",
            "contact_reason_name",
            "contact_reason_id",
            "metric",
            "metric_label",
            "current_value",
            "baseline_value",
            "abs_change",
            "pct_change",
            "direction",
            "severity",
            "impact_score",
            "csat_responses",
            "contact_volume",
            "hypothesis",
        ],
    )
    write_csv(
        COUNTRY_SUMMARY_PATH,
        country_summary,
        [
            "country_name",
            "country_code",
            "contact_volume",
            "avg_aht_minutes",
            "fcr_rate",
            "avg_csat",
            "backlog_end_of_week",
            "compensation_cost",
            "total_orders",
            "cancelled_orders",
            "cancellation_rate",
            "contact_rate",
        ],
    )
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(summary)
    write_dashboard(summary)

    print(f"Wrote {DIAGNOSTICS_PATH}")
    print(f"Wrote {COUNTRY_SUMMARY_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {DASHBOARD_PATH}")


if __name__ == "__main__":
    main()
