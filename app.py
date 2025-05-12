import os
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
default_shapefile = 'attached_assets/gadm41_NGA_2.geojson'
default_baseline_csv = 'attached_assets/baseline_20220914.csv'

# Sidebar configuration
with st.sidebar:
    # Display logo.jpg (preferred)
    try:
        st.image('attached_assets/logo.jpg', width=150)
    except Exception:
        pass

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
    lga_gdf = load_lga_gdf(default_shapefile)
    if lga_gdf is None or lga_gdf.empty:
        raise FileNotFoundError(f"GeoJSON not found or empty at {default_shapefile}")
except Exception as e:
    st.error(f"Error loading GeoJSON: {e}")
    st.stop()

# Load baseline discharge map
try:
    baseline_map = load_baseline(default_baseline_csv)
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

This dashboard provides flood risk monitoring and forecasting for Local Government Areas (LGAs) across Nigeria.

**Key Features:**
- Real-time Forecasts: 7-day river discharge predictions for any LGA
- Risk Assessment: Comparison against September 2022 flood baseline
- Historical Analysis: Review river discharge data for past dates
- LGA Selection: Select any Local Government Area for detailed information

**Data Sources:**
The system uses hydrological data from the Copernicus Global Flood Awareness System (GloFAS) provided through the Open-Meteo API. Baseline values represent the river discharge during the significant flooding event of September 14, 2022.

**Using The Dashboard:**
1. Select a state and LGA from the dropdown menus
2. View forecast or historical data based on your selected mode
3. Analyze the river discharge values and risk levels
4. Explore the 7-day forecast in the time series chart

**Disclaimer:**
This engine may be more effective for LGAs that were affected by the September 2022 flood event, as these areas have established baseline values for more accurate risk assessment. Also the forecast value does not automatically update when date or LGA is changed.
"""
    )
    st.stop()

# Clear cache when mode changes
if st.session_state.get('last_mode') != mode:
    for k in ['forecast_data', 'historical_data', 'hist_date_fetched', 'sel_lga', 'sel_state', 'lat', 'lon']:
        st.session_state.pop(k, None)
st.session_state['last_mode'] = mode

# Layout columns
col1, col2 = st.columns(2)
with col1:
    st.subheader("📍 Nigeria LGA Selection")
    states = sorted(lga_gdf['State'].unique())
    chosen_state = st.selectbox("Filter by State:", ["All States"] + states)
    lgas = sorted(lga_gdf[lga_gdf['State']==chosen_state]['LGA']) if chosen_state!="All States" else sorted(lga_gdf['LGA'])
    chosen_lga = st.selectbox("Select Local Government Area:", [""] + lgas)
    if chosen_lga:
        sel = lga_gdf[lga_gdf['LGA']==chosen_lga].iloc[0]
        # Update selected LGA and clear previous data caches
        st.session_state['sel_lga'] = sel['LGA']
        st.session_state['sel_state'] = sel['State']
        st.session_state['lat'] = sel['lat']
        st.session_state['lon'] = sel['lon']
        for cache_key in ['forecast_data', 'historical_data', 'hist_date_fetched']:
            st.session_state.pop(cache_key, None)
        st.rerun()
    if st.session_state.get('sel_lga'):
        st.success(f"Selected: {st.session_state['sel_lga']}, {st.session_state['sel_state']}")
        st.markdown(f"**Lat:** {st.session_state['lat']:.4f}°, **Lon:** {st.session_state['lon']:.4f}°")

with col2:
    if mode == "Forecast":
        st.subheader("🌧️ Flood Forecast")
        if not st.session_state.get('sel_lga'):
            st.info("Please select a state and LGA.")
        else:
            df = st.session_state.get('forecast_data')
            if df is None:
                with st.spinner("Fetching forecast data..."):
                    df = fetch_open_meteo_forecast(st.session_state['lat'], st.session_state['lon'], FORECAST_DAYS)
                st.session_state['forecast_data'] = df
            if df is not None and not df.empty:
                df['date'] = pd.to_datetime(df['date']).dt.date
                date = st.date_input("Select forecast date", min_value=df['date'].min(), max_value=df['date'].max(), value=df['date'].min())
                row = df[df['date']==date].iloc[0]
                discharge = row['discharge_max']
                baseline = baseline_map.get(st.session_state['sel_lga'])
                ratio = discharge / baseline if baseline else None
                level, color = determine_risk_level(ratio)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Forecast (m³/s)", f"{discharge:.2f}")
                c2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
                c3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
                c4.markdown(f"<div style='background-color:{color};padding:10px;border-radius:5px;text-align:center;'><strong>Risk: {level}</strong></div>", unsafe_allow_html=True)
                fig = generate_time_series_chart(df, st.session_state['sel_lga'], baseline)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.subheader("📜 Historical Data")
        if not st.session_state.get('sel_lga'):
            st.info("Please select a state and LGA.")
        else:
            date = st.date_input("Select historical date", min_value=datetime.date(2022,9,14), max_value=today, value=today)
            fetched = st.session_state.get('hist_date_fetched')
            if fetched != date:
                with st.spinner("Fetching historical data..."):
                    hist_df = fetch_open_meteo_historical(st.session_state['lat'], st.session_state['lon'], date.strftime("%Y-%m-%d"))
                st.session_state['historical_data'] = hist_df
                st.session_state['hist_date_fetched'] = date
            hist_df = st.session_state.get('historical_data')
            if hist_df is not None and not hist_df.empty:
                discharge = hist_df.iloc[0]['discharge_max']
                baseline = baseline_map.get(st.session_state['sel_lga'])
                ratio = discharge / baseline if baseline else None
                level, color = determine_risk_level(ratio)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Observed (m³/s)", f"{discharge:.2f}")
                c2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
                c3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
                c4.markdown(f"<div style='background-color:{color};padding:10px;border-radius:5px;text-align:center;'><strong>Risk: {level}</strong></div>", unsafe_allow_html=True)

# Footer
st.markdown("<hr><p style='text-align:center;'>Maintained and Created by Chibuike Ibebuchi and Itohan-Osa Abu</p>", unsafe_allow_html=True)


