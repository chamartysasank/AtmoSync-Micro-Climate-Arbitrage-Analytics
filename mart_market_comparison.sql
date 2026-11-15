-- Daily prices with 7-day moving average and premium vs the cross-market average (window functions).
select price_date, market_id, commodity_id, price_modal_usd_kg,
       avg(price_modal_usd_kg) over (partition by market_id, commodity_id order by price_date
            rows between 6 preceding and current row) as modal_7d_avg,
       price_modal_usd_kg - avg(price_modal_usd_kg) over (partition by commodity_id, price_date) as premium_vs_all_markets,
       rank() over (partition by commodity_id, price_date order by price_modal_usd_kg desc) as price_rank
from {{ ref('stg_market_prices') }}
