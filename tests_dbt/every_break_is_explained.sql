-- A break with no record-level reason means the drill-down missed something.
select check_date, source
from {{ ref('check_results') }}
where status = 'break'
  and exception_records = 0
