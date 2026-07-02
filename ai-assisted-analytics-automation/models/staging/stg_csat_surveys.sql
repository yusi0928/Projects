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
