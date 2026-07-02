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
