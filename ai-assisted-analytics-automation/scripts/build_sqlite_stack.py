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
    conn = sqlite3.connect(str(DB_PATH))
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
    QUALITY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    conn.close()
    if passed != len(results):
        raise SystemExit("One or more data quality checks failed.")
    print(f"Built {DB_PATH}")
    print(f"Exported {MART_PATH}")
    print(f"Wrote {QUALITY_PATH}")


if __name__ == "__main__":
    main()
