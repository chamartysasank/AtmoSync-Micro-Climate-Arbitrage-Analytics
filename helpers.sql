{# Cross-database helpers so the same models run on Snowflake and DuckDB. #}

{% macro json_val(col, key, dtype) %}{{ return(adapter.dispatch('json_val', 'atmosync')(col, key, dtype)) }}{% endmacro %}

{% macro default__json_val(col, key, dtype) %}
    {%- if dtype == 'varchar' -%} {{ col }}:{{ key }}::varchar
    {%- elif dtype == 'double' -%} {{ col }}:{{ key }}::float
    {%- elif dtype == 'timestamp' -%} to_timestamp_ntz(replace(replace({{ col }}:{{ key }}::varchar, 'T', ' '), 'Z', ''))
    {%- endif -%}
{% endmacro %}

{% macro duckdb__json_val(col, key, dtype) %}
    {%- if dtype == 'varchar' -%} json_extract_string({{ col }}, '$.{{ key }}')
    {%- elif dtype == 'double' -%} cast(json_extract_string({{ col }}, '$.{{ key }}') as double)
    {%- elif dtype == 'timestamp' -%} cast(replace(replace(json_extract_string({{ col }}, '$.{{ key }}'), 'T', ' '), 'Z', '') as timestamp)
    {%- endif -%}
{% endmacro %}

{# Great-circle distance in km x road factor #}
{% macro road_km(lat1, lon1, lat2, lon2) %}
    (2 * 6371.0 * asin(sqrt(
        power(sin(radians({{ lat2 }} - {{ lat1 }}) / 2), 2)
        + cos(radians({{ lat1 }})) * cos(radians({{ lat2 }})) * power(sin(radians({{ lon2 }} - {{ lon1 }}) / 2), 2)
    )) * {{ var('road_factor') }})
{% endmacro %}

{# Quality-value multiplier from remaining life (hours) at arrival #}
{% macro quality_multiplier(rem_hours) %}
    ({{ var('salvage_value_fraction') }} + (1 - {{ var('salvage_value_fraction') }})
      * least(greatest({{ rem_hours }} / {{ var('required_retail_shelf_hours') }}, 0), 1))
{% endmacro %}
