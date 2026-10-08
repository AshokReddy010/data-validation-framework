-- Level 2: the records behind each break, with the reason.
-- check_date is the day whose totals the record throws off.
with reference as (
    select txn_id, record_date, amount from {{ ref('stg_transactions') }}
),

sources as (
    select 'client_feed' as source, txn_id, record_date, amount from {{ ref('stg_client_feed') }}
    union all
    select 'billing' as source, txn_id, record_date, amount from {{ ref('stg_billing') }}
),

numbered as (
    select
        source, txn_id, record_date, amount,
        row_number() over (partition by source, txn_id order by record_date) as copy_number
    from sources
),

first_copy as (
    select * from numbered where copy_number = 1
),

source_list as (
    select distinct source from sources
),

missing as (
    select
        sl.source, r.record_date as check_date, r.txn_id, 'missing_record' as reason,
        r.amount as expected_amount, cast(null as decimal(14, 2)) as actual_amount
    from reference r
    cross join source_list sl
    left join first_copy f on f.source = sl.source and f.txn_id = r.txn_id
    where f.txn_id is null
),

duplicates as (
    select
        n.source, n.record_date as check_date, n.txn_id, 'duplicate_record' as reason,
        r.amount as expected_amount, n.amount as actual_amount
    from numbered n
    join reference r on r.txn_id = n.txn_id
    where n.copy_number > 1
),

-- A record filed under the wrong day throws off two days: the day it should
-- be on, which comes up short, and the day it landed on, which comes up over.
wrong_date as (
    select
        f.source, r.record_date as check_date, f.txn_id, 'wrong_date' as reason,
        r.amount as expected_amount, f.amount as actual_amount
    from first_copy f
    join reference r on r.txn_id = f.txn_id
    where f.record_date <> r.record_date

    union all

    select
        f.source, f.record_date as check_date, f.txn_id, 'wrong_date' as reason,
        r.amount as expected_amount, f.amount as actual_amount
    from first_copy f
    join reference r on r.txn_id = f.txn_id
    where f.record_date <> r.record_date
),

null_amount as (
    select
        f.source, f.record_date as check_date, f.txn_id, 'null_amount' as reason,
        r.amount as expected_amount, f.amount as actual_amount
    from first_copy f
    join reference r on r.txn_id = f.txn_id
    where f.amount is null
),

amount_mismatch as (
    select
        f.source, f.record_date as check_date, f.txn_id, 'amount_mismatch' as reason,
        r.amount as expected_amount, f.amount as actual_amount
    from first_copy f
    join reference r on r.txn_id = f.txn_id
    where f.amount is not null
      and abs(f.amount - r.amount) > {{ var('amount_tolerance') }}
)

select * from missing
union all
select * from duplicates
union all
select * from wrong_date
union all
select * from null_amount
union all
select * from amount_mismatch
