drop view if exists int_order_fulfillment_features;

create view int_order_fulfillment_features as
select
    order_id,
    customer_id_hash,
    country_code,
    date(order_created_at, '-' || ((cast(strftime('%w', order_created_at) as integer) + 6) % 7) || ' days') as week_start,
    order_created_at,
    cancelled_flag,
    late_delivery_flag,
    delivery_delay_minutes,
    updated_at
from stg_orders;
