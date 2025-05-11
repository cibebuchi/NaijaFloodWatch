import os
import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from requests import HTTPError
from shapely.geometry import Point
from fetch_open_meteo import fetch_open_meteo_forecast, fetch_open_meteo_historical
from utils import load_lga_gdf, load_baseline

# Page configuration
st.set_page_config(
    page_title="Nigeria Flood Dashboard",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .metric-container {
        background-color: #f7f7f7;
        border-radius: 5px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
    }
    .metric-label {
        font-size: 14px;
        color: #666;
    }
    .risk-high {
        background-color: #ffebee;
        color: #d32f2f;
    }
    .risk-medium {
        background-color: #fff8e1;
        color: #ff8f00;
    }
    .risk-low {
        background-color: #e8f5e9;
        color: #2e7d32;
    }
    .stApp header {
        background-color: rgba(0, 120, 215, 0.1);
    }
    .header-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .app-header {
        color: #0078D7;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# App title and header
st.markdown(
    """
    <div class="header-container">
        <h1 class="app-header">NaijaFloodWatch</h1>
    </div>
    """, 
    unsafe_allow_html=True
)

# Updated to use GeoJSON instead of .shp
default_shapefile = 'attached_assets/gadm41_NGA_2.geojson'

# Sidebar configuration
with st.sidebar:
    st.image('logo.jpeg', width=150)

    shapefile_path = default_shapefile
    baseline_csv = 'attached_assets/baseline_20220914.csv'

    st.subheader("Dashboard Mode")
    mode = st.radio("Select View", ["About", "Forecast", "Historical"], index=1)

    with st.expander("Help & Information"):
        st.markdown("""
        **How to use this dashboard:**
        1. Select a mode (Forecast or Historical)
        2. Choose a state and LGA from the dropdown menus
        3. View the results and time series data

        **About the data:**
        - Forecast data shows river discharge predictions
        - Risk levels are based on comparison to Sept 14, 2022 baseline
        - Data source: Copernicus GloFAS via Open-Meteo API
        """)

# Load shapefile
try:
    lga_gdf = load_lga_gdf(shapefile_path)
    if lga_gdf is None:
        st.error("Failed to load shapefile data.")
        st.stop()
except Exception as e:
    st.error(f"Error loading shapefile: {e}")
    st.stop()

# Load baseline
try:
    baseline_map = load_baseline(baseline_csv)
    if not baseline_map:
        st.warning("No baseline data available. Risk assessment will be limited.")
except Exception as e:
    st.error(f"Error loading baseline CSV: {e}")
    st.stop()

# Forecast and Historical Mode Logic
if mode in ["Forecast", "Historical"]:
    state_options = sorted(lga_gdf['State'].unique())
    selected_state = st.selectbox("Select State", state_options)

    filtered_lgas = lga_gdf[lga_gdf['State'] == selected_state]['LGA'].unique()
    selected_lga = st.selectbox("Select Local Government Area (LGA)", sorted(filtered_lgas))

    st.markdown(f"### Selected: {selected_lga}, {selected_state}")

    # Get lat/lon for selected LGA
    selected_row = lga_gdf[(lga_gdf['LGA'] == selected_lga) & (lga_gdf['State'] == selected_state)]
    if selected_row.empty:
        st.error("Selected LGA not found in dataset.")
    else:
        lat = selected_row.iloc[0]['lat']
        lon = selected_row.iloc[0]['lon']

        st.markdown(f"**Geographic Location**")
        st.write(f"Latitude: {lat:.4f} | Longitude: {lon:.4f}")

        # Forecast Mode
        if mode == "Forecast":
            forecast_date = st.date_input("Select Forecast Date", value=datetime.date.today())

            with st.spinner("Fetching forecast data..."):
                try:
                    forecast_df = fetch_open_meteo_forecast(lat, lon)
                    forecast_df = forecast_df[forecast_df['date'] == forecast_date.strftime("%Y-%m-%d")]
                except HTTPError:
                    st.error("Failed to fetch forecast data.")
                    forecast_df = None

            if forecast_df is not None and not forecast_df.empty:
                baseline_val = baseline_map.get(selected_lga, None)

                current_val = forecast_df.iloc[0]['discharge_max']
                ratio = current_val / baseline_val if baseline_val else None

                st.metric("Forecast (m³/s)", f"{current_val:.2f}")
                st.metric("Baseline (m³/s)", f"{baseline_val:.2f}" if baseline_val else "N/A")
                st.metric("Ratio", f"{ratio:.2f}" if ratio else "N/A")

        # Historical Mode
        elif mode == "Historical":
            start_date = st.date_input("Start Date", value=datetime.date.today() - datetime.timedelta(days=7))
            end_date = st.date_input("End Date", value=datetime.date.today())

            if start_date >= end_date:
                st.warning("Start date must be before end date")
            else:
                with st.spinner("Fetching historical data..."):
                    try:
                        hist_df = fetch_open_meteo_historical(lat, lon, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
                        if hist_df is not None and not hist_df.empty:
                            st.line_chart(hist_df.set_index("date")["discharge_max"])
                        else:
                            st.info("No historical data available for this range.")
                    except Exception as e:
                        st.error(f"Error fetching historical data: {e}")
