"""Illustrative Airflow DAG for the AI Analytics data foundation.

This file documents production-style orchestration. It is intentionally safe to keep in
the repository even when Airflow is not installed locally.
"""

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
