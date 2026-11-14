import pandas as pd
import streamlit as st


def render_trajectory_summary(trajectory: dict | None, biomarker: str | None = None) -> None:
    if not trajectory:
        st.info("Run a NASA OSD-575 analysis to view descriptive trajectory summaries.")
        return
    entries = trajectory
    if biomarker and biomarker in trajectory:
        entries = {biomarker: trajectory[biomarker]}
    rows=[]
    for name, item in entries.items():
        rows.append({"Biomarker":name,"Recovery class":item.get("recovery_class","Unavailable"),
                     "Overall trend":item.get("overall_trend","Unavailable"),
                     "Baseline median":item.get("preflight_baseline_median"),
                     "Explanation":item.get("trajectory_explanation","Unavailable")})
    if rows:
        st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
    st.caption("Descriptive retrospective assay trajectories only. The four-person cohort does not support clinical or population-level generalization.")
