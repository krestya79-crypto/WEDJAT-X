import pandas as pd
import streamlit as st


def render_alert_list(alerts: list[dict]) -> None:
    if not alerts:
        st.info("No persisted alert records are available yet.")
        return
    rows = []
    for item in alerts:
        rows.append({
            "State": item.get("alert_state", "Unavailable"),
            "Priority": item.get("alert_priority", "Unavailable"),
            "Signal": item.get("measurement_name", "Unavailable"),
            "Value": item.get("measurement_value"),
            "Time": item.get("timestamp", "Unavailable"),
            "Source": "SYNTHETIC" if item.get("is_synthetic") is True else "NASA LAB",
            "Lifecycle": item.get("lifecycle_status", "Unavailable"),
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    for idx, alert in enumerate(alerts[:12]):
        title = f"{alert.get('alert_state','Alert')} · {alert.get('measurement_name','Observation')} · {alert.get('timestamp','') }"
        with st.expander(title):
            if alert.get("is_synthetic") is True:
                st.markdown("<span class='source-chip gold'>SYNTHETIC TEST SIGNAL</span>", unsafe_allow_html=True)
            st.write(alert.get("explanation") or "No explanation was provided by the analysis result.")
            st.caption("Human review remains authoritative. This display is not a diagnosis or treatment recommendation.")
            evidence = alert.get("supporting_evidence") or []
            conflicts = alert.get("conflicting_evidence") or []
            if evidence: st.markdown("**Supporting evidence**\n" + "\n".join(f"- {x}" for x in evidence))
            if conflicts: st.markdown("**Conflicting evidence**\n" + "\n".join(f"- {x}" for x in conflicts))
            trust = alert.get("sensor_quality_evidence")
            if trust:
                st.markdown("**Sensor reliability context**")
                st.json(trust)
            motion = alert.get("motion_artifact_evidence")
            if motion:
                st.markdown("**Motion-artifact context**")
                st.json(motion)
