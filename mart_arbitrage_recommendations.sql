-- One row per container with the best alternative market and the recommended action.
-- Rule: REROUTE only if the best quality-adjusted benefit clears the threshold AND the original
-- route would degrade the fruit (quality multiplier < 1). A higher price alone never triggers it.
with ranked as (
    select *, row_number() over (partition by container_id order by benefit_vs_original_usd desc, market_id asc) as rn
    from {{ ref('mart_arbitrage_options') }} where not is_original_destination
),
best as (select * from ranked where rn = 1),
orig as (select * from {{ ref('mart_arbitrage_options') }} where is_original_destination)
select c.container_id, c.shipment_id, c.risk_category,
       o.market_id as original_destination, o.quality_multiplier as original_quality_multiplier,
       o.net_value_usd as original_net_value_usd,
       b.market_id as best_alternative, b.net_value_usd as best_alt_net_value_usd,
       b.benefit_vs_original_usd as best_benefit_usd,
       greatest({{ var('min_benefit_usd') }}, {{ var('min_benefit_pct') }} * abs(o.net_value_usd)) as benefit_threshold_usd,
       case when b.benefit_vs_original_usd >= greatest({{ var('min_benefit_usd') }}, {{ var('min_benefit_pct') }} * abs(o.net_value_usd))
                 and o.quality_multiplier < 1.0 then 'REROUTE'
            when c.risk_category in ('MEDIUM', 'HIGH', 'CRITICAL') then 'MONITOR'
            else 'NO_ACTION' end as recommended_action
from {{ ref('int_container_status') }} c
join orig o on o.container_id = c.container_id
join best b on b.container_id = c.container_id
