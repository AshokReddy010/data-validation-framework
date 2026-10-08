-- A matching day should have no exception records. If it does, two errors
-- cancelled out in the totals and level 1 alone would have missed them.
select check_date, source
from {{ ref('check_results') }}
where status = 'match'
  and exception_records > 0
