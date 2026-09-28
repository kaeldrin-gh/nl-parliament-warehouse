{% test single_row(model) %}
-- The model holds exactly one row.
select count(*) as row_count
from {{ model }}
having count(*) <> 1
{% endtest %}
