select
    record_id                                          as txn_id,
    account                                            as account_id,
    cast(trade_date as date)                           as record_date,
    cast(nullif(trim(amount), '') as decimal(14, 2))   as amount
from {{ source('raw', 'client_feed') }}
