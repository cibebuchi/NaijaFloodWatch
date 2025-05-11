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
from utils import load_lga_gdf, load_baseline, create_choropleth_map, generate_time_series_chart, determine_risk_level
from static_map import create_static_map

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

# Default shapefile path (update if needed)
default_shapefile = 'attached_assets/gadm41_NGA_2.geojson'

# Sidebar configuration
with st.sidebar:
    st.image('logo.jpeg', width=150)
    
    # Hidden configuration - not visible to users
    shapefile_path = default_shapefile
    baseline_csv = 'attached_assets/baseline_20220914.csv'
    
    st.subheader("Dashboard Mode")
    mode = st.radio("Select View", ["About", "Forecast", "Historical"], index=1)
    
    # Help information
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

# Dates and config
today = datetime.date.today()
FORECAST_DAYS = 7

# About mode
if mode == "About":
    st.markdown("""
    ## Nigeria Flood Early-Warning System
    
    This dashboard provides flood risk monitoring and forecasting for Local Government Areas (LGAs) across Nigeria.
    
    ### Key Features:
    - **Real-time Forecasts**: 7-day river discharge predictions for any LGA
    - **Risk Assessment**: Comparison against September 2022 flood baseline
    - **Historical Analysis**: Review river discharge data for past dates
    - **LGA Selection**: Select any Local Government Area for detailed information
    

    
    ### Data Sources:
    The system uses hydrological data from the Copernicus Global Flood Awareness System (GloFAS) 
    provided through the Open-Meteo API. Baseline values represent the river discharge during 
    the significant flooding event of September 14, 2022.
    
    ### Using The Dashboard:
    1. Select a state and LGA from the dropdown menus
    2. View forecast or historical data based on your selected mode
    3. Analyze the river discharge values and risk levels
    4. Explore the 7-day forecast in the time series chart
    
    ### Disclaimer:
    This engine may be more effective for LGAs that were affected by the September 2022 flood event, 
    as these areas have established baseline values for more accurate risk assessment.
    
    """)
    

    
    # Display static map of Nigeria with LGAs
    st.subheader("Nigeria Local Government Areas (LGAs)")
    
    # Generate static map
    nigeria_map = create_static_map(shapefile_path)
    
    if nigeria_map:
        st.pyplot(nigeria_map)
    
    # LGA selection interface below the map
    st.subheader("LGA Selection Interface")
    
    # Group by state for better organization
    states = sorted(lga_gdf['State'].unique())
    col1, col2 = st.columns(2)
    
    with col1:
        state_filter = st.selectbox("Filter by State:", ["All States"] + list(states), key="about_state_filter")
    
    # Filter LGAs by selected state
    if state_filter != "All States":
        filtered_lgas = sorted(lga_gdf[lga_gdf['State'] == state_filter]['LGA'].tolist())
    else:
        filtered_lgas = sorted(lga_gdf['LGA'].tolist())
    
    with col2:
        st.selectbox("Select Local Government Area (LGA):", filtered_lgas, key="about_lga_select")
    
    # Sample metrics display
    st.subheader("Understanding Risk Indicators")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="metric-container risk-low">
            <div class="metric-value">Low Risk</div>
            <div class="metric-label">Current discharge ≤ 80% of baseline</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class="metric-container risk-medium">
            <div class="metric-value">Medium Risk</div>
            <div class="metric-label">Current discharge between 80-120% of baseline</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown("""
        <div class="metric-container risk-high">
            <div class="metric-value">High Risk</div>
            <div class="metric-label">Current discharge > 120% of baseline</div>
        </div>
        """, unsafe_allow_html=True)

else:  # Forecast or Historical mode
    # Clear cached forecast/historical results if changing modes
    if 'last_mode' in st.session_state and st.session_state['last_mode'] != mode:
        for key in ['forecast_data', 'historical_data']:
            if key in st.session_state:
                del st.session_state[key]
    
    # Store current mode
    st.session_state['last_mode'] = mode
    
    # Create two columns for layout
    map_col, results_col = st.columns([1, 1])
    
    # Map column
    with map_col:
        st.subheader("📍 Nigeria LGA Selection")
        selected_lga = st.session_state.get('sel_lga', None)
        
        # Add tabs for different selection methods
        select_tab1, select_tab2 = st.tabs(["Dropdown Selection", "Interactive Map"])
        
        with select_tab1:
            # Direct LGA selection using dropdown
            all_lgas = sorted(lga_gdf['LGA'].tolist())
            
            # Group by state for better organization
            states = sorted(lga_gdf['State'].unique())
            state_filter = st.selectbox("Filter by State:", ["All States"] + list(states))
            
            # Filter LGAs by selected state
            if state_filter != "All States":
                filtered_lgas = sorted(lga_gdf[lga_gdf['State'] == state_filter]['LGA'].tolist())
            else:
                filtered_lgas = all_lgas
                
            selected = st.selectbox(
                "Select Local Government Area (LGA):", 
                filtered_lgas,
                index=filtered_lgas.index(selected_lga) if selected_lga in filtered_lgas else 0
            )
            
            if st.button("Select LGA", use_container_width=True):
                sel = lga_gdf[lga_gdf['LGA'] == selected].iloc[0]
                
                # Clear any existing forecast or historical data when changing LGA
                for key in ['forecast_data', 'historical_data']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                # Set the new LGA
                st.session_state['sel_lga'] = sel['LGA']
                st.session_state['sel_state'] = sel['State']
                st.session_state['lat'] = sel['lat'] 
                st.session_state['lon'] = sel['lon']
                
                st.rerun()
        
        with select_tab2:
            # Interactive map selection
            st.write("Click to view LGAs in Nigeria:")
            
            try:
                # Create an interactive map
                m = folium.Map(location=[9.08, 8.68], zoom_start=6, tiles='CartoDB positron')
                
                # Add GeoJson layer with hover tooltip
                folium.GeoJson(
                    lga_gdf[['LGA', 'State', 'geometry']].to_json(),
                    style_function=lambda f: {
                        'fillColor': '#ADD8E6',
                        'color': '#555555',
                        'weight': 0.5,
                        'fillOpacity': 0.2
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=['LGA', 'State'],
                        aliases=['LGA:', 'State:'],
                        style="background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;"
                    ),
                    highlight_function=lambda x: {'weight': 3, 'fillOpacity': 0.5, 'color': '#0078D7'}
                ).add_to(m)
                
                # Display the map in Streamlit
                map_data = st_folium(m, width=None, height=400, returned_objects=['last_clicked'])
                
                # LGA selection by map click has been disabled.
                pass
            except Exception as e:
                st.error(f"Error displaying interactive map: {e}")
                st.info("Please use the dropdown selection method instead.")
        
        # Show currently selected LGA - displayed below both tabs
        if 'sel_lga' in st.session_state:
            st.success(f"Selected: {st.session_state['sel_lga']}, {st.session_state['sel_state']}")
            
            # Simple map visualization using static image
            st.markdown(f"""
            <div style='text-align: center; background-color: #f0f2f6; color: #000; padding: 10px; border-radius: 5px; margin-top: 10px;'>
                <p style='margin-bottom: 5px;'><strong>Geographic Location</strong></p>
                <p>Latitude: {st.session_state['lat']:.4f}° | Longitude: {st.session_state['lon']:.4f}°</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Show a table of nearby LGAs for context
            try:
                current_lga = st.session_state['sel_lga']
                current_point = Point(st.session_state['lon'], st.session_state['lat'])
                
                # Calculate distances to all other LGAs
                lga_gdf['distance'] = lga_gdf.apply(
                    lambda row: current_point.distance(Point(row['lon'], row['lat'])),
                    axis=1
                )
                
                # Get 5 nearest LGAs (excluding the selected one)
                nearby = lga_gdf[lga_gdf['LGA'] != current_lga].nsmallest(5, 'distance')
                
                if not nearby.empty:
                    st.markdown("#### Nearby LGAs:")
                    st.dataframe(
                        nearby[['LGA', 'State']],
                        hide_index=True,
                        use_container_width=True
                    )
            except Exception:
                pass
    
    # Results column
    with results_col:
        if mode == "Forecast":
            st.subheader("🌧️ Flood Forecast")
            
            if 'sel_lga' not in st.session_state:
                st.info("Please select a state and LGA from the dropdown menus above to view forecast data.")
            else:
                lga = st.session_state['sel_lga']
                state = st.session_state['sel_state']
                lat = st.session_state['lat']
                lon = st.session_state['lon']
                
                with st.form("forecast_form"):
                    date = st.date_input(
                        "Select Forecast Date", 
                        value=today, 
                        min_value=today, 
                        max_value=today+datetime.timedelta(days=FORECAST_DAYS-1)
                    )
                    btn = st.form_submit_button("Generate Forecast", use_container_width=True)
                
                if btn:
                    # Clear any previous forecast data when generating a new forecast
                    if 'forecast_data' in st.session_state:
                        del st.session_state['forecast_data']
                        
                    try:
                        with st.spinner("Fetching forecast data..."):
                            df = fetch_open_meteo_forecast(lat, lon, days=FORECAST_DAYS)
                            st.session_state['forecast_data'] = df
                            
                            row = df[df['date']==date.strftime('%Y-%m-%d')]
                            discharge = float(row['discharge_max'].iloc[0]) if not row.empty else None
                            base = baseline_map.get(lga)
                            ratio = discharge/base if base and discharge else None
                            risk_level, risk_color = determine_risk_level(ratio)
                            
                            # Display metrics
                            st.markdown(f"### Forecast for {date.strftime('%B %d, %Y')}")
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric(
                                    "Forecast (m³/s)", 
                                    f"{discharge:.2f}" if discharge else "-"
                                )
                            
                            with col2:
                                st.metric(
                                    "Baseline (m³/s)", 
                                    f"{base:.2f}" if base else "-"
                                )
                            
                            with col3:
                                st.metric(
                                    "Ratio", 
                                    f"{ratio:.2f}" if ratio else "-"
                                )
                            
                            with col4:
                                st.markdown(f"""
                                <div style="background-color:{risk_color}; padding:10px; border-radius:5px; text-align:center;">
                                    <span style="color:white; font-weight:bold;">Risk: {risk_level}</span>
                                </div>
                                """, unsafe_allow_html=True)
                                
                            # Also save forecast data for time series visualization
                            st.session_state['forecast_data'] = df
                    
                    except HTTPError as e:
                        st.error(f"API error: {e}")
                        st.session_state.pop('forecast_data', None)
                
        elif mode == "Historical":
            st.subheader("📜 Historical Data")
            
            if 'sel_lga' not in st.session_state:
                st.info("Please select a state and LGA from the dropdown menus above to view historical data.")
            else:
                lga = st.session_state['sel_lga']
                state = st.session_state['sel_state']
                lat = st.session_state['lat']
                lon = st.session_state['lon']
                
                with st.form("historical_form"):
                    date = st.date_input(
                        "Select Historical Date", 
                        value=today-datetime.timedelta(days=1), 
                        min_value=datetime.date(1984,1,1), 
                        max_value=today-datetime.timedelta(days=1)
                    )
                    btn = st.form_submit_button("Retrieve Historical Data", use_container_width=True)
                
                if btn:
                    # Clear any existing historical data
                    if 'historical_data' in st.session_state:
                        del st.session_state['historical_data']
                        
                    try:
                        with st.spinner("Fetching historical data..."):
                            dfh = fetch_open_meteo_historical(lat, lon, date.strftime('%Y-%m-%d'))
                            st.session_state['historical_data'] = dfh
                            discharge = float(dfh['discharge_max'].iloc[0]) if not dfh.empty else None
                            base = baseline_map.get(lga)
                            ratio = discharge/base if base and discharge else None
                            risk_level, risk_color = determine_risk_level(ratio)
                            
                            # Display metrics - for historical we only show the observed discharge value
                            st.markdown(f"### Historical Data for {date.strftime('%B %d, %Y')}")
                            
                            st.metric(
                                "Observed Discharge (m³/s)", 
                                f"{discharge:.2f}" if discharge else "-",
                                delta=None,
                                delta_color="normal"
                            )
                            
                            # Provide some historical context
                            st.info(f"This shows the historical river discharge value for {st.session_state['sel_lga']} on {date.strftime('%B %d, %Y')}. Historical data helps understand past water levels for reference.")
                    
                    except HTTPError as e:
                        st.error(f"API error: {e}")
    
    # Time Series chart (spans both columns)
    if mode == "Forecast" and 'sel_lga' in st.session_state:
        st.subheader("📈 7-Day Forecast Time Series")
        
        lga = st.session_state['sel_lga']
        lat = st.session_state['lat']
        lon = st.session_state['lon']
        baseline = baseline_map.get(lga)
        
        # Get forecast data if not already in session state
        if 'forecast_data' not in st.session_state:
            try:
                with st.spinner("Fetching forecast data for time series..."):
                    forecast_data = fetch_open_meteo_forecast(lat, lon, days=FORECAST_DAYS)
                    st.session_state['forecast_data'] = forecast_data
            except Exception as e:
                st.error(f"Error fetching forecast data: {e}")
                forecast_data = None
        else:
            forecast_data = st.session_state['forecast_data']
            
        if forecast_data is not None:
            fig = generate_time_series_chart(forecast_data, lga, baseline)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
                
                # Show risk level explanation with better visualization
                st.markdown("""
                <div style="background-color: #f0f2f6; color: #000; color: #000; padding: 15px; border-radius: 5px; margin-top: 10px;">
                    <h4 style="margin-top: 0; color: #000;">Risk Level Indicators:</h4>
                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                        <div style="width: 15px; height: 15px; background-color: #4CAF50; margin-right: 10px; border-radius: 2px;"></div>
                        <span><strong>Low Risk</strong>: Current discharge ≤ 80% of baseline</span>
                    </div>
                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                        <div style="width: 15px; height: 15px; background-color: #FFC107; margin-right: 10px; border-radius: 2px;"></div>
                        <span><strong>Medium Risk</strong>: Current discharge between 80-120% of baseline</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div style="width: 15px; height: 15px; background-color: #F44336; margin-right: 10px; border-radius: 2px;"></div>
                        <span><strong>High Risk</strong>: Current discharge > 120% of baseline</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("No forecast data available to display.")
            
    # Information about the forecast
    if 'sel_lga' in st.session_state:
        with st.expander("About the Forecast Methodology"):
            st.markdown("""
            ### Forecast Details
            
            The flood risk assessment is based on comparing current/forecasted river discharge 
            with baseline values from September 14, 2022, which was during a significant flooding 
            event in Nigeria.
            
            **Risk Calculation:**
            - Ratio = Current Discharge / Baseline Discharge
            - Low Risk (Green): Ratio ≤ 0.8
            - Medium Risk (Yellow): 0.8 < Ratio ≤ 1.2
            - High Risk (Red): Ratio > 1.2
            
            Data is sourced from the Copernicus Global Flood Awareness System (GloFAS) via the 
            Open-Meteo API, providing river discharge forecasts with global coverage.
            """)

# Footer
st.markdown("""
---
<div style="text-align: center; color: #666;">
Nigeria Flood Early-Warning Dashboard | Data from Open-Meteo API | Updated: {} UTC<br>
Maintained and Created by Chibuike Ibebuchi and Itohan-Osa Abu
</div>
""".format(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")), unsafe_allow_html=True)
