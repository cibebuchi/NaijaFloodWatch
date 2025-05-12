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


# App Footer
st.markdown("""
<p style='font-size: 12px; color: gray; text-align: center;'>
Nigeria Flood Early-Warning Dashboard | Data from Open-Meteo API | Updated: 2025-05-11 23:59 UTC<br>
Maintained and Created by Chibuike Ibebuchi and Itohan-Osa Abu.
</p>
""", unsafe_allow_html=True)
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

# Show About Page
if mode == "About":
    st.markdown("""
    ## NaijaFloodWatch
    ### Nigeria Flood Early-Warning System
    This dashboard provides flood risk monitoring and forecasting for Local Government Areas (LGAs) across Nigeria.

    #### Key Features:
    - Real-time Forecasts: 7-day river discharge predictions for any LGA
    - Risk Assessment: Comparison against September 2022 flood baseline
    - Historical Analysis: Review river discharge data for past dates
    - LGA Selection: Select any Local Government Area for detailed information

    #### Data Sources:
    The system uses hydrological data from the Copernicus Global Flood Awareness System (GloFAS) provided through the Open-Meteo API. Baseline values represent the river discharge during the significant flooding event of September 14, 2022.

    #### Using The Dashboard:
    1. Select a state and LGA from the dropdown menus
    2. View forecast or historical data based on your selected mode
    3. Analyze the river discharge values and risk levels
    4. Explore the 7-day forecast in the time series chart

    #### Disclaimer:
    This engine may be more effective for LGAs that were affected by the September 2022 flood event, as these areas have established baseline values for more accurate risk assessment.

    #### Understanding Risk Indicators:
    - Low Risk: Current discharge ≤ 80% of baseline
    - Medium Risk: Current discharge between 80-120% of baseline
    - High Risk: Current discharge > 120% of baseline
    """)

# Forecast and Historical Mode Logic
st.markdown("---")
if mode in ["Forecast", "Historical"]:
    state_options = sorted(lga_gdf['State'].unique())
    selected_state = st.selectbox("Select State", state_options)

    filtered_lgas = lga_gdf[lga_gdf['State'] == selected_state]['LGA'].unique()
    selected_lga = st.selectbox("Select Local Government Area (LGA)", sorted(filtered_lgas))
    confirm_lga = st.button("Select LGA")

    st.markdown(f"### Selected: {selected_lga}, {selected_state}")

    # Get lat/lon for selected LGA
    selected_row = lga_gdf[(lga_gdf['LGA'] == selected_lga) & (lga_gdf['State'] == selected_state)]
    if not confirm_lga:
        st.info("Click 'Select LGA' to proceed.")
    elif selected_row.empty:
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
                    # Keep full forecast to plot 7-day trend
                    selected_day_df = forecast_df[forecast_df['date'] == forecast_date.strftime("%Y-%m-%d")]
                except HTTPError:
                    st.error("Failed to fetch forecast data.")
                    forecast_df = None

            if forecast_df is not None and not forecast_df.empty:
                baseline_val = baseline_map.get(selected_lga, None)
                if not selected_day_df.empty:
                    current_val = selected_day_df.iloc[0]['discharge_max']
                    ratio = current_val / baseline_val if baseline_val else None

                    bg_color = "#e8f5e9" if ratio and ratio <= 0.8 else ("#fff8e1" if ratio <= 1.2 else "#ffebee")
                    text_color = "#000"

                    st.markdown(f"""
                        <div class='metric-container' style='background-color: {bg_color}; color: {text_color};'>
                            <div class='metric-value'>{current_val:.2f}</div>
                            <div class='metric-label'>Forecast (m³/s)</div>
                        </div>
                        <div class='metric-container' style='background-color: {bg_color}; color: {text_color};'>
                            <div class='metric-value'>{baseline_val:.2f}</div>
                            <div class='metric-label'>Baseline (m³/s)</div>
                        </div>
                        <div class='metric-container' style='background-color: {bg_color}; color: {text_color};'>
                            <div class='metric-value'>{ratio:.2f}</div>
                            <div class='metric-label'>Ratio</div>
                        </div>
                    """, unsafe_allow_html=True)

                st.subheader("📈 7-Day Forecast Time Series")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=forecast_df['date'], y=forecast_df['discharge_max'],
                                         mode='lines+markers', name='Forecast Discharge'))
                if baseline_val:
                    fig.add_trace(go.Scatter(x=forecast_df['date'], y=[baseline_val]*len(forecast_df),
                                             mode='lines', name='Baseline', line=dict(dash='dash')))

                fig.update_layout(height=350, xaxis_title='Date', yaxis_title='Discharge (m³/s)')
                st.plotly_chart(fig, use_container_width=True)

        # Historical Mode
        elif mode == "Historical":
            hist_date = st.date_input("Select Historical Date", value=datetime.date.today() - datetime.timedelta(days=3))

            with st.spinner("Fetching historical data..."):
                try:
                    hist_df = fetch_open_meteo_historical(lat, lon, hist_date.strftime("%Y-%m-%d"))
                    if hist_df is not None and not hist_df.empty:
                        st.metric("Historical Discharge (m³/s)", f"{hist_df.iloc[0]['discharge_max']:.2f}")
                    else:
                        st.info("No data available for this date.")
                except Exception as e:
                    st.error(f"Error fetching historical data: {e}")
