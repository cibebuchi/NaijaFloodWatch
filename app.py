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

# Title
st.markdown("""
<div class="header-container">
  <h1 class="app-header">NaijaFloodWatch</h1>
</div>
""", unsafe_allow_html=True)

# Asset paths
SHAPEFILE = 'attached_assets/gadm41_NGA_2.geojson'
BASELINE_CSV = 'attached_assets/baseline_20220914.csv'
LOGO_PATH = 'attached_assets/logo.jpg'

# Sidebar configuration
with st.sidebar:
    try:
        st.image(LOGO_PATH, width=120)
    except:
        pass
    st.subheader("Dashboard Mode")
    mode = st.radio("View mode", ["About", "Forecast", "Historical"], index=1)
    with st.expander("Help & Information"):
        st.markdown(
            """
1. Select mode (Forecast or Historical).
2. Choose State and LGA.
3. Pick a date.
4. Click 'Fetch Data' to load.
5. Review metrics and charts.
"""
        )

# Load data
try:
    lga_gdf = load_lga_gdf(SHAPEFILE)
    if lga_gdf.empty:
        raise FileNotFoundError
except Exception as e:
    st.error(f"Error loading LGA data: {e}")
    st.stop()

try:
    baseline_map = load_baseline(BASELINE_CSV)
except Exception as e:
    st.error(f"Error loading baseline CSV: {e}")
    st.stop()

# Date settings
today = datetime.date.today()
FORECAST_DAYS = 7

# About mode
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
This engine may be more effective for LGAs that were affected by the September 2022 flood event, as these areas have established baseline values for more accurate risk assessment.
"""
    )
    st.stop()

# Reset state on mode change
if st.session_state.get('mode') != mode:
    for key in ['sel_lga', 'lat', 'lon', 'forecast_data', 'historical_data', 'last_fetch']:
        st.session_state.pop(key, None)
    st.session_state['mode'] = mode

# Main layout: selection and display
col_sel, col_disp = st.columns([1, 2])

with col_sel:
    st.subheader("📍 Select LGA & Date")
    states = sorted(lga_gdf['State'].unique())
    state_choice = st.selectbox("State:", ["All"] + states)
    if state_choice != "All":
        lga_list = sorted(lga_gdf[lga_gdf['State'] == state_choice]['LGA'])
    else:
        lga_list = sorted(lga_gdf['LGA'])
    lga_choice = st.selectbox("LGA:", lga_list)
    if lga_choice:
        sel = lga_gdf[lga_gdf['LGA'] == lga_choice].iloc[0]
        st.session_state['sel_lga'] = lga_choice
        st.session_state['lat'] = sel['lat']
        st.session_state['lon'] = sel['lon']
    # Date input
    if mode == "Historical":
        date = st.date_input("Select date:", max_value=today, value=today)
    else:
        min_date = today - datetime.timedelta(days=FORECAST_DAYS)
        max_date = today + datetime.timedelta(days=FORECAST_DAYS)
        date = st.date_input("Select date:", min_value=min_date, max_value=max_date, value=today)
    fetch = st.button("Fetch Data")

with col_disp:
    if 'sel_lga' not in st.session_state:
        st.info("Please select an LGA and date, then click 'Fetch Data'.")
    else:
        lat = st.session_state['lat']
        lon = st.session_state['lon']
        lga_name = st.session_state['sel_lga']
        baseline = baseline_map.get(lga_name)

        if fetch or st.session_state.get('last_fetch'):
            st.session_state['last_fetch'] = True
            if mode == "Forecast":
                # Fetch and display forecast
                with st.spinner("Fetching forecast data..."):
                    df = fetch_open_meteo_forecast(lat, lon, FORECAST_DAYS)
                df['date'] = pd.to_datetime(df['date']).dt.date
                st.session_state['forecast_data'] = df

                # Plot full 7-day forecast chart
                fig = generate_time_series_chart(df, lga_name, baseline)
                st.plotly_chart(fig, use_container_width=True)

                # Display metrics for selected date
                if date in df['date'].values:
                    row = df[df['date'] == date].iloc[0]
                    discharge = row['discharge_max']
                    ratio = discharge / baseline if baseline else None
                    level, color = determine_risk_level(ratio)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Forecast (m³/s)", f"{discharge:.2f}")
                    m2.metric("Baseline (m³/s)", f"{baseline:.2f}" if baseline else "-")
                    m3.metric("Ratio", f"{ratio:.2f}" if ratio else "-")
                    m4.markdown(
                        f"<div style='background-color:{color};padding:8px;border-radius:4px;text-align:center;'>"
                        f"<strong>Risk: {level}</strong></div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("Selected date outside forecast range; review full 7-day chart above.")

            else:
                # Fetch and display historical
                with st.spinner("Fetching historical data..."):
                    hist_df = fetch_open_meteo_historical(lat, lon, date.strftime('%Y-%m-%d'))
                discharge = hist_df.iloc[0]['discharge_max']
                st.subheader(f"Observed discharge on {date:%Y-%m-%d}")
                st.metric("Discharge (m³/s)", f"{discharge:.2f}")

# Footer
st.markdown(
    "<hr><p style='text-align:center;'>Maintained and Created by Chibuike Ibebuchi and Itohan-Osa Abu</p>",
    unsafe_allow_html=True
)

# Commit instructions:
# git add app.py
# git commit -m "Fix syntax and duplicate blocks; correct layout for date input"
# git push origin main
