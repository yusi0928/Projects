drop view if exists stg_orders;

create view stg_orders as
select
    order_id,
    customer_id_hash,
    upper(country_code) as country_code,
    date(order_created_at) as order_created_at,
    cast(cancelled_flag as integer) as cancelled_flag,
    cast(late_delivery_flag as integer) as late_delivery_flag,
    cast(delivery_delay_minutes as integer) as delivery_delay_minutes,
    datetime(updated_at) as updated_at
from raw_orders
where order_id is not null
  and order_created_at is not null;
