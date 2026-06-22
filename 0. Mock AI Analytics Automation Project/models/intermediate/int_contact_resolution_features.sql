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
