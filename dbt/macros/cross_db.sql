{# The few places where DuckDB and BigQuery SQL differ. #}

{% macro local_date(column) %}{{ return(adapter.dispatch('local_date')(column)) }}{% endmacro %}
{% macro default__local_date(column) %}cast(timezone('Europe/Amsterdam', {{ column }}) as date){% endmacro %}
{% macro bigquery__local_date(column) %}date({{ column }}, 'Europe/Amsterdam'){% endmacro %}

{% macro date_spine(start_date) %}{{ return(adapter.dispatch('date_spine')(start_date)) }}{% endmacro %}
{% macro default__date_spine(start_date) %}
    select cast(range as date) as date_day
    from range(
        timestamp '{{ start_date }}',
        cast(current_date + interval 366 day as timestamp),
        interval 1 day
    )
{% endmacro %}
{% macro bigquery__date_spine(start_date) %}
    select date_day
    from unnest(generate_date_array(date '{{ start_date }}', date_add(current_date(), interval 365 day))) as date_day
{% endmacro %}

{% macro iso_year(column) %}{{ return(adapter.dispatch('iso_year')(column)) }}{% endmacro %}
{% macro default__iso_year(column) %}cast(isoyear({{ column }}) as int64){% endmacro %}
{% macro bigquery__iso_year(column) %}extract(isoyear from {{ column }}){% endmacro %}

{% macro iso_week(column) %}{{ return(adapter.dispatch('iso_week')(column)) }}{% endmacro %}
{% macro default__iso_week(column) %}cast(weekofyear({{ column }}) as int64){% endmacro %}
{% macro bigquery__iso_week(column) %}extract(isoweek from {{ column }}){% endmacro %}

{# ISO day of week: Monday 1 to Sunday 7. #}
{% macro iso_day_of_week(column) %}{{ return(adapter.dispatch('iso_day_of_week')(column)) }}{% endmacro %}
{% macro default__iso_day_of_week(column) %}cast(isodow({{ column }}) as int64){% endmacro %}
{% macro bigquery__iso_day_of_week(column) %}mod(extract(dayofweek from {{ column }}) + 5, 7) + 1{% endmacro %}

{# One output row per element of an array column, as `alias`. #}
{% macro unnest_as(array_column, alias) %}{{ return(adapter.dispatch('unnest_as')(array_column, alias)) }}{% endmacro %}
{% macro default__unnest_as(array_column, alias) %}unnest({{ array_column }}) as unnested({{ alias }}){% endmacro %}
{% macro bigquery__unnest_as(array_column, alias) %}unnest({{ array_column }}) as {{ alias }}{% endmacro %}
