import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from requests import HTTPError

# Import utilities
try:
    from utils import (
        load_lga_gdf,
        load_baseline,
        create_choropleth_map,
        generate_time_series_chart,
        determine_risk_level,
    )
except ImportError as e:
    st.error(f"Failed to import utils module: {e}. Ensure utils.py is present and functions are defined.")
    st.stop()

# Import fetch functions
try:
    from fetch_open_meteo import (
        fetch_open_meteo_forecast,
        fetch_open_meteo_historical,
    )
except ImportError as e:
    st.error(f"Failed to import fetch_open_meteo module: {e}. Ensure fetch_open_meteo.py is present and functions are defined.")
    st.stop()

# App configuration
st.set_page_config(page_title="NaijaFloodWatch", layout="wide")

# CSS styling
st.markdown("""
<style>
    .metric-container { background-color: #f7f7f7; border-radius: 5px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }
    .metric-value { font-size: 28px; font-weight: bold; }
    .metric-label { font-size: 14px; color: #666; }
    .risk-high { background-color: #ffebee; color: #d32f2f; }
    .risk-medium { background-color: #fff8e1; color: #ff8f00; }
    .risk-low { background-color: #e8f5e9; color: #2e7d32; }
    .header-container { display: flex; align-items: center; justify-content: space-between; }
    .app-header { color: #0078D7; margin-bottom: 20px; }
    .stApp header { background-color: rgba(0, 120, 215, 0.1); }
</style>
""", unsafe_allow_html=True)

# App title
st.markdown("""
<div class="header-container">
    <h1 class="app-header">NaijaFloodWatch</h1>
</div>
""", unsafe_allow_html=True)

# Default asset paths
default_shapefile = 'attached_assets/gadm41_NGA_2.json'
default_baseline_csv = 'attached_assets/baseline_20220914.csv'

# Sidebar configuration
with st.sidebar:
    # Display logo if available, else skip
    try:
        st.image('logo.jpeg', width=150)
    except Exception:
        pass
    shapefile_path = default_shapefile
    baseline_csv = default_baseline_csv

    st.subheader("Dashboard Mode")
    mode = st.radio("Select View", ["About", "Forecast", "Historical"], index=1)
    with st.expander("Help & Information"):
        st.markdown(
            """
1. Select Forecast or Historical mode.
2. Choose a State and LGA.
3. In Forecast: pick a future date; in Historical: pick a past date.
4. View metrics and risk level for the selected day.
"""
        )

# Load GeoJSON for LGAs
try:
    lga_gdf = load_lga_gdf(shapefile_path)
    if lga_gdf is None:
        raise ValueError("Empty GeoDataFrame")
except Exception as e:
    st.error(f"Error loading GeoJSON: {e}")
    st.stop()

# Load baseline discharge map
try:
    baseline_map = load_baseline(baseline_csv)
    if not baseline_map:
        st.warning("No baseline data found. Risk levels may be incomplete.")
except Exception as e:
    st.error(f"Error loading baseline CSV: {e}")
    st.stop()

# Date settings
today = datetime.date.today()
FORECAST_DAYS = 7

# About section
if mode == "About":
    st.markdown(
        """
## Nigeria Flood Early-Warning System

This dashboard provides 7-day river discharge forecasts and single-day historical data for LGAs in Nigeria.

- **Forecast**: future discharge forecasts from Open-Meteo's GloFAS API.
- **Historical**: observed discharge for a specific past date.
- **Risk assessment**: compares discharge against baseline values from 14 September 2022.
"""
    )
    st.stop()

# Clear cache when mode changes
if 'last_mode' in st.session_state and st.session_state['last_mode'] != mode:
    for key in ['forecast_data', 'historical_data', 'hist_date_fetched']:
        st.session_state.pop(key, None)
st.session_state['last_mode'] = mode

# Layout columns
select_col, results_col = st.columns([1, 1])

with select_col:
    st.subheader("📍 Nigeria LGA Selection")
    states = sorted(lga_gdf['State'].unique())
    state_filter = st.selectbox("Filter by State:", ["All States"] + states)

    if state_filter != "All States":
        filtered_lgas = sorted(lga_gdf[lga_gdf['State'] == state_filter]['LGA'])
    else:
        filtered_lgas = sorted(lga_gdf['LGA'])

    selected_lga = st.selectbox("Select Local Government Area:", [""] + filtered_lgas)
    if st.button("Select LGA"):
        sel = lga_gdf[lga_gdf['LGA'] == selected_lga].iloc[0]
        for key in ['sel_lga', 'sel_state', 'lat', 'lon']:
            st.session_state[key] = sel[key] if key in sel else None
        st.experimental_rerun()

    if 'sel_lga' in st.session_state:
        st.success(f"Selected: {st.session_state['sel_lga']}, {st.session_state['sel_state']}")
        st.markdown(
            f"""
<div style='background-color: #eee; padding: 10px; border-radius: 5px; margin-top: 10px;'>
  <strong>Geographic Location</strong><br>
  Lat: {st.session_state['lat']:.4f}°, Lon: {st.session_state['lon']:.4f}°
</div>
""",
            unsafe_allow_html=True,
        )

with results_col:
    if mode == "Forecast":
        st.subheader("🌧️ Flood Forecast")
        if 'sel_lga' not in st.session_state:
            st.info("Please select a state and LGA to view forecast data.")
        else:
            lga = st.session_state['sel_lga']
            lat = st.session_state['lat']
            lon = st.session_state['lon']
            baseline = baseline_map.get(lga)

            if 'forecast_data' not in st.session_state:
                try:
                    with st.spinner("Fetching forecast data..."):
                        df = fetch_open_meteo_forecast(lat, lon, days=FORECAST_DAYS)
                    if df is None or df.empty:
                        raise ValueError("Empty forecast DataFrame")
                    if not {'date', 'discharge_max'}.issubset(df.columns):
                        raise KeyError("Missing 'date' or 'discharge_max' columns")
                    df['date'] = df['date'].astype(str)
                    st.session_state['forecast_data'] = df
                except Exception as e:
                    st.error(f"Error fetching forecast: {e}")
                    st.stop()

            df = st.session_state['forecast_data']
            available_dates = sorted(pd.to_datetime(df['date']).dt.date.unique())
            date = st.date_input(
                "Select forecast date",
                min_value=available_dates[0],
                max_value=available_dates[-1],
                value=available_dates[0],
            )
            discharge = float(df.loc[df['date'] == str(date), 'discharge_max'])
            ratio = (discharge / baseline) if baseline else None
            risk_level, risk_color = determine_risk_level(ratio)

            st.markdown(f"### Forecast for {date:%B %d, %Y}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Forecast (m³/s)", f"{discharge:.2f}")
            m2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
            m3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
            m4.markdown(
                f"<div style='background-color:{risk_color};padding:10px;border-radius:5px;text-align:center;'>"
                f"<span style='color:white;font-weight:bold;'>Risk: {risk_level}</span></div>",
                unsafe_allow_html=True,
            )
            fig = generate_time_series_chart(df, lga, baseline)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

    else:
        # Single‐date Historical mode
        st.subheader("📜 Historical Data")
        if 'sel_lga' not in st.session_state:
            st.info("Please select a state and LGA to view historical data.")
        else:
            lga = st.session_state['sel_lga']
            lat = st.session_state['lat']
            lon = st.session_state['lon']
            baseline = baseline_map.get(lga)

            hist_date = st.date_input(
                "Select historical date",
                min_value=datetime.date(2022, 9, 14),
                max_value=today,
                value=today,
            )

            if ('hist_date_fetched' not in st.session_state or
                    st.session_state['hist_date_fetched'] != hist_date):
                try:
                    with st.spinner("Fetching historical data…"):
                        hist_df = fetch_open_meteo_historical(
                            lat,
                            lon,
                            start_date=hist_date.strftime("%Y-%m-%d"),
                        )
                    if hist_df is None or hist_df.empty:
                        st.error("No data available for the selected date.")
                        st.session_state['historical_data'] = None
                    else:
                        st.session_state['historical_data'] = hist_df
                    st.session_state['hist_date_fetched'] = hist_date
                except Exception as e:
                    st.error(f"Error fetching historical: {e}")
                    st.session_state['historical_data'] = None

            hist_df = st.session_state.get('historical_data')
            if hist_df is None:
                st.stop()

            obs = float(hist_df.loc[0, 'discharge_max'])
            ratio = (obs / baseline) if baseline else None
            risk_level, risk_color = determine_risk_level(ratio)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Observed (m³/s)", f"{obs:.2f}")
            c2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
            c3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
            c4.markdown(
                f"<div style='background-color:{risk_color};padding:10px;border-radius:5px;text-align:center;'>"
                f"<span style='color:white;font-weight:bold;'>Risk: {risk_level}</span></div>",
                unsafe_allow_html=True,
            )

# Footer
st.markdown(
    "<hr><p style='text-align:center;'>Maintained and Created by Chibuike Ibebuchi and Itohan-Osa Abu</p>",
    unsafe_allow_html=True,
)
