{% test unique_combination(model, columns) %}
-- Fails when the listed columns, taken together, repeat.
select {{ columns | join(', ') }}, count(*) as copies
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
