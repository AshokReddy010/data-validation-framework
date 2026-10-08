-- The table an alert or a dashboard reads: one row per source per day.
with reasons as (
    select source, check_date, reason, count(*) as records
    from {{ ref('recon_exceptions') }}
    group by source, check_date, reason
),

explained as (
    select
        source,
        check_date,
        sum(records)                                                    as exception_records,
        string_agg(reason || ': ' || cast(records as varchar), ', ' order by reason) as reasons
    from reasons
    group by source, check_date
)

select
    d.check_date,
    d.source,
    d.status,
    d.expected_count,
    d.actual_count,
    d.count_diff,
    d.amount_diff,
    coalesce(e.exception_records, 0) as exception_records,
    e.reasons
from {{ ref('recon_daily') }} d
left join explained e on e.source = d.source and e.check_date = d.check_date
