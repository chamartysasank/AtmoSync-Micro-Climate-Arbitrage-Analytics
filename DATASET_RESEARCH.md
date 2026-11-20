# Dataset Research Report

**How this was done:** web searches (Kaggle/HuggingFace mirrors, Mendeley Data, arXiv, data.gov.in, UC Davis Postharvest).
**What was NOT possible:** downloading files (sandbox network restrictions), so nothing below was inspected row by row.
**Not researched in this session:** Zenodo, UCI, USDA Market News, GitHub dataset repos. Do not assume they were checked.

## A. Environmental / cold-chain datasets

| # | Dataset | What the source page says | Fits AtmoSync? |
|---|---|---|---|
| A1 | **Time-Temperature Dataset for the Strawberry Cold Chain** — Abdella, Brecht, Uysal. arXiv:2103.12895; *J. Food Engineering* 298:110477 (2021) | 6 strawberry shipments across the continental US; 3 pallets per shipment, 3 vertical loggers each (9 positions: front/middle/rear × top/middle/bottom; 54 measurement points total); readings every 5–10 min; cellular upload. | Best match for **realistic temperature profiles** inside a reefer. Temperature only (no humidity/vibration described). Strawberry, not avocado. Licence, row count, date range: **not verified**. |
| A2 | **Multi-Parameter Dataset for ML Fruit Spoilage Prediction in IoT Cold Storage** — Mendeley Data, DOI 10.17632/czz68d9fwj.1 (published 29 Sep 2025) | 10,996 entries; columns Fruit (e.g. orange, pineapple, banana, tomato), Temp (°C), Humid (%), Light (lux), CO2 (ppm), Class (Good/Bad). Uganda cold-storage project. | Has temp + humidity. **No timestamps or container IDs are described; no avocado listed; "Class" = whether *conditions* are good/bad, not measured spoilage.** Licence: **not verified**. |
| A3 | **Apple cold-storage time series** — *Data in Brief* DOI 10.1016/j.dib.2026.113157; related Mendeley DOI 10.17632/h4sghvyjyt.2 | IoT sensor pairs (Sensirion STS35 fruit-surface temp; SHT45 air temp + RH) in 10–17 bins of a commercial cold room in Ravensburg, Germany; sensor-location and calibration files included. | Best source for **humidity behaviour**; static cold room, not transport; apples. Licence: **not verified**. |

**Gap:** none of these provide avocado + vibration + container/shipment IDs → the Python simulator generates those fields (SIMULATED), using A1/A3-style behaviour as design inspiration only (no data copied).

## B. Commodity price datasets

| # | Dataset | Verified facts | Limitations |
|---|---|---|---|
| B1 | **Hass Avocado Board retail scan data (Kaggle `neuromusic/avocado-prices`)**; HuggingFace mirror `nateraw/avocado-prices` | Licence **ODbL** per the HF dataset card. Originally downloaded from hassavocadoboard.com in May 2018. A write-up reports 14 columns, 18,249 rows, Jan 2015–Mar 2018. Content: date, average price per unit, total volume, PLU 4046/4225/4770 volumes, bag counts, conventional/organic, region. | **Retail** price **per avocado** (not wholesale per kg); no min/max/modal; regions not mapped to cities 1:1. Row/column counts come from a secondary write-up. |
| B1b | Extended 2015–2020 update (Kaggle user alanluo418, downloaded Jan 2020 per Baselight listing; also described by other papers) | Per Baselight listing; arXiv:2104.04649 uses 2015–2020 HAB data | Exact Kaggle URL/licence **not verified**. |
| B2 | **AGMARKNET via data.gov.in** — "Current Daily Price of Various Commodities from Various Markets (Mandi)" | Daily min/max/modal prices per market; generated via the AGMARKNET portal; CEDA README describes 344 commodities, 650+ districts; prices in ₹/quintal. | Licence statements differ by mirror (data.gov.in listing: Open Government Licence – India; a CKAN mirror: Open Data Commons Attribution) → **confirm on data.gov.in**. **Avocado coverage not verified.** Needs a free API key. |

**Choice for the demo:** B1 is the only avocado price source found → `ingestion/hab_prices.py` converts it to the AtmoSync schema using two **assumptions** (5 fruit/kg, wholesale = 60% of retail). Until you run it, `market_prices.csv` is SIMULATED.

## C. Storage-condition literature (used for thresholds)
| Fact | Source |
|---|---|
| Mature-green avocado optimum 5–13 °C (cultivar/duration dependent); ripe fruit 2–4 °C at 90–95% RH; 0–2 °C > 7 days → pitting/scald | UC Davis Postharvest Center (as summarised by postharvest.biz, which cites postharvest.ucdavis.edu/produce-facts-sheets/avocado) |
| Hass best near 7.2 °C (45 °F); storage 2–4 weeks in air; RH 85–90% | WFLO Commodity Storage Manual 2018 (gcca.org) |
| Mature green 41–55 °F, 90–95% RH | Produce Blue Book avocado sheet |
| Deterioration rate rises 2–3× per 10 °C above optimum (general produce, not avocado-specific) | UC ANR Postharvest Technology Center (ucanr.edu .../231724.pdf) |
| Hass at 5 °C in air: 2–4 weeks max, limited by chilling injury/softening | Faubion, Mitchell & Mayer, World Avocado Congress II (1992) |
