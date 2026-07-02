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
