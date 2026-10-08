-- Level 1 comparison: each source against the reference, per day.
-- A day is a break when the counts differ, the totals differ by more than
-- the tolerance, or the source holds an amount that is null.
with calendar as (
    select distinct record_date from {{ ref('daily_totals') }}
),

compared_sources as (
    select 'client_feed' as source
    union all
    select 'billing' as source
),

reference as (
    select record_date, row_count, total_amount
    from {{ ref('daily_totals') }}
    where source = 'transactions'
),

actual as (
    select source, record_date, row_count, total_amount, null_amounts
    from {{ ref('daily_totals') }}
    where source <> 'transactions'
)

select
    c.record_date                                         as check_date,
    s.source,
    coalesce(r.row_count, 0)                              as expected_count,
    coalesce(a.row_count, 0)                              as actual_count,
    coalesce(a.row_count, 0) - coalesce(r.row_count, 0)   as count_diff,
    coalesce(r.total_amount, 0)                           as expected_total,
    coalesce(a.total_amount, 0)                           as actual_total,
    coalesce(a.total_amount, 0) - coalesce(r.total_amount, 0) as amount_diff,
    coalesce(a.null_amounts, 0)                           as null_amounts,
    case
        when coalesce(a.row_count, 0) <> coalesce(r.row_count, 0) then 'break'
        when abs(coalesce(a.total_amount, 0) - coalesce(r.total_amount, 0)) > {{ var('amount_tolerance') }} then 'break'
        when coalesce(a.null_amounts, 0) > 0 then 'break'
        else 'match'
    end                                                   as status
from calendar c
cross join compared_sources s
left join reference r on r.record_date = c.record_date
left join actual a on a.record_date = c.record_date and a.source = s.source
