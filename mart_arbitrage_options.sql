-- One row per (container, candidate market): quality-adjusted net value and benefit vs original route.
with opts as (
    select c.container_id, m.market_id, m.price_modal_usd_kg,
           (m.market_id = c.planned_destination_id) as is_original_destination,
           c.quantity_kg, c.remaining_life_hours, c.recent_burn_rate,
           {{ road_km('c.last_latitude', 'c.last_longitude', 'l.latitude', 'l.longitude') }} as distance_km
    from {{ ref('int_container_status') }} c
    join {{ ref('int_market_latest') }} m on m.commodity_id = c.commodity_id
    join {{ ref('stg_locations') }} l on l.location_id = m.market_id
),
t as (
    select *, distance_km / {{ var('avg_speed_kmph') }} as transit_hours from opts
),
v as (
    select *, remaining_life_hours - transit_hours * recent_burn_rate as remaining_life_at_arrival_h from t
),
w as (
    select *, {{ quality_multiplier('remaining_life_at_arrival_h') }} as quality_multiplier,
           price_modal_usd_kg * quantity_kg as expected_gross_value_usd,
           distance_km * quantity_kg / 1000.0 * {{ var('transport_usd_per_tonne_km') }} as transport_cost_usd,
           quantity_kg * {{ var('handling_usd_per_kg') }} as handling_cost_usd,
           case when is_original_destination then 0 else {{ var('reroute_fixed_fee_usd') }} end as reroute_fee_usd
    from v
),
x as (
    select *, expected_gross_value_usd * quality_multiplier as expected_quality_adjusted_value_usd from w
),
y as (
    select *, expected_quality_adjusted_value_usd - transport_cost_usd - handling_cost_usd - reroute_fee_usd as net_value_usd from x
)
select *,
    max(case when is_original_destination then net_value_usd end) over (partition by container_id) as original_net_value_usd,
    net_value_usd - max(case when is_original_destination then net_value_usd end) over (partition by container_id) as benefit_vs_original_usd
from y
