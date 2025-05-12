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
    .header-container { display: flex; align-items: center; justify-content: space-between; }
    .app-header { color: #0078D7; margin-bottom: 20px; }
    .stApp header { background-color: rgba(0,120,215,0.1); }
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
4. Click the 'Fetch Data' button.
5. Review metrics and chart.
"""
        )

# Load data
try:
    lga_gdf = load_lga_gdf(SHAPEFILE)
    if lga_gdf.empty:
        raise FileNotFoundError("Empty GeoDataFrame")
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

This dashboard provides flood risk monitoring and forecasting for LGAs across Nigeria.

**Key Features:**
- Real-time 7-day forecasts
- Risk assessment vs. Sep 2022 baseline
- Single-day historical data
- Manual fetch for updated data

**Data Sources:**
Copernicus GloFAS via Open-Meteo API; baseline = discharge on 14 Sep 2022.

**Usage:**
1. Select State & LGA.
2. Choose Forecast or Historical.
3. Pick date and click 'Fetch Data'.
4. View metrics and chart.

**Disclaimer:**
Manual fetch required; Forecast metrics only valid for dates within range; Historical shows raw discharge only.
"""
    )
    st.stop()

# Reset on mode change
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
    if state != "All":
        options = sorted(lga_gdf[lga_gdf['State'] == state]['LGA'])
    else:
        options = sorted(lga_gdf['LGA'])
    lga = st.selectbox("LGA:", options)
    if lga:
        sel = lga_gdf[lga_gdf['LGA'] == lga].iloc[0]
        st.session_state['sel_lga'] = lga
        st.session_state['lat'] = sel['lat']
        st.session_state['lon'] = sel['lon']
    date = st.date_input(
        "Select date:",
        min_value=today - datetime.timedelta(days=FORECAST_DAYS),
        max_value=(today if mode == "Historical" else today + datetime.timedelta(days=FORECAST_DAYS)),
        value=today
    )
    fetch_btn = st.button("Fetch Data")

with col2:
    if 'sel_lga' not in st.session_state:
        st.info("Select an LGA and date, then click 'Fetch Data'.")
    else:
        lat = st.session_state['lat']
        lon = st.session_state['lon']
        lga_name = st.session_state['sel_lga']
        baseline = baseline_map.get(lga_name)

        if fetch_btn or st.session_state.get('last_fetch'):
            st.session_state['last_fetch'] = True
            # Forecast mode
            if mode == "Forecast":
                with st.spinner("Fetching forecast data..."):
                    df = fetch_open_meteo_forecast(lat, lon, FORECAST_DAYS)
                st.session_state['forecast_data'] = df
                df = df.copy()
                df['date'] = pd.to_datetime(df['date']).dt.date
                # Always show the 7-day chart
                fig = generate_time_series_chart(df, lga_name, baseline)
                st.plotly_chart(fig, use_container_width=True)
                # Show metrics for selected date if available
                if date in df['date'].values:
                    row = df[df['date'] == date].iloc[0]
                    discharge = row['discharge_max']
                    ratio = (discharge / baseline) if baseline else None
                    level, color = determine_risk_level(ratio)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Forecast (m³/s)", f"{discharge:.2f}")
                    m2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
                    m3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
                    m4.markdown(
                        f"<div style='background-color:{color};padding:8px;border-radius:4px;text-align:center;'><strong>Risk: {level}</strong></div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("Selected date is outside the forecast range. Displaying full 7-day forecast.")
            # Historical mode
            else:
                with st.spinner("Fetching historical data..."):
                    hist_df = fetch_open_meteo_historical(lat, lon, date.strftime("%Y-%m-%d"))
                st.session_state['historical_data'] = hist_df
                discharge = hist_df.iloc[0]['discharge_max']
                st.subheader(f"Observed discharge on {date:%Y-%m-%d}")
                st.metric("Discharge (m³/s)", f"{discharge:.2f}")

# Footer
st.markdown(
    "<hr><p style='text-align:center;'>Maintained and Created by Chibuike Ibebuchi and Itohan-Osa Abu</p>",
    unsafe_allow_html=True
)

# To commit:
# git add app.py
# git commit -m "Handle forecast dates outside range and always show full 7-day chart"
# git push origin main