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
