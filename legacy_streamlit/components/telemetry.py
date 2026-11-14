import pandas as pd
import plotly.express as px
import streamlit as st

COLORS = {"heart_rate": "#47dce8", "spo2": "#74a9ff", "accelerometer": "#d7b56d"}


def render_telemetry_chart(data: pd.DataFrame, title: str = "Synthetic sensor stream") -> None:
    if data is None or data.empty:
        st.info("No telemetry samples are available. Select a local scenario and run analysis.")
        return
    required = {"timestamp", "sensor_type", "signal_value"}
    if not required.issubset(data.columns):
        st.warning("This dataset does not contain the expected timestamped sensor fields.")
        return
    fig = px.line(data, x="timestamp", y="signal_value", color="sensor_type", facet_row="sensor_type",
                  color_discrete_map=COLORS, markers=False, title=title,
                  labels={"timestamp": "Mission time", "signal_value": "Observed signal", "sensor_type": "Sensor"})
    fig.update_traces(connectgaps=False, line=dict(width=2))
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(9,18,29,.7)",
                      font=dict(family="Manrope, sans-serif", color="#aabccc"), title_font_size=14,
                      margin=dict(l=8,r=15,t=50,b=10), height=max(310, 230*data.sensor_type.nunique()),
                      legend_title_text="Synthetic sensor")
    fig.update_xaxes(showgrid=True, gridcolor="#203346", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#203346", zeroline=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
