import pandas as pd
import streamlit as st
from frontend.components.metrics import metric_card, percent_value, safe_value


def sensor_map(trust: dict | None) -> dict:
    if not trust:
        return {}
    sensors = trust.get("sensors")
    if isinstance(sensors, dict):
        return sensors
    sensor = trust.get("sensor_type")
    return {sensor or "sensor": trust}


def render_sensor_trust(trust: dict | None) -> None:
    sensors = sensor_map(trust)
    if not sensors:
        st.info("No persisted sensor-trust evaluation is available. Run a synthetic wearable analysis.")
        return
    selected = st.selectbox("Sensor stream", list(sensors), key="trust_sensor_select")
    record = sensors[selected]
    a,b,c,d=st.columns(4)
    with a: metric_card("QUALITY SCORE", safe_value(record.get("quality_score"), "/100"), "Signal integrity estimate")
    with b: metric_card("RELIABILITY", str(record.get("reliability_category", "Unavailable")).replace("_", " "), "Trust category")
    with c: metric_card("MISSING SAMPLES", safe_value(record.get("missing_sample_count"), digits=0), f"Missing rate {percent_value(record.get('missing_rate'))}")
    with d: metric_card("DISCONNECTION", percent_value(record.get("disconnection_rate")), "Detected stream loss")
    details = {
        "Noise metric": record.get("noise_metric"), "Spike count": record.get("spike_count"),
        "Drift detected": record.get("drift_detected"), "Timestamp gaps": record.get("timestamp_gap_count"),
        "Motion overlap": record.get("motion_overlap_pct"), "Valid samples": record.get("valid_sample_count"),
    }
    st.markdown("<div class='section-label'>Signal quality detail</div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([{"Measure": k, "Observed": "Unavailable" if v is None else v} for k,v in details.items()]), hide_index=True, width="stretch")
    if record.get("explanation"):
        st.caption(record["explanation"])
