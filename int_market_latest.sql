select commodity_id, market_id, price_date as latest_price_date, price_modal_usd_kg
from (
    select *, row_number() over (partition by commodity_id, market_id order by price_date desc) as rn
    from {{ ref('stg_market_prices') }}
) t where rn = 1
