"""Adapter: Hass Avocado Board retail scan data (Kaggle 'avocado-prices') -> AtmoSync market_prices schema.

IMPORTANT - this converts RETAIL price PER AVOCADO into an approximate WHOLESALE price PER KG using two
ASSUMPTIONS (units_per_kg, wholesale_ratio). The result is DERIVED, not an observed wholesale price.
Column and region names below follow the dataset description on Kaggle/HuggingFace/secondary sources;
open your downloaded CSV and confirm them (see docs/dataset_research/DATASET_RESEARCH.md).
"""
from __future__ import annotations
import pandas as pd

# HAB region label -> AtmoSync market id. Edit after inspecting the real file's `region` values.
REGION_TO_MARKET = {"Chicago": "CHICAGO", "Atlanta": "ATLANTA", "DallasFtWorth": "DALLAS", "Houston": "HOUSTON",
                    "Denver": "DENVER", "PhoenixTucson": "PHOENIX", "LosAngeles": "LOS_ANGELES",
                    "NewYork": "NEW_YORK", "Seattle": "SEATTLE"}


def load_hab_avocado(path: str, units_per_kg: float = 5.0, wholesale_ratio: float = 0.6,
                     avocado_type: str = "conventional", region_map: dict | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    need = {"Date", "AveragePrice", "type", "region"}
    if not need <= set(df.columns):
        raise ValueError(f"Unexpected columns {list(df.columns)}; expected at least {sorted(need)}")
    df = df[df["type"] == avocado_type]
    rmap = region_map or REGION_TO_MARKET
    df = df[df["region"].isin(rmap)].copy()
    kg_price = df["AveragePrice"] * units_per_kg * wholesale_ratio
    return pd.DataFrame({"price_date": pd.to_datetime(df["Date"]).dt.date.astype(str), "market_id": df["region"].map(rmap),
                         "commodity_id": "avocado_hass", "price_min_usd_kg": (kg_price * 0.9).round(2),
                         "price_max_usd_kg": (kg_price * 1.1).round(2), "price_modal_usd_kg": kg_price.round(2),
                         "data_origin": "DERIVED from Hass Avocado Board retail scan data (assumed conversion)"}).reset_index(drop=True)
