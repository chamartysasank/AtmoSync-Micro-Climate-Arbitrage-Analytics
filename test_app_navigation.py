"""Every registered Streamlit view must render without exceptions (guards against broken navigation)."""
import pytest
from streamlit.testing.v1 import AppTest
from common.config import ROOT


def _titles():
    from app.views import discover
    return [v.TITLE for v in discover()]


def test_registry_has_unique_titles_and_orders():
    from app.views import discover
    vs = discover()
    assert len({v.TITLE for v in vs}) == len(vs) and len({v.ORDER for v in vs}) == len(vs)
    assert [v.TITLE for v in vs][:2] == ["Overview", "Shipment Monitoring"]


@pytest.mark.parametrize("title", _titles())
def test_each_view_renders(title):
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    assert not at.exception
    at.sidebar.radio[0].set_value(title).run()
    assert not at.exception, f"{title}: {[e.value for e in at.exception]}"
