import streamlit as st


def render_header(title: str, subtitle: str, source: str | None = None, synthetic: bool = False) -> None:
    chip = "<span class='source-chip'>NASA OSD-575 · DISCRETE LAB</span>" if source == "NASA_LAB" else "<span class='source-chip gold'>SYNTHETIC SIMULATION</span>" if synthetic else ""
    st.markdown(
        f"<div class='eyebrow'>WEDJAT-X / MISSION SYSTEMS</div><div class='page-title'>{title}</div>"
        f"<div class='page-subtitle'>{subtitle}</div><div style='margin-top:14px'>{chip}</div>",
        unsafe_allow_html=True,
    )
    st.write("")
