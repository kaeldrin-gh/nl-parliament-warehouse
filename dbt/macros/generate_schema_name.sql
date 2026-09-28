{# Use the configured schema as-is (staging, core) instead of dbt's
   "<target schema>_<custom schema>", so both engines get the same names. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
