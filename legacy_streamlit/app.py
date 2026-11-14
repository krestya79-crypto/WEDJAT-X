"""Streamlit mission-control frontend backed by application.service."""
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from application.exceptions import WedjatXError
from application.service import (
    analyze_nasa_sample,
    analyze_wearable_stream,
    get_analysis_history,
    get_latest_analysis,
    get_recent_alerts,
    get_system_status,
)
from legacy_streamlit.components.alerts import render_alert_list
from legacy_streamlit.components.astronaut import render_astronaut
from legacy_streamlit.components.biomarkers import render_biomarker_chart
from legacy_streamlit.components.header import render_header
from legacy_streamlit.components.metrics import metric_card, safe_value
from legacy_streamlit.components.sensor_trust import render_sensor_trust, sensor_map
from legacy_streamlit.components.sidebar import render_sidebar
from legacy_streamlit.components.telemetry import render_telemetry_chart
from legacy_streamlit.components.trajectory import render_trajectory_summary

ROOT = Path(__file__).resolve().parents[1]
NASA_PATH = ROOT / "cleaned_data" / "WEDJAT_X_Master_Biomarker_Dataset.csv"
SCENARIO_DIR = ROOT / "synthetic_data"
SCENARIOS = sorted(path.name for path in SCENARIO_DIR.glob("*_scenario.csv"))


@st.cache_data(show_spinner=False)
def load_nasa_data() -> pd.DataFrame:
    if not NASA_PATH.exists():
        raise FileNotFoundError(f"Audited NASA dataset is not available: {NASA_PATH.name}")
    return pd.read_csv(NASA_PATH)


@st.cache_data(show_spinner=False)
def load_scenario(name: str) -> pd.DataFrame:
    path = SCENARIO_DIR / name
    if path.parent.resolve() != SCENARIO_DIR.resolve() or not path.is_file():
        raise FileNotFoundError("Selected local synthetic scenario was not found.")
    return pd.read_csv(path)


@st.cache_data(ttl=8, show_spinner=False)
def load_history(limit: int = 50) -> list[dict]:
    return get_analysis_history(limit)


@st.cache_data(ttl=8, show_spinner=False)
def load_alerts(limit: int = 50) -> list[dict]:
    return get_recent_alerts(limit)


def as_dict(result: Any) -> dict:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    if isinstance(result, dict):
        return result
    raise TypeError(f"Unexpected analysis result type: {type(result).__name__}")


def show_analysis_error(exc: Exception) -> None:
    if isinstance(exc, WedjatXError):
        st.error(f"Input or routing issue: {exc}")
    elif isinstance(exc, (FileNotFoundError, ValueError, TypeError)):
        st.error(str(exc))
    else:
        st.error(f"Analysis did not complete: {exc}")
    st.caption("No normal state is inferred from a failed request. Check the source data and retry.")


def analyze_nasa(participant: str) -> dict | None:
    try:
        df = load_nasa_data()
        with st.spinner("Evaluating discrete OSD-575 laboratory observations…"):
            result = analyze_nasa_sample(df, metadata={"astronaut_id": participant, "source_file": NASA_PATH.name})
        payload = as_dict(result)
        st.session_state["wedjat_latest_nasa"] = payload
        st.cache_data.clear()
        return payload
    except Exception as exc:  # validation failures intentionally surface as exceptions in the backend API
        show_analysis_error(exc)
        return None


def analyze_synthetic(df: pd.DataFrame, scenario_name: str) -> dict | None:
    try:
        with st.spinner("Processing explicitly synthetic sensor scenarios…"):
            result = analyze_wearable_stream(df, metadata={"scenario": scenario_name, "source_label": "SYNTHETIC"})
        payload = as_dict(result)
        st.session_state["wedjat_latest_wearable"] = payload
        st.cache_data.clear()
        return payload
    except Exception as exc:
        show_analysis_error(exc)
        return None


def get_latest() -> dict | None:
    try:
        return get_latest_analysis()
    except Exception as exc:
        st.error(f"Local analysis history is unavailable: {exc}")
        return None


def result_alert(result: dict | None) -> dict:
    if not result:
        return {}
    return result.get("alert") or result.get("alert_summary") or {}


def latest_result_for_source(history: list[dict], source: str) -> dict | None:
    return next((item for item in history if item.get("source_type") == source), None)


def display_history(history: list[dict]) -> None:
    if not history:
        st.info("No analysis sessions are stored yet. Use Analysis Console to run an analysis.")
        return
    rows = [{
        "Processed": item.get("timestamp", "Unavailable"),
        "Source": "SYNTHETIC WEARABLE" if item.get("is_synthetic") else "NASA LAB",
        "Subject": item.get("astronaut_id") or item.get("subject_id") or "—",
        "Status": item.get("processing_status", "Unavailable"),
        "Request": item.get("request_id", "—"),
    } for item in history]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    ids = [item.get("request_id", "") for item in history]
    selected = st.selectbox("Open saved result", ids, key="history_result_select")
    record = next((item for item in history if item.get("request_id") == selected), None)
    if record:
        with st.expander("Selected result evidence", expanded=False):
            st.json({k: record.get(k) for k in ("data_summary", "baseline_summary", "anomaly_evidence", "sensor_trust", "trajectory_summary", "alert", "warnings", "errors")})


def page_overview() -> None:
    render_header("Mission overview", "A live summary of the local decision-support system, persisted analysis activity, and current evidence.")
    try:
        status = get_system_status()
        history = load_history(20)
        alerts = load_alerts(20)
    except Exception as exc:
        st.error(f"Could not load local mission status: {exc}")
        return
    latest = get_latest()
    sensor_result = latest_result_for_source(history, "SYNTHETIC_WEARABLE")
    trust = (sensor_result or {}).get("sensor_trust")
    trust_entries = sensor_map(trust)
    trust_scores = [entry.get("quality_score") for entry in trust_entries.values() if entry.get("quality_score") is not None]
    trust_text = safe_value(sum(trust_scores)/len(trust_scores), "/100") if trust_scores else "Unavailable"
    alert_summary = result_alert(latest)
    c1,c2,c3,c4 = st.columns(4)
    with c1: metric_card("SYSTEM STATUS", status.get("status", "Unavailable"), "Local analytics engines")
    with c2: metric_card("SAVED ANALYSES", str(len(history)), "Recent persisted sessions")
    with c3: metric_card("ALERTS · LATEST RESULT", safe_value(alert_summary.get("active_alert_count"), digits=0), f"{len(alerts)} recent persisted evidence records")
    with c4: metric_card("LATEST SENSOR TRUST", trust_text, "Most recent synthetic stream")
    st.write("")
    left,right=st.columns([1.4,1])
    with left:
        st.markdown("<div class='section-label'>Latest processing session</div>", unsafe_allow_html=True)
        if latest:
            source = "SYNTHETIC WEARABLE" if latest.get("is_synthetic") else "NASA OSD-575 LAB"
            st.markdown(f"<div class='card'><div class='card-kicker'>{source}</div><div class='card-value' style='font-size:20px'>{latest.get('processing_status','Unavailable')}</div><div class='card-caption'>Request {latest.get('request_id','—')} · {latest.get('timestamp','Unavailable')}</div><div class='card-caption'>Operational state: {alert_summary.get('highest_operational_state','Unavailable')} · Subject: {latest.get('astronaut_id') or latest.get('subject_id') or '—'}</div></div>", unsafe_allow_html=True)
        else:
            st.info("No analysis history yet. Select a source in the sidebar and open Analysis Console.")
        st.markdown("<div class='section-label'>Recent analysis history</div>", unsafe_allow_html=True)
        display_history(history[:8])
    with right:
        render_astronaut("CREW SYSTEM OVERVIEW")
        st.markdown("<div class='callout' style='margin-top:12px'>NASA OSD-575 is discrete laboratory evidence. Wearable charts and sensor reliability are synthetic simulations only.</div>", unsafe_allow_html=True)


def page_astronaut() -> None:
    render_header("Astronaut monitoring", "A clear status panel for the latest analysis. Vitals remain unavailable unless an analyzed wearable stream supplies them.")
    latest=get_latest()
    left,right=st.columns([.95,1.4],gap="large")
    with left: render_astronaut("ASTRONAUT SYSTEM VISUAL")
    with right:
        if not latest:
            st.info("No saved analysis is available. Run an analysis from the console.")
            return
        synthetic=latest.get("is_synthetic") is True
        if synthetic:
            st.markdown("<span class='source-chip gold'>SYNTHETIC WEARABLE SAMPLE</span>",unsafe_allow_html=True)
        else:
            st.markdown("<span class='source-chip'>NASA OSD-575 DISCRETE LAB DATA</span>",unsafe_allow_html=True)
        st.write("")
        measurements=latest.get("measurements",[])
        def last_sensor(sensor):
            values=[m for m in measurements if m.get("sensor_type")==sensor and m.get("signal_value") is not None]
            return values[-1].get("signal_value") if values else None
        hr=last_sensor("heart_rate") if synthetic else None
        spo2=last_sensor("spo2") if synthetic else None
        accel=last_sensor("accelerometer") if synthetic else None
        trust=latest.get("sensor_trust") if synthetic else None
        trust_entries=sensor_map(trust)
        reliability=next(iter(trust_entries.values()),{}).get("reliability_category")
        cols=st.columns(2)
        with cols[0]: metric_card("HEART RATE · SAMPLE",safe_value(hr," bpm"),"Stored result preview; unavailable for NASA lab records")
        with cols[1]: metric_card("SpO₂ · SAMPLE",safe_value(spo2,"%"),"Stored result preview; unavailable for NASA lab records")
        cols=st.columns(2)
        with cols[0]: metric_card("ACTIVITY SENSOR", "Available" if accel is not None else "Unavailable", "Accelerometer sample observed; no activity score invented" if accel is not None else "No activity estimate fabricated")
        with cols[1]: metric_card("SIGNAL RELIABILITY",str(reliability or "Unavailable").replace("_"," "),"From stored sensor-trust result")
        st.markdown(f"<div class='card' style='margin-top:12px'><div class='card-kicker'>LATEST RESULT</div><div class='card-caption'>Source: {latest.get('source_type','Unavailable')} · Status: {latest.get('processing_status','Unavailable')} · ID: {latest.get('astronaut_id') or latest.get('subject_id') or '—'}</div></div>",unsafe_allow_html=True)


def page_console(default_source: str) -> None:
    render_header("Analysis console", "Run one deliberate analysis request against a repository-backed source. Analysis runs only when you press the button.")
    source=st.radio("Data source",["NASA_LAB","SYNTHETIC_WEARABLE"],index=0 if default_source=="NASA_LAB" else 1,
                    format_func=lambda v: "NASA OSD-575 · discrete lab" if v=="NASA_LAB" else "Synthetic wearable · simulation",horizontal=True)
    if source=="NASA_LAB":
        st.markdown("<div class='callout'>The selected source is the audited OSD-575 master dataset. It contains discrete venipuncture assay milestones, not continuous astronaut telemetry.</div>",unsafe_allow_html=True)
        try:
            df=load_nasa_data()
            participants=sorted(df.Participant_ID.dropna().astype(str).unique().tolist())
        except Exception as exc:
            show_analysis_error(exc); return
        participant=st.selectbox("Astronaut / participant",participants,key="console_nasa_participant")
        st.caption(f"{len(df):,} actual dataset rows · {df.Biomarker_Name.nunique():,} biomarkers · source file {NASA_PATH.name}")
        if st.button("Analyze selected NASA participant",type="primary",key="console_run_nasa"):
            result=analyze_nasa(participant)
            if result: st.success(f"Completed {result['request_id']} · {result['processing_status']}")
    else:
        st.markdown("<div class='callout'><b>SYNTHETIC SIMULATION ONLY.</b> These local scenario files are generated test data and do not represent NASA astronaut telemetry.</div>",unsafe_allow_html=True)
        if not SCENARIOS:
            st.error("No local synthetic scenario CSV files are available."); return
        choice=st.selectbox("Local synthetic scenario",SCENARIOS,key="console_synth_scenario")
        uploaded=st.file_uploader("Optional synthetic CSV",type=["csv"],key="console_synth_upload")
        try:
            frame=pd.read_csv(uploaded) if uploaded else load_scenario(choice)
            st.caption(f"{len(frame):,} rows · scenarios are routed with synthetic provenance")
            render_telemetry_chart(frame,title="SYNTHETIC · selected input stream")
        except Exception as exc:
            show_analysis_error(exc); return
        if st.button("Analyze synthetic stream",type="primary",key="console_run_synth"):
            result=analyze_synthetic(frame,uploaded.name if uploaded else choice)
            if result: st.success(f"Completed {result['request_id']} · {result['processing_status']} · is_synthetic={result['is_synthetic']}")
    st.markdown("<div class='section-label'>Latest saved analysis</div>",unsafe_allow_html=True)
    latest=get_latest()
    if latest:
        st.json({k:latest.get(k) for k in ("request_id","source_type","is_synthetic","processing_status","data_summary","baseline_summary","anomaly_evidence","sensor_trust","trajectory_summary","alert","warnings","errors")})


def page_telemetry() -> None:
    render_header("Live telemetry", "Inspect a local sensor scenario and its sampled time series. This panel is synthetic test telemetry only.",synthetic=True)
    st.markdown("<div class='callout'><b>SYNTHETIC — NOT NASA TELEMETRY.</b> Every local scenario is marked synthetic. Missing readings are shown as gaps and never connected through.</div>",unsafe_allow_html=True)
    if not SCENARIOS:
        st.warning("No local synthetic scenario files are available."); return
    col1,col2=st.columns([1,2])
    with col1: choice=st.selectbox("Scenario",SCENARIOS,key="telemetry_scenario")
    with col2: uploaded=st.file_uploader("Or upload a synthetic CSV with timestamp, sensor_type and signal_value",type=["csv"],key="telemetry_upload")
    try:
        frame=pd.read_csv(uploaded) if uploaded else load_scenario(choice)
    except Exception as exc:
        show_analysis_error(exc); return
    if "is_synthetic" in frame and not frame["is_synthetic"].fillna(False).all():
        st.error("Upload contains rows without is_synthetic=True. The backend will reject contradictory provenance."); return
    render_telemetry_chart(frame,f"SYNTHETIC · {uploaded.name if uploaded else choice}")
    a,b,c=st.columns(3)
    with a: metric_card("SAMPLES",f"{len(frame):,}","Uploaded or local simulation")
    with b: metric_card("SENSOR TYPES",str(frame.sensor_type.nunique()) if "sensor_type" in frame else "Unavailable","No sensor value is inferred")
    with c: metric_card("MISSING VALUES",str(frame.signal_value.isna().sum()) if "signal_value" in frame else "Unavailable","Shown as gaps")
    if st.button("Analyze this synthetic scenario",type="primary",key="telemetry_run"):
        result=analyze_synthetic(frame,uploaded.name if uploaded else choice)
        if result: st.success(f"Analysis {result['processing_status']} · explicitly synthetic")
    latest=st.session_state.get("wedjat_latest_wearable") or latest_result_for_source(load_history(20),"SYNTHETIC_WEARABLE")
    if latest:
        state=result_alert(latest).get("highest_operational_state","Unavailable")
        trust=latest.get("sensor_trust") or {}
        sensors=sensor_map(trust)
        reliability=", ".join(str(x.get("reliability_category","Unavailable")).replace("_"," ") for x in sensors.values()) or "Unavailable"
        gaps=[x.get("disconnection_rate") for x in sensors.values() if x.get("disconnection_rate") is not None]
        gap_rate=(sum(gaps)/len(gaps))*100 if gaps else None
        x,y,z=st.columns(3)
        with x: metric_card("DISCONNECTION RATE",safe_value(gap_rate,"%"),"From sensor-trust evaluation")
        with y: metric_card("ALERT STATE",str(state),"Backend assessment · not a medical status")
        with z: metric_card("SENSOR RELIABILITY",reliability,"From latest persisted wearable analysis")
        alert_records=latest.get("alert",{}).get("active_alerts",[])
        motion=sum(bool(item.get("motion_artifact_evidence",{}).get("motion_correlated")) for item in alert_records)
        st.caption(f"Motion-correlated samples flagged by alert evidence: {motion} · sensor disconnect and timestamp-gap evidence is available in Sensor Trust.")


def page_biomarkers() -> None:
    render_header("NASA biomarker analysis", "Explore actual OSD-575 measurements across the seven mission milestones. These are discrete laboratory assays.",source="NASA_LAB")
    st.markdown("<div class='callout'>NASA OSD-575 data is retrospective laboratory evidence for four Inspiration4 participants. It is not continuous wearable telemetry and does not support clinical or population-level generalization.</div>",unsafe_allow_html=True)
    try:
        df=load_nasa_data(); participants=sorted(df.Participant_ID.dropna().astype(str).unique().tolist())
    except Exception as exc:
        show_analysis_error(exc); return
    left,right=st.columns(2)
    with left: participant=st.selectbox("Participant",participants,key="biomarker_participant")
    participant_data=df[df.Participant_ID.astype(str)==participant]
    biomarkers=sorted(participant_data.Biomarker_Name.dropna().astype(str).unique().tolist())
    with right: biomarker=st.selectbox("Biomarker",biomarkers,key="biomarker_name")
    if st.button("Run NASA analysis for this participant",type="primary",key="biomarker_run"):
        result=analyze_nasa(participant)
        if result: st.success(f"Actual source data analyzed · {result['processing_status']}")
    result=st.session_state.get("wedjat_latest_nasa")
    if not result or result.get("astronaut_id")!=participant:
        result=next((x for x in load_history(50) if x.get("source_type")=="NASA_LAB" and (x.get("astronaut_id") or x.get("subject_id"))==participant),None)
    baseline=(result or {}).get("baseline_summary",{}).get(biomarker,{})
    one,two,three=st.columns(3)
    with one: metric_card("PREFLIGHT BASELINE MEDIAN",safe_value(baseline.get("baseline_median")),str(baseline.get("preflight_sample_count","—"))+" preflight samples")
    with two: metric_card("BASELINE MAD",safe_value(baseline.get("baseline_mad")),"Robust dispersion measure")
    trajectory=(result or {}).get("trajectory_summary",{}).get(biomarker,{})
    with three: metric_card("DESCRIPTIVE TRAJECTORY",str(trajectory.get("recovery_class","Run analysis" )).replace("_"," "),trajectory.get("overall_trend","Longitudinal context"))
    render_biomarker_chart(participant_data,biomarker,baseline)
    if result:
        evidence=[(key,value) for key,value in (result.get("anomaly_evidence",{}).get("statistical",{}) or {}).items() if value.get("biomarker_name")==biomarker]
        if evidence:
            st.markdown("<div class='section-label'>Backend statistical evidence</div>",unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([{"Milestone":v.get("timepoint"),"Measured value":v.get("measurement_value"),"Robust z":v.get("robust_z"),"Anomaly":v.get("is_anomaly"),"Explanation":v.get("explanation")} for _,v in evidence]),width="stretch",hide_index=True)
        render_trajectory_summary((result.get("trajectory_summary") or {}),biomarker)
    else:
        st.info("Run analysis to display backend baseline, anomaly and trajectory evidence. The chart above shows only actual source measurements.")


def page_alerts() -> None:
    render_header("Intelligent alert center", "Review explainable operational evidence and lifecycle context. Alerts support human review; they do not diagnose or prescribe.")
    alerts=load_alerts(100)
    if alerts:
        source=st.selectbox("Filter source",["All sources","NASA LAB","SYNTHETIC WEARABLE"])
        if source=="NASA LAB": alerts=[x for x in alerts if x.get("is_synthetic") is False]
        elif source=="SYNTHETIC WEARABLE": alerts=[x for x in alerts if x.get("is_synthetic") is True]
        states=sorted({str(x.get("alert_state","Unavailable")) for x in alerts})
        if states:
            selected=st.multiselect("Filter state",states,default=states)
            alerts=[x for x in alerts if x.get("alert_state") in selected]
    render_alert_list(alerts)
    st.markdown("<div class='callout'>All evidence requires authorized human review. No diagnosis or treatment recommendation is produced by this interface.</div>",unsafe_allow_html=True)


def page_sensor_trust() -> None:
    render_header("Sensor trust", "Inspect continuity, missingness, noise, drift, disconnection, and motion context for a stored synthetic stream.",synthetic=True)
    st.markdown("<div class='callout'><b>SYNTHETIC TELEMETRY ONLY.</b> Trust scores describe test-signal quality and are not confidence in an astronaut’s medical state.</div>",unsafe_allow_html=True)
    result=latest_result_for_source(load_history(50),"SYNTHETIC_WEARABLE")
    if result:
        st.caption(f"Latest stored stream: {result.get('timestamp','Unavailable')} · {result.get('request_id','—')}")
    render_sensor_trust(result.get("sensor_trust") if result else None)


def page_trajectory() -> None:
    render_header("Recovery trajectory", "Descriptive biomarker trends at actual OSD-575 collection milestones, with the personal preflight median as reference.",source="NASA_LAB")
    st.markdown("<div class='callout'>Milestones are discrete biospecimen collection times. Lines connect observed sample points only; missing measurements remain gaps.</div>",unsafe_allow_html=True)
    try:
        df=load_nasa_data(); participants=sorted(df.Participant_ID.dropna().astype(str).unique().tolist())
    except Exception as exc:
        show_analysis_error(exc); return
    a,b=st.columns(2)
    with a: participant=st.selectbox("Participant",participants,key="trajectory_participant")
    subset=df[df.Participant_ID.astype(str)==participant]
    biomarkers=sorted(subset.Biomarker_Name.dropna().astype(str).unique().tolist())
    with b: biomarker=st.selectbox("Biomarker",biomarkers,key="trajectory_biomarker")
    result=st.session_state.get("wedjat_latest_nasa")
    if not result or result.get("astronaut_id")!=participant:
        result=next((x for x in load_history(50) if x.get("source_type")=="NASA_LAB" and (x.get("astronaut_id") or x.get("subject_id"))==participant),None)
    base=(result or {}).get("baseline_summary",{}).get(biomarker,{})
    render_biomarker_chart(subset,biomarker,base)
    render_trajectory_summary((result or {}).get("trajectory_summary"),biomarker)
    if not result:
        if st.button("Run analysis for selected participant",type="primary",key="trajectory_run"):
            analyze_nasa(participant); st.rerun()
        st.caption("Trajectory classification appears after an analysis for this participant has been run.")


def main() -> None:
    st.set_page_config(page_title="WEDJAT-X · Mission Health Systems",page_icon="◈",layout="wide",initial_sidebar_state="expanded")
    css=(Path(__file__).resolve().parent/"styles"/"main.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>",unsafe_allow_html=True)
    page,source=render_sidebar()
    routes={
        "Mission Overview":page_overview,
        "Astronaut Monitoring":page_astronaut,
        "Analysis Console":lambda:page_console(source),
        "Live Telemetry":page_telemetry,
        "NASA Biomarkers":page_biomarkers,
        "Alert Center":page_alerts,
        "Sensor Trust":page_sensor_trust,
        "Recovery Trajectory":page_trajectory,
    }
    routes[page]()
    st.markdown("<div style='margin-top:42px;border-top:1px solid #203346;padding-top:14px;color:#6f8497;font:9px DM Mono,monospace'>WEDJAT-X · OFFLINE RESEARCH DECISION SUPPORT · HUMAN MEDICAL REVIEW REQUIRED</div>",unsafe_allow_html=True)


if __name__ == "__main__":
    main()
