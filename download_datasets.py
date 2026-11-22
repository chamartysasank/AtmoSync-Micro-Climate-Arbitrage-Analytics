"""Prints (and optionally runs) the steps to fetch the REAL datasets. Datasets are NOT bundled in the ZIP.
  python scripts/download_datasets.py            # show instructions
  python scripts/download_datasets.py --kaggle   # needs `pip install kaggle` + ~/.kaggle/kaggle.json
Always re-verify each dataset's license on its page before redistribution."""
import subprocess, sys
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
TEXT = f"""
1) Hass Avocado Board retail prices (Kaggle mirror, license ODbL per HuggingFace card)
   https://www.kaggle.com/datasets/neuromusic/avocado-prices          (Jan 2015 - Mar 2018)
   An extended 2015-2020 update exists (Kaggle user alanluo418, 'The Price And Sales Of Avocado') - search Kaggle for it; exact URL NOT verified.
   Original source: https://hassavocadoboard.com/ (retail volume and price data)
   Save as: {RAW / 'avocado.csv'}  then use ingestion/hab_prices.py

2) Strawberry cold-chain time-temperature dataset (Abdella, Brecht, Uysal; J. Food Eng. 298:110477, 2021)
   https://arxiv.org/abs/2103.12895   - follow the data-availability statement in the paper for the files.
3) Fruit spoilage IoT cold-storage dataset (Mendeley Data, DOI 10.17632/czz68d9fwj.1) - 10,996 rows per the dataset page.
4) Apple cold-storage temperature/humidity time series (Mendeley DOI 10.17632/h4sghvyjyt.2).
5) India AGMARKNET daily mandi prices (min/max/modal) via https://data.gov.in (needs a free API key).
"""
if __name__ == "__main__":
    print(TEXT)
    if "--kaggle" in sys.argv:
        RAW.mkdir(parents=True, exist_ok=True)
        subprocess.run(["kaggle", "datasets", "download", "-d", "neuromusic/avocado-prices", "-p", str(RAW), "--unzip"], check=True)
