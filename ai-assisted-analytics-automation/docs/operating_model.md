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
