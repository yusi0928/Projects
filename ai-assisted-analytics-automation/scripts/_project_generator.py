from __future__ import annotations

import argparse
import csv
import hashlib
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


COUNTRIES = [
    ("DE", "Germany", "Central Europe", "EUR"),
    ("NL", "Netherlands", "Benelux", "EUR"),
    ("UK", "United Kingdom", "Northern Europe", "GBP"),
    ("PL", "Poland", "Central Europe", "PLN"),
    ("AT", "Austria", "Central Europe", "EUR"),
]

CONTACT_REASONS = [
    ("late_delivery", "Late delivery", "Delivery"),
    ("missing_item", "Missing item", "Order accuracy"),
    ("refund_request", "Refund request", "Payment and refunds"),
    ("cancellation", "Cancellation", "Order lifecycle"),
    ("payment_issue", "Payment issue", "Payment and refunds"),
    ("account_issue", "Account issue", "Account"),
]


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def hash_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:12]}"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def generate_data(project: Path) -> None:
    random.seed(42)
    start = date(2026, 1, 5)
    days = 16 * 7
    agents = [hash_id("agent", str(i)) for i in range(1, 61)]
    customers = [hash_id("cust", str(i)) for i in range(1, 2201)]

    country_rows = [
        {"country_code": c, "country_name": n, "region": r, "currency": cur}
        for c, n, r, cur in COUNTRIES
    ]
    reason_rows = [
        {
            "contact_reason_id": rid,
            "contact_reason_name": name,
            "reason_group": group,
            "is_ai_safe": 1,
        }
        for rid, name, group in CONTACT_REASONS
    ]

    orders = []
    contacts = []
    csat = []
    compensation = []
    activity = []
    contact_counter = 1
    order_counter = 1
    survey_counter = 1
    compensation_counter = 1

    base_orders = {"DE": 140, "NL": 90, "UK": 115, "PL": 75, "AT": 55}
    base_contact_rate = {
        "late_delivery": 0.020,
        "missing_item": 0.012,
        "refund_request": 0.011,
        "cancellation": 0.010,
        "payment_issue": 0.007,
        "account_issue": 0.006,
    }

    for day_i in range(days):
        current = start + timedelta(days=day_i)
        wk = ((week_start(current) - start).days // 7) + 1
        weekday_factor = 1.18 if current.weekday() in (4, 5, 6) else 0.92

        for country, _, _, _ in COUNTRIES:
            volume = int(base_orders[country] * weekday_factor * random.uniform(0.84, 1.16))
            for _ in range(volume):
                order_id = f"ord_{order_counter:07d}"
                order_counter += 1
                customer_id = random.choice(customers)

                late_prob = 0.08
                cancel_prob = 0.045
                if country == "DE" and wk in (12, 13):
                    late_prob += 0.15
                if country == "UK" and wk in (10, 11):
                    cancel_prob += 0.065
                late_delivery = random.random() < late_prob
                cancelled = random.random() < cancel_prob
                delay = 0
                if late_delivery:
                    delay = int(random.uniform(15, 95))

                updated_at = datetime.combine(current, datetime.min.time()) + timedelta(
                    hours=random.randint(1, 23), minutes=random.randint(0, 59)
                )
                if random.random() < 0.03:
                    updated_at += timedelta(days=random.randint(1, 10))

                orders.append(
                    {
                        "order_id": order_id,
                        "customer_id_hash": customer_id,
                        "country_code": country,
                        "order_created_at": current.isoformat(),
                        "cancelled_flag": int(cancelled),
                        "late_delivery_flag": int(late_delivery),
                        "delivery_delay_minutes": delay,
                        "updated_at": updated_at.isoformat(timespec="seconds"),
                    }
                )

                for reason_id, _, _ in CONTACT_REASONS:
                    contact_prob = base_contact_rate[reason_id]
                    if late_delivery and reason_id == "late_delivery":
                        contact_prob += 0.20
                    if cancelled and reason_id == "cancellation":
                        contact_prob += 0.18
                    if country == "NL" and wk == 14 and reason_id == "refund_request":
                        contact_prob += 0.06
                    if country == "PL" and wk == 15:
                        contact_prob += 0.015
                    if random.random() >= contact_prob:
                        continue

                    created_dt = datetime.combine(current, datetime.min.time()) + timedelta(
                        hours=random.randint(8, 22), minutes=random.randint(0, 59)
                    )
                    handling_base = {
                        "late_delivery": 470,
                        "missing_item": 420,
                        "refund_request": 540,
                        "cancellation": 360,
                        "payment_issue": 620,
                        "account_issue": 520,
                    }[reason_id]
                    handling = int(max(90, random.gauss(handling_base, 120)))
                    if country == "DE" and wk in (12, 13) and reason_id == "late_delivery":
                        handling += int(random.uniform(180, 420))
                    if country == "NL" and wk == 14 and reason_id == "refund_request":
                        handling += int(random.uniform(90, 220))

                    backlog_pressure = country == "DE" and wk in (12, 13) and reason_id == "late_delivery"
                    resolved = random.random() > (0.08 + (0.18 if backlog_pressure else 0))
                    resolution_days = random.choice([0, 0, 1, 1, 2, 3, 5])
                    resolved_at = ""
                    status = "open"
                    if resolved:
                        resolved_dt = created_dt + timedelta(days=resolution_days, seconds=handling)
                        resolved_at = resolved_dt.isoformat(timespec="seconds")
                        status = "resolved"
                    reopened = int(resolved and random.random() < (0.10 if reason_id in ("refund_request", "late_delivery") else 0.05))
                    updated_contact = created_dt + timedelta(days=random.randint(0, 9), hours=random.randint(0, 8))

                    contact_id = f"con_{contact_counter:07d}"
                    contact_counter += 1
                    agent_id = random.choice(agents)
                    contacts.append(
                        {
                            "contact_id": contact_id,
                            "order_id": order_id,
                            "customer_id_hash": customer_id,
                            "agent_id_hash": agent_id,
                            "country_code": country,
                            "contact_reason_id": reason_id,
                            "created_at": created_dt.isoformat(timespec="seconds"),
                            "resolved_at": resolved_at,
                            "status": status,
                            "reopened_flag": reopened,
                            "handling_time_seconds": handling if resolved else 0,
                            "updated_at": updated_contact.isoformat(timespec="seconds"),
                        }
                    )

                    if resolved and random.random() < 0.36:
                        score_base = 4.2
                        if reason_id == "late_delivery":
                            score_base -= 0.35
                        if country == "DE" and wk in (12, 13) and reason_id == "late_delivery":
                            score_base -= 0.55
                        if country == "UK" and wk in (10, 11) and cancelled:
                            score_base -= 0.45
                        if reopened:
                            score_base -= 0.35
                        score = min(5, max(1, round(random.gauss(score_base, 0.65))))
                        survey_dt = created_dt + timedelta(days=random.choice([1, 2, 3, 7, 9]))
                        csat.append(
                            {
                                "survey_id": f"sur_{survey_counter:07d}",
                                "contact_id": contact_id,
                                "score": score,
                                "submitted_at": survey_dt.isoformat(timespec="seconds"),
                                "updated_at": (survey_dt + timedelta(hours=1)).isoformat(timespec="seconds"),
                            }
                        )
                        survey_counter += 1

                    needs_comp = reason_id in ("refund_request", "missing_item", "late_delivery") and random.random() < 0.32
                    if country == "NL" and wk == 14 and reason_id == "refund_request":
                        needs_comp = random.random() < 0.72
                    if needs_comp:
                        refund = round(random.uniform(2, 18), 2) if reason_id in ("refund_request", "missing_item") else 0.0
                        voucher = round(random.uniform(3, 14), 2) if reason_id in ("late_delivery", "refund_request") else 0.0
                        goodwill = round(random.uniform(2, 9), 2) if random.random() < 0.45 else 0.0
                        if country == "NL" and wk == 14:
                            goodwill += round(random.uniform(5, 18), 2)
                        comp_dt = created_dt + timedelta(days=random.choice([0, 1, 2, 5, 8]))
                        compensation.append(
                            {
                                "compensation_id": f"cmp_{compensation_counter:07d}",
                                "contact_id": contact_id,
                                "order_id": order_id,
                                "refund_amount": refund,
                                "voucher_amount": voucher,
                                "goodwill_amount": goodwill,
                                "created_at": comp_dt.isoformat(timespec="seconds"),
                                "updated_at": (comp_dt + timedelta(hours=2)).isoformat(timespec="seconds"),
                            }
                        )
                        compensation_counter += 1

        for country, _, _, _ in COUNTRIES:
            country_agents = random.sample(agents, 12)
            for agent_id in country_agents:
                scheduled = random.choice([240, 360, 420, 480])
                available = max(0, scheduled - random.randint(20, 80))
                handled = int(available / random.uniform(18, 32))
                activity.append(
                    {
                        "agent_id_hash": agent_id,
                        "activity_date": current.isoformat(),
                        "country_code": country,
                        "scheduled_minutes": scheduled,
                        "available_minutes": available,
                        "handled_contacts": handled,
                        "updated_at": datetime.combine(current, datetime.min.time()).isoformat(timespec="seconds"),
                    }
                )

    write_csv(project / "data/seeds/dim_country.csv", country_rows)
    write_csv(project / "data/seeds/dim_contact_reason.csv", reason_rows)
    write_csv(project / "data/raw/raw_orders.csv", orders)
    write_csv(project / "data/raw/raw_contacts.csv", contacts)
    write_csv(project / "data/raw/raw_csat_surveys.csv", csat)
    write_csv(project / "data/raw/raw_compensation.csv", compensation)
    write_csv(project / "data/raw/raw_agent_activity.csv", activity)


def project_files(project: Path) -> None:
    write_text(
        project / "README.md",
        """
# AI Analytics: AI-Ready CS Operations Data Foundation

This repository is a self-initiated portfolio project that simulates a marketplace customer support analytics stack. It focuses on the data foundation required before dashboards or AI-assisted analytics can be trusted.

The current milestone stops at the semantic layer:

```text
synthetic raw operational data
-> staging models
-> intermediate business logic
-> governed weekly KPI mart
-> semantic metric definitions
-> quality checks, orchestration design, privacy controls
```

Later milestones can add weekly diagnostics, visualization, AI-assisted root-cause hypotheses, human validation, and leadership WBR reporting.

## Business Context

Customer Support leadership needs a weekly business review across countries and contact reasons. The key metrics are contact volume, AHT, FCR, CSAT, backlog, compensation cost, cancellation rate, and contact rate.

This project intentionally starts from raw operational tables rather than a clean CSV, because AI-enabled analytics depends on trusted data foundations, consistent KPI definitions, and quality controls.

## Architecture

```text
raw_contacts          -> stg_contacts          -> int_contact_resolution_features
raw_orders            -> stg_orders            -> int_order_fulfillment_features
raw_csat_surveys      -> stg_csat_surveys      -> int_contact_csat
raw_compensation      -> stg_compensation      -> int_contact_compensation
raw_agent_activity    -> stg_agent_activity    -> int_staffing_capacity
dim_country           -> dim_country
dim_contact_reason    -> dim_contact_reason

intermediate models -> mart_weekly_cs_kpi_by_country_reason
mart + definitions  -> semantic layer / AI-safe analytical layer
```

## How To Run

This project uses Python standard library and SQLite only.

```bash
python3 scripts/generate_synthetic_data.py
python3 scripts/build_sqlite_stack.py
```

Outputs:

- `build/ai_analytics.db`
- `data/marts/mart_weekly_cs_kpi_by_country_reason.csv`
- `docs/data_quality_results.md`

## What This Demonstrates

- Raw-to-mart analytics engineering design
- dbt-style model layering without requiring dbt to run locally
- Metric definition and semantic layer thinking
- Incremental loading and late-arriving data design
- Airflow-style orchestration and dependency management
- Data quality gates before analysis or AI
- Privacy controls for AI-ready analytics

## Data Privacy

All data is synthetic. IDs are hashed-looking synthetic identifiers. The project does not include names, emails, phone numbers, addresses, or customer message text. The AI-safe layer is aggregated to weekly country/contact-reason grain.
""",
    )

    write_text(
        project / "models/staging/stg_contacts.sql",
        """
drop view if exists stg_contacts;

create view stg_contacts as
select
    contact_id,
    order_id,
    customer_id_hash,
    agent_id_hash,
    upper(country_code) as country_code,
    lower(contact_reason_id) as contact_reason_id,
    datetime(created_at) as created_at,
    nullif(datetime(resolved_at), '') as resolved_at,
    lower(status) as status,
    cast(reopened_flag as integer) as reopened_flag,
    cast(handling_time_seconds as integer) as handling_time_seconds,
    datetime(updated_at) as updated_at
from raw_contacts
where contact_id is not null
  and created_at is not null;
""",
    )
    write_text(
        project / "models/staging/stg_orders.sql",
        """
drop view if exists stg_orders;

create view stg_orders as
select
    order_id,
    customer_id_hash,
    upper(country_code) as country_code,
    date(order_created_at) as order_created_at,
    cast(cancelled_flag as integer) as cancelled_flag,
    cast(late_delivery_flag as integer) as late_delivery_flag,
    cast(delivery_delay_minutes as integer) as delivery_delay_minutes,
    datetime(updated_at) as updated_at
from raw_orders
where order_id is not null
  and order_created_at is not null;
""",
    )
    write_text(
        project / "models/staging/stg_csat_surveys.sql",
        """
drop view if exists stg_csat_surveys;

create view stg_csat_surveys as
select
    survey_id,
    contact_id,
    cast(score as integer) as score,
    datetime(submitted_at) as submitted_at,
    datetime(updated_at) as updated_at
from raw_csat_surveys
where survey_id is not null
  and contact_id is not null;
""",
    )
    write_text(
        project / "models/staging/stg_compensation.sql",
        """
drop view if exists stg_compensation;

create view stg_compensation as
select
    compensation_id,
    contact_id,
    order_id,
    cast(refund_amount as real) as refund_amount,
    cast(voucher_amount as real) as voucher_amount,
    cast(goodwill_amount as real) as goodwill_amount,
    datetime(created_at) as created_at,
    datetime(updated_at) as updated_at
from raw_compensation
where compensation_id is not null;
""",
    )
    write_text(
        project / "models/staging/stg_agent_activity.sql",
        """
drop view if exists stg_agent_activity;

create view stg_agent_activity as
select
    agent_id_hash,
    date(activity_date) as activity_date,
    upper(country_code) as country_code,
    cast(scheduled_minutes as integer) as scheduled_minutes,
    cast(available_minutes as integer) as available_minutes,
    cast(handled_contacts as integer) as handled_contacts,
    datetime(updated_at) as updated_at
from raw_agent_activity
where agent_id_hash is not null
  and activity_date is not null;
""",
    )

    write_text(
        project / "models/intermediate/int_contact_resolution_features.sql",
        """
drop view if exists int_contact_resolution_features;

create view int_contact_resolution_features as
select
    c.contact_id,
    c.order_id,
    c.customer_id_hash,
    c.agent_id_hash,
    c.country_code,
    c.contact_reason_id,
    date(c.created_at, '-' || ((cast(strftime('%w', c.created_at) as integer) + 6) % 7) || ' days') as week_start,
    date(date(c.created_at, '-' || ((cast(strftime('%w', c.created_at) as integer) + 6) % 7) || ' days'), '+6 days') as week_end,
    c.created_at,
    c.resolved_at,
    c.status,
    c.reopened_flag,
    c.handling_time_seconds / 60.0 as handling_time_minutes,
    case when c.status = 'resolved' then 1 else 0 end as is_resolved,
    case when c.status = 'resolved' and c.reopened_flag = 0 then 1 else 0 end as is_fcr_success,
    case
        when c.status <> 'resolved' then 1
        when c.resolved_at > datetime(date(date(c.created_at, '-' || ((cast(strftime('%w', c.created_at) as integer) + 6) % 7) || ' days'), '+6 days'), '+23 hours', '+59 minutes') then 1
        else 0
    end as is_backlog_at_week_end,
    c.updated_at
from stg_contacts c;
""",
    )
    write_text(
        project / "models/intermediate/int_order_fulfillment_features.sql",
        """
drop view if exists int_order_fulfillment_features;

create view int_order_fulfillment_features as
select
    order_id,
    customer_id_hash,
    country_code,
    date(order_created_at, '-' || ((cast(strftime('%w', order_created_at) as integer) + 6) % 7) || ' days') as week_start,
    order_created_at,
    cancelled_flag,
    late_delivery_flag,
    delivery_delay_minutes,
    updated_at
from stg_orders;
""",
    )
    write_text(
        project / "models/intermediate/int_contact_csat.sql",
        """
drop view if exists int_contact_csat;

create view int_contact_csat as
select
    c.contact_id,
    c.country_code,
    c.contact_reason_id,
    c.week_start,
    s.survey_id,
    s.score as csat_score,
    s.submitted_at,
    s.updated_at
from int_contact_resolution_features c
left join stg_csat_surveys s
    on c.contact_id = s.contact_id;
""",
    )
    write_text(
        project / "models/intermediate/int_contact_compensation.sql",
        """
drop view if exists int_contact_compensation;

create view int_contact_compensation as
select
    c.contact_id,
    c.order_id,
    c.country_code,
    c.contact_reason_id,
    c.week_start,
    coalesce(sum(sc.refund_amount), 0) as refund_amount,
    coalesce(sum(sc.voucher_amount), 0) as voucher_amount,
    coalesce(sum(sc.goodwill_amount), 0) as goodwill_amount,
    coalesce(sum(sc.refund_amount + sc.voucher_amount + sc.goodwill_amount), 0) as compensation_cost
from int_contact_resolution_features c
left join stg_compensation sc
    on c.contact_id = sc.contact_id
group by 1,2,3,4,5;
""",
    )
    write_text(
        project / "models/intermediate/int_staffing_capacity.sql",
        """
drop view if exists int_staffing_capacity;

create view int_staffing_capacity as
select
    date(activity_date, '-' || ((cast(strftime('%w', activity_date) as integer) + 6) % 7) || ' days') as week_start,
    country_code,
    count(distinct agent_id_hash) as active_agents,
    sum(scheduled_minutes) as scheduled_minutes,
    sum(available_minutes) as available_minutes,
    sum(handled_contacts) as handled_contacts
from stg_agent_activity
group by 1,2;
""",
    )
    write_text(
        project / "models/marts/mart_weekly_cs_kpi_by_country_reason.sql",
        """
drop table if exists mart_weekly_cs_kpi_by_country_reason;

create table mart_weekly_cs_kpi_by_country_reason as
with order_week_country as (
    select
        week_start,
        country_code,
        count(*) as total_orders,
        sum(cancelled_flag) as cancelled_orders,
        sum(late_delivery_flag) as late_delivery_orders
    from int_order_fulfillment_features
    group by 1,2
),
contact_base as (
    select
        c.week_start,
        c.country_code,
        c.contact_reason_id,
        count(*) as contact_volume,
        sum(c.is_resolved) as resolved_contacts,
        sum(c.is_fcr_success) as fcr_success_contacts,
        avg(case when c.is_resolved = 1 then c.handling_time_minutes end) as avg_aht_minutes,
        sum(c.is_backlog_at_week_end) as backlog_end_of_week
    from int_contact_resolution_features c
    group by 1,2,3
),
csat_base as (
    select
        week_start,
        country_code,
        contact_reason_id,
        count(csat_score) as csat_responses,
        avg(csat_score) as avg_csat
    from int_contact_csat
    group by 1,2,3
),
comp_base as (
    select
        week_start,
        country_code,
        contact_reason_id,
        sum(compensation_cost) as compensation_cost
    from int_contact_compensation
    group by 1,2,3
)
select
    cb.week_start,
    dc.country_name,
    cb.country_code,
    dcr.contact_reason_name,
    cb.contact_reason_id,
    cb.contact_volume,
    round(cb.avg_aht_minutes, 2) as avg_aht_minutes,
    round(case when cb.resolved_contacts = 0 then null else cb.fcr_success_contacts * 1.0 / cb.resolved_contacts end, 4) as fcr_rate,
    round(cs.avg_csat, 2) as avg_csat,
    coalesce(cs.csat_responses, 0) as csat_responses,
    cb.backlog_end_of_week,
    round(coalesce(co.compensation_cost, 0), 2) as compensation_cost,
    owc.total_orders,
    owc.cancelled_orders,
    round(owc.cancelled_orders * 1.0 / nullif(owc.total_orders, 0), 4) as cancellation_rate,
    round(cb.contact_volume * 1.0 / nullif(owc.total_orders, 0), 4) as contact_rate,
    sc.active_agents,
    sc.available_minutes,
    datetime('now') as built_at
from contact_base cb
left join csat_base cs
    on cb.week_start = cs.week_start
    and cb.country_code = cs.country_code
    and cb.contact_reason_id = cs.contact_reason_id
left join comp_base co
    on cb.week_start = co.week_start
    and cb.country_code = co.country_code
    and cb.contact_reason_id = co.contact_reason_id
left join order_week_country owc
    on cb.week_start = owc.week_start
    and cb.country_code = owc.country_code
left join int_staffing_capacity sc
    on cb.week_start = sc.week_start
    and cb.country_code = sc.country_code
left join dim_country dc
    on cb.country_code = dc.country_code
left join dim_contact_reason dcr
    on cb.contact_reason_id = dcr.contact_reason_id;
""",
    )

    write_text(
        project / "models/semantic/semantic_cs_kpi_metrics.yml",
        """
semantic_model:
  name: cs_weekly_operations
  description: Weekly customer support KPI semantic layer at country and contact reason grain.
  model: mart_weekly_cs_kpi_by_country_reason
  grain:
    - week_start
    - country_code
    - contact_reason_id
  owner: CS Operations Analytics
  refresh_cadence: Weekly on Monday morning after rolling two-week reprocessing
  ai_usage_policy: AI may use this aggregated mart and metric definitions, but may not access raw contact, customer, agent, or free-text data.

metrics:
  - name: contact_volume
    definition: Number of contacts created in the week.
    ai_safe: true
  - name: avg_aht_minutes
    definition: Average handling time in minutes for resolved contacts.
    ai_safe: true
  - name: fcr_rate
    definition: Resolved contacts not reopened within the observation window divided by resolved contacts.
    ai_safe: true
  - name: avg_csat
    definition: Average submitted CSAT score linked to contacts.
    ai_safe: true
  - name: backlog_end_of_week
    definition: Contacts created in the week that remain open at week end.
    ai_safe: true
  - name: compensation_cost
    definition: Refund, voucher, and goodwill amount linked to contacts.
    ai_safe: true
  - name: cancellation_rate
    definition: Cancelled orders divided by total orders at country-week level.
    caveat: Repeated across contact reasons for the same country-week.
    ai_safe: true
""",
    )

    write_text(
        project / "scripts/generate_synthetic_data.py",
        """
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "_project_generator.py"

namespace = runpy.run_path(str(GENERATOR))
namespace["generate_data"](ROOT)
print("Synthetic data regenerated.")
""",
    )
    write_text(
        project / "scripts/_project_generator.py",
        Path(__file__).read_text(encoding="utf-8"),
    )
    write_text(
        project / "scripts/build_sqlite_stack.py",
        """
from pathlib import Path
import csv
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "build" / "ai_analytics.db"
MART_PATH = ROOT / "data" / "marts" / "mart_weekly_cs_kpi_by_country_reason.csv"
QUALITY_PATH = ROOT / "docs" / "data_quality_results.md"

RAW_FILES = {
    "raw_orders": ROOT / "data/raw/raw_orders.csv",
    "raw_contacts": ROOT / "data/raw/raw_contacts.csv",
    "raw_csat_surveys": ROOT / "data/raw/raw_csat_surveys.csv",
    "raw_compensation": ROOT / "data/raw/raw_compensation.csv",
    "raw_agent_activity": ROOT / "data/raw/raw_agent_activity.csv",
    "dim_country": ROOT / "data/seeds/dim_country.csv",
    "dim_contact_reason": ROOT / "data/seeds/dim_contact_reason.csv",
}

SQL_ORDER = [
    "models/staging/stg_contacts.sql",
    "models/staging/stg_orders.sql",
    "models/staging/stg_csat_surveys.sql",
    "models/staging/stg_compensation.sql",
    "models/staging/stg_agent_activity.sql",
    "models/intermediate/int_contact_resolution_features.sql",
    "models/intermediate/int_order_fulfillment_features.sql",
    "models/intermediate/int_contact_csat.sql",
    "models/intermediate/int_contact_compensation.sql",
    "models/intermediate/int_staffing_capacity.sql",
    "models/marts/mart_weekly_cs_kpi_by_country_reason.sql",
]


def load_csv(conn, table_name, path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError(f"No rows in {path}")
    cols = reader.fieldnames
    conn.execute(f"drop table if exists {table_name}")
    conn.execute(
        f"create table {table_name} ({', '.join([c + ' text' for c in cols])})"
    )
    placeholders = ",".join(["?"] * len(cols))
    conn.executemany(
        f"insert into {table_name} ({', '.join(cols)}) values ({placeholders})",
        [[row[c] for c in cols] for row in rows],
    )


def scalar(conn, sql):
    return conn.execute(sql).fetchone()[0]


def run_quality_checks(conn):
    checks = [
        ("raw_orders primary key uniqueness", "select count(*) = count(distinct order_id) from raw_orders"),
        ("raw_contacts primary key uniqueness", "select count(*) = count(distinct contact_id) from raw_contacts"),
        ("raw_csat_surveys primary key uniqueness", "select count(*) = count(distinct survey_id) from raw_csat_surveys"),
        ("raw_compensation primary key uniqueness", "select count(*) = count(distinct compensation_id) from raw_compensation"),
        ("valid contact status values", "select count(*) = 0 from stg_contacts where status not in ('open','resolved')"),
        ("valid CSAT score range", "select count(*) = 0 from stg_csat_surveys where score < 1 or score > 5"),
        ("non-negative handling time", "select count(*) = 0 from stg_contacts where handling_time_seconds < 0"),
        ("non-negative compensation amounts", "select count(*) = 0 from stg_compensation where refund_amount < 0 or voucher_amount < 0 or goodwill_amount < 0"),
        ("mart grain uniqueness", "select count(*) = count(distinct week_start || '|' || country_code || '|' || contact_reason_id) from mart_weekly_cs_kpi_by_country_reason"),
        ("rate metrics within bounds", "select count(*) = 0 from mart_weekly_cs_kpi_by_country_reason where fcr_rate < 0 or fcr_rate > 1 or cancellation_rate < 0 or cancellation_rate > 1 or contact_rate < 0"),
        ("AI-safe mart has no direct customer or agent IDs", "select count(*) = 0 from pragma_table_info('mart_weekly_cs_kpi_by_country_reason') where name like '%customer%' or name like '%agent_id%'"),
    ]
    results = []
    for name, sql in checks:
        passed = bool(scalar(conn, sql))
        results.append((name, passed))
    return results


def export_table(conn, table_name, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = conn.execute(f"select * from {table_name} order by week_start, country_code, contact_reason_id").fetchall()
    cols = [d[0] for d in conn.execute(f"select * from {table_name} limit 1").description]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    for table, path in RAW_FILES.items():
        load_csv(conn, table, path)
    for sql_file in SQL_ORDER:
        conn.executescript((ROOT / sql_file).read_text(encoding="utf-8"))
    conn.commit()
    results = run_quality_checks(conn)
    export_table(conn, "mart_weekly_cs_kpi_by_country_reason", MART_PATH)

    passed = sum(1 for _, ok in results if ok)
    lines = [
        "# Data Quality Results",
        "",
        f"Generated from `scripts/build_sqlite_stack.py`.",
        "",
        f"Passed {passed}/{len(results)} checks.",
        "",
        "| Check | Status |",
        "| --- | --- |",
    ]
    for name, ok in results:
        lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} |")
    QUALITY_PATH.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    conn.close()
    if passed != len(results):
        raise SystemExit("One or more data quality checks failed.")
    print(f"Built {DB_PATH}")
    print(f"Exported {MART_PATH}")
    print(f"Wrote {QUALITY_PATH}")


if __name__ == "__main__":
    main()
""",
    )

    write_text(
        project / "orchestration/airflow_dag.py",
        """
\"\"\"Illustrative Airflow DAG for the AI Analytics data foundation.

This file documents production-style orchestration. It is intentionally safe to keep in
the repository even when Airflow is not installed locally.
\"\"\"

from datetime import datetime, timedelta


DAG_ID = "ai_analytics_cs_weekly_kpi_foundation"
SCHEDULE = "0 6 * * 1"  # Monday 06:00, before weekly business review.
ROLLING_REPROCESSING_WINDOW_WEEKS = 2


TASK_DEPENDENCIES = {
    "ingest_raw_orders": [],
    "ingest_raw_contacts": [],
    "ingest_raw_csat_surveys": [],
    "ingest_raw_compensation": [],
    "ingest_raw_agent_activity": [],
    "run_raw_data_quality_checks": [
        "ingest_raw_orders",
        "ingest_raw_contacts",
        "ingest_raw_csat_surveys",
        "ingest_raw_compensation",
        "ingest_raw_agent_activity",
    ],
    "build_staging_models": ["run_raw_data_quality_checks"],
    "build_intermediate_models": ["build_staging_models"],
    "build_weekly_cs_kpi_mart_incremental": ["build_intermediate_models"],
    "run_kpi_quality_checks": ["build_weekly_cs_kpi_mart_incremental"],
    "publish_semantic_layer": ["run_kpi_quality_checks"],
    "mark_ai_safe_dataset_ready": ["publish_semantic_layer"],
}


DEFAULT_ARGS = {
    "owner": "cs-operations-analytics",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=15),
    "start_date": datetime(2026, 1, 1),
}


def describe_dependency_order():
    for task, upstream in TASK_DEPENDENCIES.items():
        print(f"{task}: depends on {upstream or 'source system availability'}")


if __name__ == "__main__":
    describe_dependency_order()
""",
    )

    write_text(
        project / "docs/business_case.md",
        """
# Business Case

Customer Support leadership needs a weekly business review that explains KPI movement across countries and contact reasons.

The analytics team wants to make the workflow AI-ready, but the AI layer must not read raw operational data directly. First, the team needs a trusted data foundation:

1. Stable raw source ingestion
2. Staging cleanup and standardization
3. Intermediate business logic
4. Governed KPI mart
5. Metric definitions and semantic layer
6. Quality checks and privacy controls

The current milestone builds that foundation.
""",
    )
    write_text(
        project / "docs/data_lineage.md",
        """
# Data Lineage And Pipeline Dependencies

```mermaid
flowchart TD
    raw_orders[raw_orders] --> stg_orders[stg_orders]
    raw_contacts[raw_contacts] --> stg_contacts[stg_contacts]
    raw_csat[raw_csat_surveys] --> stg_csat[stg_csat_surveys]
    raw_comp[raw_compensation] --> stg_comp[stg_compensation]
    raw_agent[raw_agent_activity] --> stg_agent[stg_agent_activity]

    stg_contacts --> int_contact[int_contact_resolution_features]
    stg_orders --> int_order[int_order_fulfillment_features]
    stg_csat --> int_csat[int_contact_csat]
    stg_comp --> int_comp[int_contact_compensation]
    stg_agent --> int_staff[int_staffing_capacity]

    int_contact --> mart[mart_weekly_cs_kpi_by_country_reason]
    int_order --> mart
    int_csat --> mart
    int_comp --> mart
    int_staff --> mart
    dim_country[dim_country] --> mart
    dim_reason[dim_contact_reason] --> mart

    mart --> semantic[semantic_cs_kpi_metrics]
    semantic --> ai_safe[AI-safe aggregated analytics layer]
```

The AI or reporting layer must run only after the mart and quality checks pass.
""",
    )
    write_text(
        project / "docs/metric_definitions.md",
        """
# Metric Definitions

The primary mart is `mart_weekly_cs_kpi_by_country_reason`.

Grain: one row per `week_start`, `country_code`, and `contact_reason_id`.

| Metric | Definition | Caveat |
| --- | --- | --- |
| contact_volume | Number of contacts created in the week. | Contact creation week is used. |
| avg_aht_minutes | Average handling time for resolved contacts. | Open contacts are excluded from AHT. |
| fcr_rate | Resolved contacts not reopened divided by resolved contacts. | Uses synthetic reopen flag as 7-day proxy. |
| avg_csat | Average submitted survey score linked to contacts. | Survey response bias may exist. |
| backlog_end_of_week | Contacts created in the week that remain open at week end. | Not a full historical backlog snapshot. |
| compensation_cost | Refund + voucher + goodwill amount linked to contacts. | Late compensation can update prior weeks. |
| cancellation_rate | Cancelled orders divided by total orders at country-week level. | Repeated across contact reasons. |
| contact_rate | Contacts divided by total orders. | Contact reason rows are not additive for this rate. |

Metric owner: CS Operations Analytics.

Refresh cadence: weekly every Monday after rolling two-week reprocessing.
""",
    )
    write_text(
        project / "docs/privacy_controls.md",
        """
# Privacy Controls

This repository uses synthetic data only.

## Implemented Controls

- No customer names, emails, phone numbers, addresses, or free-text support messages.
- Customer and agent identifiers are hashed-looking synthetic IDs.
- The AI-safe layer is aggregated to weekly country/contact-reason grain.
- The mart does not expose customer-level or agent-level identifiers.

## Real Enterprise Controls

- Keep raw contact-level data in a restricted access layer.
- Redact or exclude free-text fields before AI usage.
- Tokenize customer and agent identifiers.
- Allow AI to consume only approved marts, metric definitions, data quality status, and analyst validation notes.
- Log AI prompt inputs and outputs for auditability.
""",
    )
    write_text(
        project / "docs/data_quality_checks.md",
        """
# Data Quality Checks

Quality checks are executed by `scripts/build_sqlite_stack.py`.

Checks include:

- Primary key uniqueness for raw source tables
- Accepted values for contact status
- CSAT scores between 1 and 5
- Non-negative handling time and compensation values
- Mart uniqueness at `week_start + country_code + contact_reason_id`
- Rate metrics within expected bounds
- AI-safe mart excludes direct customer and agent identifiers

The AI/reporting layer should not run if these checks fail.
""",
    )
    write_text(
        project / "docs/operating_model.md",
        """
# Operating Model

## Refresh Cadence

- Raw operational sources: daily ingestion.
- Staging and intermediate models: daily refresh.
- Weekly KPI mart: Monday morning before CS weekly business review.
- Semantic layer: published only after KPI quality checks pass.

## Incremental Loading

Raw tables include `created_at` and/or `updated_at` fields. In production, ingestion would use a watermark table to load new or changed records.

Recommended strategy:

- Append new source records daily.
- Rebuild current week and previous two weeks to handle late CSAT, compensation, reopened contacts, and order status corrections.
- Trigger targeted backfills when source corrections affect older periods.
- Store aggregated marts longer than raw operational records.

## Ownership

- Source systems: operational system owners.
- KPI definitions: CS Operations Analytics.
- Pipeline orchestration: Analytics Engineering.
- AI usage policy: Analytics + Data Governance.
""",
    )
    write_text(
        project / "docs/resume_bullets.md",
        """
# Resume Positioning

## Project Title

AI-Ready CS Operations Analytics Stack

## Resume Bullet

Designed a self-initiated analytics engineering portfolio project simulating a marketplace customer support data environment. Built dbt-style data models from raw operational tables to governed weekly KPI marts, including metric definitions, data quality checks, incremental loading design, Airflow-style orchestration, privacy controls, and AI-ready semantic layer documentation.

## Supporting Bullets

- Modeled raw CS, order, CSAT, compensation, and agent activity data into staging, intermediate, and weekly KPI mart layers.
- Defined governed KPI semantics for contact volume, AHT, FCR, CSAT, backlog, compensation cost, cancellation rate, and contact rate.
- Added data quality gates and privacy controls to ensure downstream dashboards or AI summaries use only trusted aggregated outputs.
- Documented orchestration dependencies, refresh cadence, late-arriving data handling, and rolling reprocessing logic.
""",
    )


def build_stack(project: Path) -> None:
    script = project / "scripts/build_sqlite_stack.py"
    namespace = {"__file__": str(script), "__name__": "__main__"}
    exec(script.read_text(encoding="utf-8"), namespace)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    target = args.target
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"Target already exists and is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    project_files(target)
    generate_data(target)
    build_stack(target)
    print(f"Created AI Analytics project at: {target}")


if __name__ == "__main__":
    main()
