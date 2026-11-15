{% if target.type == 'snowflake' %}{{ config(cluster_by=['container_id', 'reading_ts']) }}{% endif %}
-- Parses raw JSON payloads, validates ranges and removes duplicates.
-- Mirrors ingestion/cleaning.py (minus optional imputation, which SQL never does).
with src as (
    select event_id, event_ts, payload from {{ source('raw', 'raw_sensor_events') }}
),
parsed as (
    select
        event_id,
        event_ts,
        {{ json_val('payload', 'container_id', 'varchar') }}   as container_id,
        {{ json_val('payload', 'sensor_id', 'varchar') }}      as sensor_id,
        {{ json_val('payload', 'shipment_id', 'varchar') }}    as shipment_id,
        {{ json_val('payload', 'reading_ts', 'timestamp') }}   as reading_ts,
        nullif(nullif({{ json_val('payload', 'temperature_c', 'double') }}, -999), -9999) as temperature_c,
        nullif(nullif({{ json_val('payload', 'humidity_pct', 'double') }}, -999), -9999)  as humidity_pct,
        {{ json_val('payload', 'vibration_g', 'double') }}     as vibration_g,
        {{ json_val('payload', 'latitude', 'double') }}        as latitude,
        {{ json_val('payload', 'longitude', 'double') }}       as longitude
    from src
),
valid as (
    select * from parsed
    where reading_ts is not null
      and container_id is not null and sensor_id is not null and shipment_id is not null
      and temperature_c between {{ var('valid_temp_min_c') }} and {{ var('valid_temp_max_c') }}
      and humidity_pct  between {{ var('valid_rh_min_pct') }} and {{ var('valid_rh_max_pct') }}
      and (vibration_g is null or vibration_g between 0 and {{ var('valid_vibration_max_g') }})
),
deduped as (
    select *, row_number() over (
        partition by container_id, sensor_id, reading_ts order by event_ts desc, event_id desc) as rn
    from valid
)
select event_id, event_ts, container_id, sensor_id, shipment_id, reading_ts,
       temperature_c, humidity_pct, vibration_g, latitude, longitude
from deduped where rn = 1
