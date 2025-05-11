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

# Placeholder: continue with app logic
