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
