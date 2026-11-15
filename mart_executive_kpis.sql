select count(*) as total_containers,
       sum(case when c.risk_category = 'LOW' then 1 else 0 end) as healthy_containers,
       sum(case when c.risk_category in ('MEDIUM', 'HIGH', 'CRITICAL') then 1 else 0 end) as at_risk_containers,
       sum(case when c.risk_category = 'CRITICAL' then 1 else 0 end) as critical_alerts,
       sum(case when r.recommended_action = 'REROUTE' then 1 else 0 end) as arbitrage_opportunities,
       coalesce(sum(case when r.recommended_action = 'REROUTE' then r.best_benefit_usd end), 0) as estimated_benefit_usd
from {{ ref('int_container_status') }} c
join {{ ref('mart_arbitrage_recommendations') }} r on r.container_id = c.container_id
