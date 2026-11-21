"""Data Quality page (Feature 7)."""
import streamlit as st
from ingestion.quality import assess_quality, save_quality_summary
from common.store import Store

TITLE, ORDER = "Data Quality", 90


def render(ctx):
    rep = ctx["r"]["quality"]; s = rep.summary
    st.caption("Scores combine completeness, validity (the pipeline's own cleaning rules), uniqueness and timeliness (config/features/quality.yaml).")
    cols = st.columns(5)
    cols[0].metric("Overall", f"{s['overall_score']:.1f}", s["status"], delta_color="off")
    for col, k in zip(cols[1:], ("completeness", "validity", "uniqueness", "timeliness")):
        col.metric(k.capitalize(), f"{s[k + '_score']:.1f}")
    c = st.columns(5)
    for col, (lab, key) in zip(c, [("Missing values", "missing_values"), ("Invalid readings", "invalid_readings"), ("Out of range", "out_of_range"), ("Duplicates", "duplicates"), ("Missing readings", "missing_readings")]):
        col.metric(lab, s[key])
    sev = st.multiselect("Finding severity", ["CRITICAL", "WARNING", "INFO"], default=["CRITICAL", "WARNING", "INFO"], key="dq_sev")
    st.subheader("Findings"); st.dataframe(rep.issues[rep.issues["severity"].isin(sev)], use_container_width=True)
    st.subheader("By container (lowest score first)")
    ids = st.multiselect("Containers", sorted(rep.by_container["container_id"]), key="dq_ids")
    bc = rep.by_container[rep.by_container["container_id"].isin(ids)] if ids else rep.by_container
    st.dataframe(bc.round({c: 1 for c in bc.select_dtypes("number").columns}), use_container_width=True)
    st.bar_chart(bc.set_index("container_id")["score"])
    st.subheader("By field"); st.dataframe(rep.by_field.round(2), use_container_width=True)
    st.download_button("Download report (Markdown)", rep.to_markdown(), "data_quality_report.md", "text/markdown")
    st.download_button("Download by-container table (CSV)", rep.by_container.to_csv(index=False), "quality_by_container.csv", "text/csv")
    if st.button("Save summary to quality history", key="dq_save"):
        st.success(f"{save_quality_summary(rep)} row stored in ops.dq_reports")
    h = Store().read_table("dq_reports")
    if not h.empty:
        st.subheader("Stored history"); st.line_chart(h.set_index("run_ts")[["overall_score", "completeness_score", "validity_score"]])
