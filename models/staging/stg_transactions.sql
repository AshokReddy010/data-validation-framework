select
    txn_id,
    account_id,
    cast(txn_date as date)            as record_date,
    cast(amount as decimal(14, 2))    as amount,
    status
from {{ source('raw', 'transactions') }}
