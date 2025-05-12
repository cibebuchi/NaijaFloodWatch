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
3. Select date.
4. Click the Fetch button to load data.
5. View metrics and chart.
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

# Date settings
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
3. Pick date and click Fetch.
4. Review the displayed metrics and charts.

**Disclaimer:**
Most accurate for LGAs affected by Sep 2022 flood; this dashboard requires manual Fetch after selection changes.
"""
    )
    st.stop()

# Reset session on mode change
if st.session_state.get('mode') != mode:
    for key in ['sel_lga', 'lat', 'lon', 'forecast_data', 'historical_data', 'last_fetch']:
        st.session_state.pop(key, None)
    st.session_state['mode'] = mode

# Layout
col1, col2 = st.columns([1, 2])
with col1:
    st.subheader("📍 LGA Selection")
    states = sorted(lga_gdf['State'].unique())
    state = st.selectbox("State:", ["All"] + states)
    options = sorted(lga_gdf[lga_gdf['State']==state]['LGA']) if state!="All" else sorted(lga_gdf['LGA'])
    lga = st.selectbox("LGA:", options)
    if lga:
        sel = lga_gdf[lga_gdf['LGA']==lga].iloc[0]
        st.session_state['sel_lga'] = lga
        st.session_state['lat'] = sel['lat']
        st.session_state['lon'] = sel['lon']
    date = st.date_input("Select date:", min_value=(today - datetime.timedelta(days=FORECAST_DAYS)), max_value=today if mode=="Historical" else today + datetime.timedelta(days=FORECAST_DAYS), value=today)
    fetch_btn = st.button("Fetch Data")

with col2:
    if 'sel_lga' not in st.session_state:
        st.info("Please select an LGA and date, then click Fetch.")
    else:
        lat = st.session_state['lat']
        lon = st.session_state['lon']
        lga_name = st.session_state['sel_lga']
        baseline = baseline_map.get(lga_name)

        if fetch_btn or st.session_state.get('last_fetch'):
            st.session_state['last_fetch'] = True
            if mode == "Forecast":
                with st.spinner("Fetching forecast data..."):
                    df = fetch_open_meteo_forecast(lat, lon, FORECAST_DAYS)
                st.session_state['forecast_data'] = df
                df = df.copy()
                df['date'] = pd.to_datetime(df['date']).dt.date
                row = df[df['date']==date].iloc[0]
                discharge = row['discharge_max']
                ratio = discharge/baseline if baseline else None
                level, color = determine_risk_level(ratio)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Forecast (m³/s)", f"{discharge:.2f}")
                c2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
                c3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
                c4.markdown(f"<div style='background-color:{color};padding:8px;border-radius:4px;text-align:center;'><strong>Risk: {level}</strong></div>", unsafe_allow_html=True)
                fig = generate_time_series_chart(df, lga_name, baseline)
                st.plotly_chart(fig, use_container_width=True)
            else:
                with st.spinner("Fetching historical data..."):
                    hist_df = fetch_open_meteo_historical(lat, lon, date.strftime("%Y-%m-%d"))
                st.session_state['historical_data'] = hist_df
                discharge = hist_df.iloc[0]['discharge_max']
                st.subheader(f"Observed discharge on {date.strftime('%Y-%m-%d')} (m³/s)")
                st.metric("Discharge", f"{discharge:.2f}")

# Footer
st.markdown("<hr><p style='text-align:center;'>Maintained and Created by Chibuike Ibebuchi and Itohan-Osa Abu</p>", unsafe_allow_html=True)

# To commit:
# git add app.py
# git commit -m "Add manual Fetch button; remove baseline in Historical mode"
# git push origin main
