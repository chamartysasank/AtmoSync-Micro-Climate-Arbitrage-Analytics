"""Shared, cached data for all Streamlit views (Phase 2). Views never recompute the base pipeline themselves."""
from __future__ import annotations
import streamlit as st
from analytics.pipeline import run_pipeline
from common.config import load_settings


@st.cache_data(show_spinner="Running AtmoSync pipeline...")
def get_results() -> dict:
    return run_pipeline(load_settings())


def get_context() -> dict:
    return {"cfg": load_settings(), "r": get_results()}
