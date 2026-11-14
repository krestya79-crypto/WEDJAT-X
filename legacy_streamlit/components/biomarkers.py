import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_biomarker_chart(data: pd.DataFrame, biomarker: str, baseline: dict | None = None) -> None:
    points = data.loc[data["Biomarker_Name"] == biomarker].copy()
    if points.empty:
        st.info("No observations for this biomarker in the selected participant.")
        return
    points["Measurement_Value"] = pd.to_numeric(points["Measurement_Value"], errors="coerce")
    order = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
    points["Timepoint"] = pd.Categorical(points["Timepoint"], categories=order, ordered=True)
    points = points.sort_values("Timepoint")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=points.Timepoint.astype(str), y=points.Measurement_Value, mode="lines+markers",
                             connectgaps=False, name="OSD-575 assay", line=dict(color="#47dce8",width=2),
                             marker=dict(size=8,color="#47dce8"), hovertemplate="%{x}<br>%{y}<extra>Discrete assay</extra>"))
    median = (baseline or {}).get("baseline_median")
    if median is not None and pd.notna(median):
        fig.add_hline(y=float(median), line_dash="dash", line_color="#d1ad5e",
                      annotation_text="Personal preflight median", annotation_font_color="#d1ad5e")
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(9,18,29,.7)",
                      font=dict(family="Manrope, sans-serif", color="#aabccc"), height=390,
                      margin=dict(l=10,r=20,t=30,b=10), xaxis_title="OSD-575 mission milestone",
                      yaxis_title=str(points["Measurement_Unit"].dropna().iloc[0]) if "Measurement_Unit" in points and points["Measurement_Unit"].notna().any() else "Measured value")
    fig.update_xaxes(showgrid=True,gridcolor="#203346")
    fig.update_yaxes(showgrid=True,gridcolor="#203346")
    st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})
