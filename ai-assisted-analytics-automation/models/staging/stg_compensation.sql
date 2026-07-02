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
