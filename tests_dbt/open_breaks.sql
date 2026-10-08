-- Warns, without failing the build, while any break is open.
{{ config(severity = 'warn') }}
select check_date, source, reasons
from {{ ref('check_results') }}
where status = 'break'
