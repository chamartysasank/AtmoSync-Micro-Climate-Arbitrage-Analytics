"""AtmoSync supporting web UI (Tableau remains the primary BI dashboard).   streamlit run app/streamlit_app.py
Navigation is built from app/views/*.py (see app/views/__init__.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st

st.set_page_config(page_title="AtmoSync Control Center", layout="wide")

from app.context import get_context          # noqa: E402  (after sys.path / page config)
from app.views import discover               # noqa: E402

ctx = get_context()
views = discover()
st.sidebar.title("AtmoSync")
choice = st.sidebar.radio("Navigation", [v.TITLE for v in views], key="nav")
st.sidebar.caption("Supporting app. Primary BI dashboard: Tableau.")
st.title("AtmoSync — Micro-Climate Arbitrage Control Center (local preview)")
st.caption("Data shown is SIMULATED sample data. Scores and forecasts are transparent heuristics, not validated spoilage predictions.")
next(v for v in views if v.TITLE == choice).render(ctx)
