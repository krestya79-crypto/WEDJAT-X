from pathlib import Path
from urllib.parse import quote
import streamlit as st


def render_astronaut(label: str = "CREW MONITOR") -> None:
    asset = Path(__file__).resolve().parents[1] / "assets" / "astronaut.svg"
    svg = asset.read_text(encoding="utf-8")
    st.markdown(f"<div class='card' style='text-align:center;padding:12px 16px 16px'><div class='card-kicker'>{label}</div><img alt='Stylized astronaut illustration' src='data:image/svg+xml;utf8,{quote(svg)}' style='width:min(100%,330px);height:auto;display:block;margin:0 auto'><div class='card-caption'>Monitoring interface · no live human telemetry connected</div></div>", unsafe_allow_html=True)
