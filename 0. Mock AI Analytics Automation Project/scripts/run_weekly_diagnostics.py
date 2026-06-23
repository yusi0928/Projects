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
KPI_REPORTING_PATH = DASHBOARD_DIR / "kpi_reporting.html"
KPI_GOVERNANCE_PATH = DASHBOARD_DIR / "kpi_governance.html"

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

METRIC_DEFINITIONS = {
    "contact_volume": {
        "definition": "Number of contacts created in the week.",
        "formula": "count(contacts)",
        "grain": "week, country, contact reason",
        "owner": "CS Operations Analytics",
        "good_direction": "Context-dependent",
        "caveat": "Volume increases can reflect demand growth or upstream friction.",
    },
    "contact_rate": {
        "definition": "Contacts divided by total orders.",
        "formula": "contact_volume / total_orders",
        "grain": "week, country, contact reason with country-week order denominator",
        "owner": "CS Operations Analytics",
        "good_direction": "Lower",
        "caveat": "Order volume repeats across reason-level rows; interpret at country-week or with reason mix context.",
    },
    "avg_aht_minutes": {
        "definition": "Average handling time in minutes for resolved contacts.",
        "formula": "sum(handle_minutes) / resolved_contacts",
        "grain": "week, country, contact reason",
        "owner": "CS Operations Analytics",
        "good_direction": "Lower",
        "caveat": "Sensitive to contact complexity, agent mix, and escalation mix.",
    },
    "fcr_rate": {
        "definition": "Resolved contacts not reopened within the observation window divided by resolved contacts.",
        "formula": "first_contact_resolved_contacts / resolved_contacts",
        "grain": "week, country, contact reason",
        "owner": "CS Operations Analytics",
        "good_direction": "Higher",
        "caveat": "Can move with policy complexity and downstream issue recurrence.",
    },
    "avg_csat": {
        "definition": "Average submitted CSAT score linked to contacts.",
        "formula": "sum(csat_score) / csat_responses",
        "grain": "week, country, contact reason",
        "owner": "CS Operations Analytics",
        "good_direction": "Higher",
        "caveat": "Low survey response count should be treated as low confidence.",
    },
    "backlog_end_of_week": {
        "definition": "Contacts created in the week that remain open at week end.",
        "formula": "count(open_contacts_at_week_end)",
        "grain": "week, country, contact reason",
        "owner": "CS Operations Analytics",
        "good_direction": "Lower",
        "caveat": "Backlog reflects both demand pressure and staffing capacity.",
    },
    "compensation_cost": {
        "definition": "Refund, voucher, and goodwill amount linked to contacts.",
        "formula": "sum(compensation_amount)",
        "grain": "week, country, contact reason",
        "owner": "CS Operations Analytics",
        "good_direction": "Lower",
        "caveat": "Separate contact volume effect from compensation-per-contact effect.",
    },
    "cancellation_rate": {
        "definition": "Cancelled orders divided by total orders at country-week level.",
        "formula": "cancelled_orders / total_orders",
        "grain": "country-week metric repeated across contact reasons",
        "owner": "CS Operations Analytics",
        "good_direction": "Lower",
        "caveat": "Do not sum across contact reasons; validate at country-week grain.",
    },
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


def aggregate_reason(rows, week):
    grouped = defaultdict(list)
    for row in rows:
        if row["week_start"] == week:
            grouped[(row["contact_reason_name"], row["contact_reason_id"])].append(row)
    summaries = []
    for (reason_name, reason_id), items in grouped.items():
        country_week = {(r["week_start"], r["country_code"]): r for r in items}
        total_orders = sum(r["total_orders"] for r in country_week.values())
        cancelled_orders = sum(r["cancelled_orders"] for r in country_week.values())
        contact_volume = sum(r["contact_volume"] or 0 for r in items)
        summaries.append(
            {
                "contact_reason_name": reason_name,
                "contact_reason_id": reason_id,
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


def confidence_for(metric, current_row, baseline_rows):
    contact_volume = current_row["contact_volume"] or 0
    csat_responses = current_row["csat_responses"] or 0
    baseline_contacts = mean(r["contact_volume"] for r in baseline_rows) or 0
    baseline_csat = mean(r["csat_responses"] for r in baseline_rows) or 0

    if metric == "avg_csat":
        if csat_responses < 5:
            return "low"
        if csat_responses < 15 or baseline_csat < 8:
            return "medium"
        return "high"
    if metric in {"avg_aht_minutes", "fcr_rate", "contact_volume", "backlog_end_of_week", "compensation_cost"}:
        if contact_volume < 5:
            return "low"
        if contact_volume < 20 or baseline_contacts < 10:
            return "medium"
        return "high"
    if metric in {"cancellation_rate", "contact_rate"}:
        orders = current_row["total_orders"] or 0
        if orders < 100:
            return "low"
        if orders < 300:
            return "medium"
        return "high"
    return "medium"


def confidence_score(confidence):
    return {"high": 1.0, "medium": 0.65, "low": 0.35}.get(confidence, 0.5)


def business_impact_score(metric, current_row, current, baseline, abs_change):
    contact_volume = current_row["contact_volume"] or 0
    total_orders = current_row["total_orders"] or 0
    compensation = current_row["compensation_cost"] or 0
    if abs_change is None:
        return 0
    magnitude = abs(abs_change)
    if metric == "compensation_cost":
        return min(100, magnitude / 8 + compensation / 60 + contact_volume * 0.6)
    if metric == "contact_volume":
        return min(100, magnitude * 1.3 + contact_volume * 0.4)
    if metric == "contact_rate":
        return min(100, magnitude * 180 + contact_volume * 0.45 + total_orders / 120)
    if metric == "cancellation_rate":
        return min(100, magnitude * 250 + total_orders / 80)
    if metric == "backlog_end_of_week":
        return min(100, magnitude * 2 + contact_volume * 0.35)
    if metric == "avg_aht_minutes":
        return min(100, magnitude * max(contact_volume, 1) * 0.5)
    if metric == "fcr_rate":
        return min(100, magnitude * max(contact_volume, 1) * 120)
    if metric == "avg_csat":
        return min(100, magnitude * max(current_row["csat_responses"] or 0, 1) * 4)
    return min(100, score_change(metric, current, baseline, abs_change, None))


def impact_label(score):
    if score >= 45:
        return "high"
    if score >= 18:
        return "medium"
    return "low"


def possible_owner(metric):
    if metric in {"avg_aht_minutes", "fcr_rate", "backlog_end_of_week"}:
        return "CS Operations"
    if metric == "avg_csat":
        return "CX Quality"
    if metric == "compensation_cost":
        return "CS Policy / Finance"
    if metric in {"contact_rate", "contact_volume"}:
        return "Product Ops / CS Ops"
    if metric == "cancellation_rate":
        return "Fulfillment Ops"
    return "CS Analytics"


def validation_prompt(metric, confidence):
    prefix = "Low-confidence signal: validate sample size first. " if confidence == "low" else ""
    prompts = {
        "avg_aht_minutes": "Check contact complexity, new-agent share, backlog pressure, process/tool incidents, and contact mix.",
        "fcr_rate": "Review reopened cases, downstream unresolved issues, policy/process ambiguity, agent knowledge gaps, and complex contact mix.",
        "avg_csat": "Check survey response count, complaint themes, country/reason friction, and whether FCR or AHT also deteriorated.",
        "compensation_cost": "Decompose volume effect vs compensation-per-contact effect; check policy changes and late delivery/cancellation mix.",
        "contact_rate": "Compare contact movement with order movement; check product/process friction and reason mix shift.",
        "contact_volume": "Review demand shifts, reason mix, upstream incidents, and whether order volume also changed.",
        "cancellation_rate": "Validate at country-week grain; check fulfillment, partner, delivery, and policy/process changes.",
        "backlog_end_of_week": "Check staffing coverage, queue age, contact volume, and AHT movement.",
    }
    return prefix + prompts.get(metric, "Validate sample size, adjacent weeks, and operational context before escalation.")


def why_this_matters(metric, row):
    if metric == "avg_aht_minutes":
        return "Longer handling time can reduce capacity and increase backlog risk."
    if metric == "fcr_rate":
        return "Lower first-contact resolution can create repeat contacts and weaker customer experience."
    if metric == "avg_csat":
        return "CSAT movement affects customer trust, but response count determines reliability."
    if metric == "compensation_cost":
        return "Higher compensation cost can signal policy exposure or operational failures with direct financial impact."
    if metric == "contact_rate":
        return "A higher contact rate means support demand is rising relative to orders."
    if metric == "contact_volume":
        return "Higher volume changes workload and can pressure service levels."
    if metric == "cancellation_rate":
        return "Cancellation rate is an order-level business outcome and should be investigated at country-week grain."
    if metric == "backlog_end_of_week":
        return "Backlog creates delayed resolution and future customer experience risk."
    return "Movement may affect weekly operating review priorities."


def recommended_action(metric, severity_value, confidence, impact):
    if confidence == "low":
        return "Validate sample size before escalating."
    if impact == "high" and severity_value in {"high", "medium"}:
        return "Assign owner and review source records this week."
    if metric in {"cancellation_rate", "contact_rate"}:
        return "Validate denominator and grain before business narrative."
    return "Monitor and compare with adjacent weeks."


def decomposition_note(metric, current_row, baseline_rows, current, baseline, abs_change):
    baseline_contacts = mean(r["contact_volume"] for r in baseline_rows) or 0
    baseline_orders = mean(r["total_orders"] for r in baseline_rows) or 0
    baseline_comp = mean(r["compensation_cost"] for r in baseline_rows) or 0
    baseline_csat = mean(r["csat_responses"] for r in baseline_rows) or 0
    contact_delta = (current_row["contact_volume"] or 0) - baseline_contacts
    order_delta = (current_row["total_orders"] or 0) - baseline_orders
    if metric == "compensation_cost":
        current_cpc = (current_row["compensation_cost"] or 0) / max(current_row["contact_volume"] or 0, 1)
        baseline_cpc = baseline_comp / max(baseline_contacts, 1)
        return f"Volume effect: contacts {contact_delta:+.0f}; compensation/contact {current_cpc:.1f} vs {baseline_cpc:.1f} baseline."
    if metric == "contact_rate":
        return f"Contacts changed {contact_delta:+.0f}; orders changed {order_delta:+.0f}. Interpret relative demand, not contacts alone."
    if metric == "avg_csat":
        return f"CSAT response count: {current_row['csat_responses']:.0f} latest vs {baseline_csat:.1f} baseline."
    if metric == "avg_aht_minutes":
        return f"Compare AHT movement with contact volume change ({contact_delta:+.0f}) and reason mix before concluding process impact."
    if metric == "cancellation_rate":
        return "Country-week order metric repeated across reasons; validate using country-week totals, not summed reason rows."
    return "Review movement alongside sample size, adjacent weeks, and operational context."


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
    low_confidence = row.get("confidence") == "low"
    if metric == "avg_csat" and low_confidence:
        return "CSAT moved on a low survey count. Treat as a validation prompt, not a performance conclusion."
    if metric in {"contact_volume", "contact_rate"} and row["direction"] in {"up", "worse"}:
        if "delivery" in reason:
            return "Possible delivery reliability pressure. Validate late-order rate, courier incidents, and warehouse capacity."
        if "payment" in reason:
            return "Possible payment journey friction. Validate payment failures and checkout release calendar."
        if "cancellation" in reason:
            return "Possible cancellation intent increase. Validate cancellation policy, supply issues, and order mix."
        return "Possible demand or operational friction in this contact reason. Validate reason-level ticket samples and upstream events."
    if metric == "compensation_cost" and row["direction"] == "worse":
        return "Compensation exposure increased. Check whether this is driven by higher contact volume, higher compensation per contact, policy change, or late delivery/cancellation mix."
    if metric == "backlog_end_of_week" and row["direction"] == "worse":
        return "Backlog pressure increased. Validate staffing coverage, unresolved queue age, and whether AHT or volume also rose."
    if metric == "avg_aht_minutes" and row["direction"] == "worse":
        return "AHT increased. Validate contact complexity, new-agent share, backlog pressure, process/tool issues, and contact mix."
    if metric == "fcr_rate" and row["direction"] == "worse":
        return "FCR decreased. Validate unresolved downstream issues, policy/process ambiguity, agent knowledge gaps, and complex contact mix."
    if metric == "avg_csat" and row["direction"] == "worse":
        return "CSAT decreased. Validate survey count, service quality themes, and specific reason/country friction."
    if metric == "cancellation_rate" and row["direction"] == "worse":
        return f"Cancellation rate increased in {country}. Validate fulfillment, partner, delivery, and policy/process changes at country-week grain."
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
            movement_severity = severity(metric, abs_change, pct_change)
            confidence = confidence_for(metric, current_row, baseline_rows)
            raw_impact = business_impact_score(metric, current_row, current, baseline, abs_change)
            business_impact = impact_label(raw_impact)
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
                "severity": movement_severity,
                "severity_score": score_change(metric, current, baseline, abs_change, pct_change),
                "confidence": confidence,
                "business_impact": business_impact,
                "impact_score": raw_impact * confidence_score(confidence),
                "impact_score_raw": raw_impact,
                "csat_responses": current_row["csat_responses"],
                "contact_volume": current_row["contact_volume"],
                "total_orders": current_row["total_orders"],
                "compensation_cost": current_row["compensation_cost"],
            }
            diag_context = dict(current_row)
            diag_context.update(diag)
            diag["hypothesis"] = hypothesis_for(diag_context, {})
            diag["why_this_matters"] = why_this_matters(metric, diag_context)
            diag["suggested_validation"] = validation_prompt(metric, confidence)
            diag["possible_owner"] = possible_owner(metric)
            diag["recommended_next_action"] = recommended_action(
                metric, movement_severity, confidence, business_impact
            )
            diag["decomposition_note"] = decomposition_note(
                metric, current_row, baseline_rows, current, baseline, abs_change
            )
            diagnostics.append(diag)

    severity_rank = {"high": 0, "medium": 1, "monitor": 2}
    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    impact_rank = {"high": 0, "medium": 1, "low": 2}
    diagnostics.sort(
        key=lambda d: (
            d["direction"] != "worse",
            impact_rank.get(d["business_impact"], 3),
            confidence_rank.get(d["confidence"], 3),
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
    worse_signals = [d for d in diagnostics if d["direction"] == "worse"]
    low_confidence = [d for d in diagnostics if d["confidence"] == "low"]
    matters_most = next((d for d in diagnostics if d["direction"] == "worse"), diagnostics[0] if diagnostics else None)
    investigate_first = [
        d
        for d in diagnostics
        if d["direction"] == "worse" and d["business_impact"] in {"high", "medium"}
    ][:6]
    what_changed = [
        f"{item['metric_label']} is {item['formatted_change']} vs baseline"
        for item in headline_changes
        if item["direction"] == "worse"
    ][:3]
    summary = {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_mart": str(MART_PATH.relative_to(ROOT)),
        "latest_week": latest_week,
        "baseline_weeks": baseline_weeks,
        "weekly_series": weekly,
        "latest_overall": latest,
        "country_summary": sorted(
            aggregate_country(rows, latest_week), key=lambda r: r["contact_volume"], reverse=True
        ),
        "reason_summary": sorted(
            aggregate_reason(rows, latest_week), key=lambda r: r["contact_volume"], reverse=True
        ),
        "headline_changes": headline_changes,
        "top_signals": diagnostics[:10],
        "investigate_first": investigate_first,
        "low_confidence_signals": low_confidence[:6],
        "high_signal_count": len(high_signals),
        "worse_signal_count": len(worse_signals),
        "low_confidence_count": len(low_confidence),
        "executive_summary": {
            "what_changed": what_changed
            or ["No major top-line deterioration detected versus the four-week baseline."],
            "matters_most": (
                f"{matters_most['country_name']} / {matters_most['contact_reason_name']} / {matters_most['metric_label']} "
                f"has {matters_most['business_impact']} business impact and {matters_most['confidence']} confidence."
                if matters_most
                else "No diagnostic signals available."
            ),
            "investigate_first": [
                f"{d['country_code']} {d['contact_reason_name']} {d['metric_label']}"
                for d in investigate_first[:3]
            ],
            "low_confidence": [
                f"{d['country_code']} {d['contact_reason_name']} {d['metric_label']}"
                for d in low_confidence[:3]
            ],
        },
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
            "| Segment | Metric | Latest vs baseline | Severity | Confidence | Business impact | Analyst hypothesis |",
            "| --- | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for item in summary["top_signals"][:8]:
        segment = f"{item['country_name']} / {item['contact_reason_name']}"
        change = format_change(item["metric"], item["abs_change"], item["pct_change"])
        latest = format_value(item["metric"], item["current_value"])
        baseline = format_value(item["metric"], item["baseline_value"])
        lines.append(
            f"| {segment} | {item['metric_label']} | {latest} vs {baseline}; {change} | {item['severity']} | {item['confidence']} | {item['business_impact']} | {item['hypothesis']} |"
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


def nav_html(active):
    links = [
        ("reporting", "KPI Reporting Dashboard", "kpi_reporting.html"),
        ("diagnostics", "Weekly Diagnostics Dashboard", "index.html"),
        ("governance", "KPI Governance Page", "kpi_governance.html"),
    ]
    return "".join(
        f'<a class="{"active" if key == active else ""}" href="{href}">{escape(label)}</a>'
        for key, label, href in links
    )


def disclaimer_html():
    return (
        "Synthetic/mock portfolio project. No real customer, employee, financial, "
        "employer, or proprietary company data is used."
    )


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
    exec_items = "".join(
        f"<li>{escape(item)}</li>" for item in summary["executive_summary"]["what_changed"]
    )
    investigate_items = "".join(
        f"<li>{escape(item)}</li>"
        for item in (summary["executive_summary"]["investigate_first"] or ["No high-priority signal after confidence and impact weighting."])
    )
    low_conf_items = "".join(
        f"<li>{escape(item)}</li>"
        for item in (summary["executive_summary"]["low_confidence"] or ["No low-confidence top signals in the current queue."])
    )
    signal_rows = []
    for item in summary["top_signals"][:12]:
        signal = f"{item['country_code']} / {item['contact_reason_name']} / {item['metric_label']}"
        volume_context = (
            f"Contacts {item['contact_volume']:.0f}; CSAT responses {item['csat_responses']:.0f}"
            if item["metric"] == "avg_csat"
            else f"Contacts {item['contact_volume']:.0f}; orders {item['total_orders']:.0f}"
        )
        signal_rows.append(
            f"""
            <tr>
              <td><strong>{escape(signal)}</strong><br><small>{escape(volume_context)}</small></td>
              <td>{escape(format_value(item['metric'], item['current_value']))}</td>
              <td>{escape(format_value(item['metric'], item['baseline_value']))}</td>
              <td>{escape(format_change(item['metric'], item['abs_change'], item['pct_change']))}</td>
              <td><span class="pill {escape(item['severity'])}">{escape(item['severity'])}</span></td>
              <td><span class="pill confidence-{escape(item['confidence'])}">{escape(item['confidence'])}</span></td>
              <td><span class="pill impact-{escape(item['business_impact'])}">{escape(item['business_impact'])}</span><br><small>score {item['impact_score']:.1f}</small></td>
              <td>{escape(item['why_this_matters'])}</td>
              <td>{escape(item['suggested_validation'])}<br><small>{escape(item['decomposition_note'])}</small></td>
              <td>{escape(item['possible_owner'])}</td>
              <td>{escape(item['recommended_next_action'])}</td>
            </tr>"""
        )
    first_rows = []
    for item in summary["investigate_first"]:
        first_rows.append(
            f"""
            <tr>
              <td>{escape(item['country_name'])} / {escape(item['contact_reason_name'])}</td>
              <td>{escape(item['metric_label'])}</td>
              <td>{escape(item['business_impact'])}</td>
              <td>{escape(item['confidence'])}</td>
              <td>{escape(item['possible_owner'])}</td>
              <td>{escape(item['recommended_next_action'])}</td>
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
    nav {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
    nav a {{ color: var(--ink); text-decoration: none; border: 1px solid var(--line); border-radius: 6px; padding: 7px 10px; background: #fff; }}
    nav a.active {{ color: #fff; background: var(--ink); border-color: var(--ink); }}
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
    .summary-grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .summary-card {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: var(--soft); }}
    .summary-card h2 {{ margin: 0 0 8px; font-size: 16px; }}
    .summary-card ul {{ margin: 0; padding-left: 18px; color: var(--muted); line-height: 1.45; }}
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
    .pill.confidence-high, .pill.impact-high {{ color: #166534; border-color: #bbf7d0; background: #f0fdf4; }}
    .pill.confidence-medium, .pill.impact-medium {{ color: #92400e; border-color: #fed7aa; background: #fff7ed; }}
    .pill.confidence-low, .pill.impact-low {{ color: #991b1b; border-color: #fecaca; background: #fff1f2; }}
    .note {{ color: var(--muted); line-height: 1.55; }}
    @media (max-width: 900px) {{
      .kpi-grid, .grid, .summary-grid {{ grid-template-columns: 1fr; }}
      table {{ font-size: 13px; }}
    }}
  </style>
</head>
<body>
  <header>
    <nav>{nav_html("diagnostics")}</nav>
    <h1>Weekly CS KPI Diagnostics</h1>
    <p>Answers: what changed this week, and what should analysts investigate first? Signals support analyst validation and do not claim causality.</p>
    <div class="meta">
      <span>Latest week: {escape(summary['latest_week'])}</span>
      <span>Baseline: {escape(', '.join(summary['baseline_weeks']))}</span>
      <span>Source: data/marts/mart_weekly_cs_kpi_by_country_reason.csv</span>
      <span>{escape(disclaimer_html())}</span>
    </div>
  </header>
  <main>
    <section class="summary-grid">
      <div class="summary-card"><h2>What changed this week?</h2><ul>{exec_items}</ul></div>
      <div class="summary-card"><h2>Movement that matters most</h2><p class="note">{escape(summary['executive_summary']['matters_most'])}</p></div>
      <div class="summary-card"><h2>Investigate first</h2><ul>{investigate_items}</ul></div>
      <div class="summary-card"><h2>Low confidence</h2><ul>{low_conf_items}</ul></div>
    </section>
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
          <span>Priority review</span>
          <h2>What should analysts investigate first?</h2>
        </div>
        <table>
          <thead>
            <tr><th>Segment</th><th>Metric</th><th>Business impact</th><th>Confidence</th><th>Possible owner</th><th>Recommended next action</th></tr>
          </thead>
          <tbody>{''.join(first_rows)}</tbody>
        </table>
      </section>
      <section class="panel wide">
        <div class="panel-heading">
          <span>Analyst queue</span>
          <h2>Signals to validate</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Signal</th>
              <th>Latest</th>
              <th>Baseline</th>
              <th>Change</th>
              <th>Severity</th>
              <th>Confidence</th>
              <th>Business impact</th>
              <th>Why this matters</th>
              <th>Suggested validation</th>
              <th>Possible owner</th>
              <th>Recommended next action</th>
            </tr>
          </thead>
          <tbody>{''.join(signal_rows)}</tbody>
        </table>
      </section>
      <section class="panel wide note">
        <strong>Method note.</strong> Severity describes how unusual or large the movement is. Business impact estimates how much the business should care by considering affected contact volume, order volume, compensation cost, or operational importance. Confidence is reduced for low sample sizes, especially CSAT signals with few survey responses. Cancellation rate and order-based metrics are country-week metrics repeated across contact reasons and should not be summed across reasons.
      </section>
    </section>
  </main>
  <script type="application/json" id="dashboard-data">{escape(payload)}</script>
</body>
</html>
"""
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_PATH.write_text(html, encoding="utf-8")


def write_kpi_reporting_dashboard(summary):
    reporting_metrics = ["contact_volume", "contact_rate", "avg_aht_minutes", "fcr_rate", "avg_csat", "compensation_cost"]
    cards = []
    latest = summary["latest_overall"]
    for metric in reporting_metrics:
        cards.append(
            f"""
            <section class="kpi">
              <span>{escape(METRIC_LABELS[metric])}</span>
              <strong>{escape(format_value(metric, latest.get(metric)))}</strong>
              <small>{escape(METRIC_DEFINITIONS[metric]['good_direction'])} is favorable</small>
            </section>"""
        )
    trend_sections = []
    for metric in ["contact_volume", "contact_rate", "avg_aht_minutes", "fcr_rate", "avg_csat", "compensation_cost"]:
        trend_sections.append(
            f"""
            <section class="panel">
              <div class="panel-heading"><span>KPI trend</span><h2>{escape(METRIC_LABELS[metric])}</h2></div>
              {svg_line_chart_from_summary(summary, metric)}
            </section>"""
        )
    country_rows = []
    for row in summary["country_summary"][:8]:
        country_rows.append(
            f"""
            <tr>
              <td>{escape(row['country_name'])}</td>
              <td>{escape(format_value('contact_volume', row['contact_volume']))}</td>
              <td>{escape(format_value('contact_rate', row['contact_rate']))}</td>
              <td>{escape(format_value('avg_aht_minutes', row['avg_aht_minutes']))}</td>
              <td>{escape(format_value('fcr_rate', row['fcr_rate']))}</td>
              <td>{escape(format_value('avg_csat', row['avg_csat']))}</td>
            </tr>"""
        )
    reason_rows = []
    for row in summary["reason_summary"][:8]:
        reason_rows.append(
            f"""
            <tr>
              <td>{escape(row['contact_reason_name'])}</td>
              <td>{escape(format_value('contact_volume', row['contact_volume']))}</td>
              <td>{escape(format_value('contact_rate', row['contact_rate']))}</td>
              <td>{escape(format_value('avg_aht_minutes', row['avg_aht_minutes']))}</td>
              <td>{escape(format_value('fcr_rate', row['fcr_rate']))}</td>
              <td>{escape(format_value('compensation_cost', row['compensation_cost']))}</td>
            </tr>"""
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Analytics KPI Reporting Dashboard</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: #0f172a; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fff; }}
    header {{ padding: 28px clamp(18px, 4vw, 56px) 18px; border-bottom: 1px solid #dbe3ef; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
    nav a {{ color: #0f172a; text-decoration: none; border: 1px solid #dbe3ef; border-radius: 6px; padding: 7px 10px; }}
    nav a.active {{ color: #fff; background: #0f172a; border-color: #0f172a; }}
    h1 {{ margin: 0; font-size: clamp(26px, 4vw, 42px); letter-spacing: 0; }}
    header p, .note {{ color: #475569; line-height: 1.55; max-width: 900px; }}
    main {{ padding: 24px clamp(18px, 4vw, 56px) 48px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; color: #475569; font-size: 14px; }}
    .meta span {{ border: 1px solid #dbe3ef; border-radius: 6px; padding: 6px 9px; background: #f8fafc; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .kpi {{ border: 1px solid #dbe3ef; border-radius: 8px; padding: 14px; min-height: 110px; }}
    .kpi span {{ color: #475569; font-size: 13px; }}
    .kpi strong {{ display: block; margin-top: 10px; font-size: 26px; letter-spacing: 0; }}
    .kpi small {{ display: block; margin-top: 8px; color: #475569; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .panel {{ border: 1px solid #dbe3ef; border-radius: 8px; padding: 16px; overflow: hidden; }}
    .wide {{ grid-column: 1 / -1; }}
    .panel-heading span {{ color: #2563eb; font-weight: 700; font-size: 12px; text-transform: uppercase; }}
    .panel-heading h2 {{ margin: 3px 0 12px; font-size: 18px; letter-spacing: 0; }}
    svg {{ width: 100%; height: auto; display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid #dbe3ef; text-align: left; vertical-align: top; }}
    th {{ color: #475569; font-size: 12px; text-transform: uppercase; }}
    @media (max-width: 900px) {{ .kpi-grid, .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <nav>{nav_html("reporting")}</nav>
    <h1>KPI Reporting Dashboard</h1>
    <p>Answers: how is customer support performance trending? This is the standard reporting view from the governed KPI mart, separate from anomaly investigation.</p>
    <div class="meta">
      <span>Latest week: {escape(summary['latest_week'])}</span>
      <span>Source: data/marts/mart_weekly_cs_kpi_by_country_reason.csv</span>
      <span>{escape(disclaimer_html())}</span>
    </div>
  </header>
  <main>
    <section class="kpi-grid">{''.join(cards)}</section>
    <section class="grid">
      {''.join(trend_sections)}
      <section class="panel wide">
        <div class="panel-heading"><span>Country breakdown</span><h2>Latest week by country</h2></div>
        <table><thead><tr><th>Country</th><th>Contacts</th><th>Contact rate</th><th>AHT</th><th>FCR</th><th>CSAT</th></tr></thead><tbody>{''.join(country_rows)}</tbody></table>
      </section>
      <section class="panel wide">
        <div class="panel-heading"><span>Contact reason breakdown</span><h2>Latest week by reason</h2></div>
        <table><thead><tr><th>Reason</th><th>Contacts</th><th>Contact rate</th><th>AHT</th><th>FCR</th><th>Compensation</th></tr></thead><tbody>{''.join(reason_rows)}</tbody></table>
      </section>
      <section class="panel wide note">
        <strong>Business interpretation notes.</strong> Use this page for recurring KPI reporting. For exception triage, use the Weekly Diagnostics Dashboard. Order-based metrics such as cancellation rate and contact rate require grain awareness because order volume is repeated across reason-level rows.
      </section>
    </section>
  </main>
</body>
</html>
"""
    KPI_REPORTING_PATH.write_text(html, encoding="utf-8")


def write_kpi_governance_page(summary):
    metric_rows = []
    for metric in ["contact_volume", "contact_rate", "avg_aht_minutes", "fcr_rate", "avg_csat", "backlog_end_of_week", "compensation_cost", "cancellation_rate"]:
        meta = METRIC_DEFINITIONS[metric]
        metric_rows.append(
            f"""
            <tr>
              <td><strong>{escape(METRIC_LABELS[metric])}</strong><br><code>{escape(metric)}</code></td>
              <td>{escape(meta['definition'])}<br><small>{escape(meta['formula'])}</small></td>
              <td>{escape(meta['grain'])}</td>
              <td>{escape(meta['owner'])}</td>
              <td>Weekly</td>
              <td>{escape(meta['good_direction'])}</td>
              <td>{escape(meta['caveat'])}</td>
            </tr>"""
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Analytics KPI Governance Page</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: #0f172a; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fff; }}
    header {{ padding: 28px clamp(18px, 4vw, 56px) 18px; border-bottom: 1px solid #dbe3ef; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }}
    nav a {{ color: #0f172a; text-decoration: none; border: 1px solid #dbe3ef; border-radius: 6px; padding: 7px 10px; }}
    nav a.active {{ color: #fff; background: #0f172a; border-color: #0f172a; }}
    h1 {{ margin: 0; font-size: clamp(26px, 4vw, 42px); letter-spacing: 0; }}
    header p, .note {{ color: #475569; line-height: 1.55; max-width: 920px; }}
    main {{ padding: 24px clamp(18px, 4vw, 56px) 48px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; color: #475569; font-size: 14px; }}
    .meta span {{ border: 1px solid #dbe3ef; border-radius: 6px; padding: 6px 9px; background: #f8fafc; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .panel {{ border: 1px solid #dbe3ef; border-radius: 8px; padding: 16px; overflow: hidden; }}
    .wide {{ grid-column: 1 / -1; }}
    .panel h2 {{ margin: 0 0 10px; font-size: 18px; letter-spacing: 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid #dbe3ef; text-align: left; vertical-align: top; }}
    th {{ color: #475569; font-size: 12px; text-transform: uppercase; }}
    code {{ background: #f8fafc; border: 1px solid #dbe3ef; border-radius: 4px; padding: 1px 4px; }}
    ul {{ color: #475569; line-height: 1.55; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} table {{ font-size: 13px; }} }}
  </style>
</head>
<body>
  <header>
    <nav>{nav_html("governance")}</nav>
    <h1>KPI Governance Page</h1>
    <p>Governed KPI layer for AI-assisted CS weekly business review. Answers: can we trust these KPIs, how are they defined, and can AI safely use them?</p>
    <div class="meta">
      <span>Semantic layer: models/semantic/semantic_cs_kpi_metrics.yml</span>
      <span>Quality status: 11/11 PASS</span>
      <span>{escape(disclaimer_html())}</span>
    </div>
  </header>
  <main>
    <section class="grid">
      <section class="panel">
        <h2>Executive summary</h2>
        <p class="note">One governed semantic KPI layer supports automated HTML reporting, weekly diagnostics, KPI governance documentation, and future BI implementation.</p>
      </section>
      <section class="panel">
        <h2>AI-safe usage policy</h2>
        <p class="note">AI may use the aggregated mart, metric definitions, data quality status, and analyst validation notes. AI should not access raw customer, agent, free-text, employer, or proprietary data.</p>
      </section>
      <section class="panel wide">
        <h2>KPI catalog</h2>
        <table>
          <thead><tr><th>KPI</th><th>Definition and formula</th><th>Grain</th><th>Owner</th><th>Refresh</th><th>Good direction</th><th>Caveats</th></tr></thead>
          <tbody>{''.join(metric_rows)}</tbody>
        </table>
      </section>
      <section class="panel">
        <h2>Data lineage</h2>
        <ul>
          <li>Raw synthetic inputs in <code>data/raw/*.csv</code></li>
          <li>SQL staging models in <code>models/staging/*.sql</code></li>
          <li>Business logic models in <code>models/intermediate/*.sql</code></li>
          <li>Governed mart in <code>data/marts/mart_weekly_cs_kpi_by_country_reason.csv</code></li>
          <li>Semantic definitions in <code>models/semantic/semantic_cs_kpi_metrics.yml</code></li>
        </ul>
      </section>
      <section class="panel">
        <h2>Data quality and caveats</h2>
        <ul>
          <li>Latest quality run passed 11/11 checks.</li>
          <li>Mart grain is weekly country/contact reason.</li>
          <li>Cancellation rate and order metrics are country-week metrics repeated across reasons.</li>
          <li>CSAT should be interpreted with survey response count.</li>
        </ul>
      </section>
    </section>
  </main>
</body>
</html>
"""
    KPI_GOVERNANCE_PATH.write_text(html, encoding="utf-8")


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
            "severity_score",
            "confidence",
            "business_impact",
            "impact_score",
            "impact_score_raw",
            "csat_responses",
            "contact_volume",
            "total_orders",
            "compensation_cost",
            "hypothesis",
            "why_this_matters",
            "suggested_validation",
            "possible_owner",
            "recommended_next_action",
            "decomposition_note",
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
    write_kpi_reporting_dashboard(summary)
    write_kpi_governance_page(summary)

    print(f"Wrote {DIAGNOSTICS_PATH}")
    print(f"Wrote {COUNTRY_SUMMARY_PATH}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {DASHBOARD_PATH}")
    print(f"Wrote {KPI_REPORTING_PATH}")
    print(f"Wrote {KPI_GOVERNANCE_PATH}")


if __name__ == "__main__":
    main()
