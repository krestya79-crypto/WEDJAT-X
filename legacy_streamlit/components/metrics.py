import streamlit as st


def metric_card(label: str, value: str, caption: str = "") -> None:
    st.markdown(f"<div class='card'><div class='card-kicker'>{label}</div><div class='card-value'>{value}</div><div class='card-caption'>{caption}</div></div>", unsafe_allow_html=True)


def safe_value(value, suffix: str = "", digits: int = 1) -> str:
    if value is None:
        return "Unavailable"
    try:
        import pandas as pd
        if pd.isna(value):
            return "Unavailable"
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def percent_value(fraction, digits: int = 1) -> str:
    if fraction is None:
        return "Unavailable"
    try:
        import pandas as pd
        if pd.isna(fraction):
            return "Unavailable"
        return f"{float(fraction) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "Unavailable"
