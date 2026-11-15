select cast(price_date as date) as price_date, market_id, commodity_id,
       price_min_usd_kg, price_max_usd_kg, price_modal_usd_kg, data_origin
from {{ source('raw', 'raw_market_prices') }}
