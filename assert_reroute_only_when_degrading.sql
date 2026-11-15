-- Business rule: never recommend REROUTE when the original route would arrive at full quality.
select * from {{ ref('mart_arbitrage_recommendations') }}
where recommended_action = 'REROUTE' and (original_quality_multiplier >= 1.0 or best_benefit_usd <= 0)
