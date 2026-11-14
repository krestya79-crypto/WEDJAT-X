from pathlib import Path
import streamlit as st

PAGES = ["Mission Overview", "Astronaut Monitoring", "Analysis Console", "Live Telemetry",
         "NASA Biomarkers", "Alert Center", "Sensor Trust", "Recovery Trajectory"]


def render_sidebar() -> tuple[str, str]:
    with st.sidebar:
        st.markdown("<div class='brand'><div class='brand-mark'>W</div><div><div class='brand-name'>WEDJAT-X</div><div class='brand-tag'>FLIGHT HEALTH SYSTEMS</div></div></div>", unsafe_allow_html=True)
        st.markdown("<div class='section-label'>Mission navigation</div>", unsafe_allow_html=True)
        page = st.radio("Dashboard section", PAGES, label_visibility="collapsed")
        st.markdown("<div class='section-label' style='margin-top:24px'>Analysis source</div>", unsafe_allow_html=True)
        source = st.selectbox("Select a data path", ["NASA_LAB", "SYNTHETIC_WEARABLE"],
                              format_func=lambda v: "NASA OSD-575 · discrete lab" if v == "NASA_LAB" else "Synthetic wearable · simulated")
        if source == "SYNTHETIC_WEARABLE":
            st.markdown("<div class='callout'><b>SYNTHETIC ONLY</b><br>These scenarios are software test data, not astronaut telemetry.</div>", unsafe_allow_html=True)
        else:
            st.caption("Discrete laboratory assay milestones. Not continuous telemetry.")
        st.markdown("<hr>", unsafe_allow_html=True)
        if st.button("↻  Refresh mission data", width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("<div style='margin-top:16px;font:9px DM Mono,monospace;color:#687f92'>OFFLINE MODE · LOCAL SQLITE<br>HUMAN REVIEW IS AUTHORITATIVE</div>", unsafe_allow_html=True)
    return page, source
