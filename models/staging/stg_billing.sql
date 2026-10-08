select
    billing_id,
    txn_id,
    cast(bill_date as date)                 as record_date,
    cast(billed_amount as decimal(14, 2))   as amount
from {{ source('raw', 'billing') }}
