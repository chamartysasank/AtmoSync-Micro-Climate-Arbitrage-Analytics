{% if target.type == 'snowflake' %}{{ config(materialized='table', cluster_by=['container_id', 'reading_ts']) }}{% endif %}
-- Per-reading shelf-life burn rate (transparent heuristic; see docs/methodology/methodology.md)
with base as (
    select *, lag(reading_ts) over (partition by container_id order by reading_ts) as prev_ts
    from {{ ref('stg_sensor_events') }}
),
calc as (
    select *,
        least(coalesce({{ dbt.datediff('prev_ts', 'reading_ts', 'second') }}, 0) / 3600.0, {{ var('max_gap_hours') }}) as dt_hours,
        (temperature_c < {{ var('temp_min_c') }} or temperature_c > {{ var('temp_max_c') }}) as temp_excursion,
        (humidity_pct  < {{ var('rh_min_pct') }}  or humidity_pct  > {{ var('rh_max_pct') }}) as rh_excursion,
        power({{ var('q10') }}, (greatest(temperature_c, {{ var('chill_floor_c') }}) - {{ var('reference_temp_c') }}) / 10.0)
          * (1 + {{ var('rh_penalty_per_10pct') }} * greatest({{ var('rh_min_pct') }} - humidity_pct, 0) / 10.0) as burn_rate
    from base
)
select *,
    (temp_excursion or rh_excursion) as is_excursion,
    dt_hours * burn_rate / ({{ var('base_shelf_life_days') }} * 24.0) as life_consumed_increment
from calc
