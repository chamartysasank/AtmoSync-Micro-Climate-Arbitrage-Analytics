-- Shipment-level risk ranking (adds shipment route info to the container status)
select rank() over (order by c.risk_score desc) as risk_rank,
       c.shipment_id, c.container_id, s.origin_id, c.planned_destination_id, s.planned_arrival_ts,
       c.risk_score, c.risk_category, c.life_consumed_fraction, c.remaining_life_hours,
       c.quality_window_hours, c.hours_to_destination, c.slack_hours, c.recent_burn_rate
from {{ ref('int_container_status') }} c
join {{ ref('stg_shipments') }} s on s.shipment_id = c.shipment_id
