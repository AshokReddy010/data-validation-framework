-- Level 1: one row per source per day, with a count and a total.
with unioned as (
    select 'transactions' as source, record_date, amount from {{ ref('stg_transactions') }}
    union all
    select 'client_feed'  as source, record_date, amount from {{ ref('stg_client_feed') }}
    union all
    select 'billing'      as source, record_date, amount from {{ ref('stg_billing') }}
)

select
    source,
    record_date,
    count(*)                                        as row_count,
    coalesce(sum(amount), 0)                        as total_amount,
    sum(case when amount is null then 1 else 0 end) as null_amounts
from unioned
group by source, record_date
