select container_id, date_trunc('hour', reading_ts) as hour_ts,
       avg(temperature_c) as avg_temp_c, max(temperature_c) as max_temp_c,
       avg(humidity_pct) as avg_humidity_pct, avg(vibration_g) as avg_vibration_g,
       sum(case when is_excursion then 1 else 0 end) as excursion_readings, count(*) as reading_count
from {{ ref('int_readings_rated') }}
group by container_id, date_trunc('hour', reading_ts)
