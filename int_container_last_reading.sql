select container_id, reading_ts as last_reading_ts, latitude as last_latitude, longitude as last_longitude
from (
    select *, row_number() over (partition by container_id order by reading_ts desc) as rn
    from {{ ref('int_readings_rated') }}
) t where rn = 1
