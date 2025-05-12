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

# Asset paths
SHAPEFILE = 'attached_assets/gadm41_NGA_2.geojson'
BASELINE_CSV = 'attached_assets/baseline_20220914.csv'
LOGO_PATH = 'attached_assets/logo.jpg'

# Sidebar
with st.sidebar:
    try:
        st.image(LOGO_PATH, width=150)
    except:
        pass
    st.subheader("Dashboard Mode")
    mode = st.radio("Select view", ["About", "Forecast", "Historical"], index=1)
    with st.expander("Help & Information"):
        st.markdown(
            """
1. Choose mode (Forecast/Historical).
2. Select State and LGA.
3. Forecast: pick a date; Historical: pick a past date.
4. Metrics update automatically on selection change.
"""
        )

# Load data
try:
    lga_gdf = load_lga_gdf(SHAPEFILE)
    if lga_gdf.empty:
        raise FileNotFoundError
except Exception as e:
    st.error(f"Error loading GeoJSON: {e}")
    st.stop()

try:
    baseline_map = load_baseline(BASELINE_CSV)
except Exception as e:
    st.error(f"Error loading baseline CSV: {e}")
    st.stop()

# Today and forecast horizon
today = datetime.date.today()
FORECAST_DAYS = 7

# About page
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
Hydrological data from the Copernicus GloFAS API via Open-Meteo. Baseline values: discharge on 14 Sep 2022.

**Usage:**
1. Select state & LGA.
2. Switch to Forecast or Historical.
3. Pick date; metrics update automatically.
4. Explore time series chart for forecasts.

**Disclaimer:**
Most accurate for LGAs affected by Sep 2022 flood; changing selection updates metrics but does not auto-fetch mid-chart.
"""
    )
    st.stop()

# Reset session on mode change to clear caches
if st.session_state.get('mode') != mode:
    for key in ['sel_lga', 'sel_state', 'lat', 'lon', 'forecast_data', 'historical_data']:
        st.session_state.pop(key, None)
    st.session_state['mode'] = mode

# Layout
col_select, col_display = st.columns([1, 2])
with col_select:
    st.subheader("📍 LGA Selection")
    states = sorted(lga_gdf['State'].unique())
    state = st.selectbox("State:", ["All"] + states)
    if state != "All":
        options = sorted(lga_gdf[lga_gdf['State']==state]['LGA'])
    else:
        options = sorted(lga_gdf['LGA'])
    lga = st.selectbox("LGA:", options)
    if lga:
        sel = lga_gdf[lga_gdf['LGA']==lga].iloc[0]
        changed = (st.session_state.get('sel_lga') != lga)
        st.session_state['sel_lga'] = lga
        st.session_state['sel_state'] = sel['State']
        st.session_state['lat'] = sel['lat']
        st.session_state['lon'] = sel['lon']
        if changed:
            st.session_state.pop('forecast_data', None)
            st.session_state.pop('historical_data', None)
            st.rerun()

with col_display:
    if not st.session_state.get('sel_lga'):
        st.info("Please select an LGA.")
    else:
        lat = st.session_state['lat']
        lon = st.session_state['lon']
        lga_name = st.session_state['sel_lga']
        baseline = baseline_map.get(lga_name)

        if mode == "Forecast":
            st.subheader("🌧️ Forecast")
            if 'forecast_data' not in st.session_state:
                with st.spinner("Fetching forecast data..."):
                    st.session_state['forecast_data'] = fetch_open_meteo_forecast(lat, lon, FORECAST_DAYS)
            df = st.session_state['forecast_data']
            if df is not None:
                df['date'] = pd.to_datetime(df['date']).dt.date
                date = st.date_input("Date:", min_value=df['date'].min(), max_value=df['date'].max(), value=df['date'].min())
                row = df[df['date']==date].iloc[0]
                discharge = row['discharge_max']
                ratio = discharge/baseline if baseline else None
                level, color = determine_risk_level(ratio)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Forecast (m³/s)", f"{discharge:.2f}")
                m2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
                m3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
                m4.markdown(f"<div style='background-color:{color};padding:8px;border-radius:4px;text-align:center;'><strong>Risk: {level}</strong></div>", unsafe_allow_html=True)
                fig = generate_time_series_chart(df, lga_name, baseline)
                st.plotly_chart(fig, use_container_width=True)

        else:
            st.subheader("📜 Historical")
            date = st.date_input("Date:", min_value=datetime.date(2022,9,14), max_value=today, value=today)
            if ('historical_data' not in st.session_state) or (st.session_state['historical_data_date'] != date):
                with st.spinner("Fetching historical data..."):
                    hist_df = fetch_open_meteo_historical(lat, lon, date.strftime("%Y-%m-%d"))
                st.session_state['historical_data'] = hist_df
                st.session_state['historical_data_date'] = date
            hist_df = st.session_state['historical_data']
            if hist_df is not None:
                discharge = hist_df.iloc[0]['discharge_max']
                ratio = discharge/baseline if baseline else None
                level, color = determine_risk_level(ratio)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Observed (m³/s)", f"{discharge:.2f}")
                c2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
                c3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
                c4.markdown(f"<div style='background-color:{color};padding:8px;border-radius:4px;text-align:center;'><strong>Risk: {level}</strong></div>", unsafe_allow_html=True)

# Footer
st.markdown("<hr><p style='text-align:center;'>Maintained and Created by Chibuike Ibebuchi and Itohan-Osa Abu</p>", unsafe_allow_html=True)

# To commit this change:
# git add app.py
# git commit -m "Fix forecast auto-update on LGA/date change"
# git push origin main
