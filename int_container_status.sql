-- One row per container: consumed life, recent burn rate, quality window, risk score + category.
with rated as (select * from {{ ref('int_readings_rated') }}),
last_r as (select * from {{ ref('int_container_last_reading') }}),
as_of as (select max(reading_ts) as as_of_ts from rated),
agg as (
    select container_id,
           count(*) as reading_count,
           avg(temperature_c) as avg_temp_c, max(temperature_c) as max_temp_c,
           avg(humidity_pct) as avg_humidity_pct,
           sum(case when temp_excursion then 1 else 0 end) as temp_excursion_count,
           sum(case when rh_excursion then 1 else 0 end) as rh_excursion_count,
           avg(case when is_excursion then 1.0 else 0.0 end) as excursion_share,
           sum(life_consumed_increment) as in_transit_consumed
    from rated group by container_id
),
recent as (
    select r.container_id, avg(r.burn_rate) as recent_burn_rate
    from rated r join last_r l on r.container_id = l.container_id
    where r.reading_ts >= {{ dbt.dateadd('minute', -1 * var('recent_window_minutes'), 'l.last_reading_ts') }}
    group by r.container_id
),
joined as (
    select s.container_id, s.shipment_id, s.commodity_id, s.quantity_kg, s.planned_destination_id,
           a.reading_count, a.avg_temp_c, a.max_temp_c, a.avg_humidity_pct,
           a.temp_excursion_count, a.rh_excursion_count, a.excursion_share,
           least(greatest(s.pre_loading_life_consumed + a.in_transit_consumed, 0), 1) as life_consumed_fraction,
           rc.recent_burn_rate,
           l.last_reading_ts, l.last_latitude, l.last_longitude, ao.as_of_ts,
           {{ road_km('l.last_latitude', 'l.last_longitude', 'd.latitude', 'd.longitude') }} as distance_to_destination_km
    from {{ ref('stg_shipments') }} s
    join agg a on a.container_id = s.container_id
    join recent rc on rc.container_id = s.container_id
    join last_r l on l.container_id = s.container_id
    join {{ ref('stg_locations') }} d on d.location_id = s.planned_destination_id
    cross join as_of ao
),
calc as (
    select *,
        {{ var('base_shelf_life_days') }} * 24.0 * (1 - life_consumed_fraction) as remaining_life_hours,
        distance_to_destination_km / {{ var('avg_speed_kmph') }} as hours_to_destination
    from joined
),
calc2 as (
    select *,
        greatest(remaining_life_hours - {{ var('required_retail_shelf_hours') }}, 0) / greatest(recent_burn_rate, 0.01) as quality_window_hours
    from calc
),
calc3 as (
    select *, quality_window_hours - hours_to_destination as slack_hours from calc2
),
scored as (
    select *,
        100 * ( {{ var('w_burn') }}      * least(greatest((recent_burn_rate - 1) / ({{ var('rate_cap') }} - 1), 0), 1)
              + {{ var('w_margin') }}    * least(greatest(1 - slack_hours / {{ var('slack_scale_hours') }}, 0), 1)
              + {{ var('w_excursion') }} * excursion_share
              + {{ var('w_consumed') }}  * life_consumed_fraction ) as risk_score
    from calc3
)
select *,
    {{ dbt.datediff('last_reading_ts', 'as_of_ts', 'second') }} / 60.0 as minutes_since_last_reading,
    case when slack_hours <= 0 then 'CRITICAL'
         when slack_hours < {{ var('high_slack_hours') }} then 'HIGH'
         when risk_score >= {{ var('medium_score') }} then 'MEDIUM'
         else 'LOW' end as risk_category
from scored
