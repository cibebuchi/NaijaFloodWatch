import pandas as pd
import streamlit as st
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
import plotly.express as px
import plotly.graph_objects as go
from shapely.geometry import Point
from streamlit_folium import st_folium
import datetime
import os

@st.cache_data
def load_lga_gdf(path):
    """Load and process LGA shapefile data"""
    try:
        # Read the shapefile
        gdf = gpd.read_file(path)
        
        # Ensure the CRS is WGS 84 (EPSG:4326)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        
        # First convert to a projected CRS for accurate centroid calculation
        gdf_projected = gdf.to_crs(epsg=3857)  # Web Mercator projection
        centroids = gdf_projected.geometry.centroid
        
        # Convert centroids back to WGS 84
        centroids = gpd.GeoSeries(centroids, crs=3857).to_crs(4326)
        
        # Extract coordinates
        gdf['lat'] = centroids.y
        gdf['lon'] = centroids.x
        
        # Identify the LGA name column
        name_cols = ['ADM2_NAME','NAME_2','NAME2','LGA_NAME','ADM2nm','NAME']
        lga_col = next((c for c in gdf.columns if c in name_cols), None)
        state_col = 'NAME_1' if 'NAME_1' in gdf.columns else None
        
        if not lga_col:
            lga_col = next((c for c in gdf.columns if gdf[c].dtype == object and c not in ['geometry','NAME_1']), None)
            
        if not lga_col:
            st.error("Could not identify LGA name column in shapefile")
            return None
            
        # Rename columns for consistency
        rename_cols = {}
        if lga_col:
            rename_cols[lga_col] = 'LGA'
        if state_col:
            rename_cols[state_col] = 'State'
            
        gdf = gdf.rename(columns=rename_cols)
        
        # Ensure 'State' column exists, create if missing
        if 'State' not in gdf.columns:
            gdf['State'] = 'Unknown'
            
        # Return relevant columns
        return gdf[['LGA', 'State', 'lat', 'lon', 'geometry']]
    except Exception as e:
        st.error(f"Error loading shapefile: {e}")
        return None

@st.cache_data
def load_baseline(path):
    """Load baseline data for flood comparison"""
    try:
        df = pd.read_csv(path)
        return df.set_index('LGA')['baseline'].to_dict()
    except Exception as e:
        st.error(f"Error loading baseline data: {e}")
        return {}

def create_choropleth_map(gdf, baseline_map=None, selected_lga=None):
    """Create an enhanced map of Nigeria with LGAs"""
    # Initialize the map centered on Nigeria
    m = folium.Map(
        location=[9.08, 8.68], 
        zoom_start=6,
        tiles='CartoDB positron'
    )
    
    # Style function for GeoJson
    def style_function(feature):
        lga_name = feature['properties']['LGA']
        if selected_lga and lga_name == selected_lga:
            return {
                'fillColor': '#0078D7',
                'color': '#0078D7',
                'weight': 3,
                'fillOpacity': 0.7
            }
        return {
            'fillColor': '#ADD8E6',
            'color': '#555555',
            'weight': 0.5,
            'fillOpacity': 0.2
        }
    
    # Make sure we have valid LGA and State columns
    map_gdf = gdf.copy()
    if 'LGA' not in map_gdf.columns:
        st.error("LGA column not found in GeoDataFrame")
        return m
        
    if 'State' not in map_gdf.columns:
        map_gdf['State'] = 'Unknown'
    
    # Simplified geometries for better performance
    try:
        simplified_gdf = map_gdf.copy()
        simplified_gdf['geometry'] = simplified_gdf.geometry.simplify(0.01)
    except Exception:
        simplified_gdf = map_gdf  # Use original if simplification fails
    
    # Add GeoJson layer with hover tooltip
    try:
        geo_json = folium.GeoJson(
            simplified_gdf[['LGA', 'State', 'geometry']].to_json(),
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['LGA', 'State'],
                aliases=['LGA:', 'State:'],
                style="background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;"
            ),
            highlight_function=lambda x: {'weight': 3, 'fillOpacity': 0.5, 'color': '#0078D7'}
        )
        geo_json.add_to(m)
        
        # Add markers for selected LGA for better visibility
        if selected_lga:
            try:
                selected_row = map_gdf[map_gdf['LGA'] == selected_lga].iloc[0]
                folium.Marker(
                    location=[selected_row['lat'], selected_row['lon']],
                    popup=f"{selected_lga}, {selected_row['State']}",
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(m)
            except (IndexError, KeyError):
                pass  # If we can't add the marker, just continue
    except Exception as e:
        st.error(f"Error creating map layer: {e}")
    
    # Add a legend
    legend_html = '''
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; background-color: white; padding: 10px; border-radius: 5px; box-shadow: 0 0 15px rgba(0,0,0,0.2);">
    <p><strong>Nigeria LGAs</strong></p>
    <p><i style="background: #ADD8E6; width: 15px; height: 15px; display: inline-block; opacity: 0.7;"></i> LGA</p>
    <p><i style="background: #0078D7; width: 15px; height: 15px; display: inline-block; opacity: 0.7;"></i> Selected LGA</p>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def generate_time_series_chart(forecast_data, lga_name, baseline_value=None):
    """Generate enhanced time series chart with Plotly"""
    if forecast_data is None or forecast_data.empty:
        return None
        
    # Create time series with Plotly
    fig = go.Figure()
    
    # Add forecast line
    fig.add_trace(go.Scatter(
        x=forecast_data['date'],
        y=forecast_data['discharge_max'],
        mode='lines+markers',
        name='Discharge Forecast',
        line=dict(color='#0078D7', width=3),
        marker=dict(size=8, color='#0078D7')
    ))
    
    # Add baseline as a horizontal line if available
    if baseline_value and not pd.isna(baseline_value):
        # Add baseline
        fig.add_trace(go.Scatter(
            x=forecast_data['date'],
            y=[baseline_value] * len(forecast_data),
            mode='lines',
            name='Baseline (Sept 14, 2022)',
            line=dict(color='#000000', width=2)
        ))
        
        # Add risk level zones
        max_discharge = max(forecast_data['discharge_max'].max(), baseline_value * 1.5)
        min_discharge = min(forecast_data['discharge_max'].min(), baseline_value * 0.5)
        
        # High risk zone (> 120% of baseline)
        fig.add_trace(go.Scatter(
            x=forecast_data['date'],
            y=[baseline_value * 1.2] * len(forecast_data),
            mode='lines',
            name='High Risk Threshold',
            line=dict(color='#F44336', width=1, dash='dot'),
            fill=None
        ))
        
        # Medium risk zone (80-120% of baseline)
        fig.add_trace(go.Scatter(
            x=forecast_data['date'],
            y=[baseline_value * 0.8] * len(forecast_data),
            mode='lines',
            name='Low Risk Threshold',
            line=dict(color='#4CAF50', width=1, dash='dot'),
            fill='tonexty',
            fillcolor='rgba(255, 193, 7, 0.1)'
        ))
    
    # Figure layout
    fig.update_layout(
        title=f'7-Day River Discharge Forecast for {lga_name}',
        xaxis_title='Date',
        yaxis_title='Discharge (m³/s)',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=20, r=20, t=50, b=20),
        height=450,
        template='plotly_white',
        hovermode='x unified'
    )
    
    return fig

def determine_risk_level(ratio):
    """Determine risk level based on ratio to baseline"""
    if ratio is None or pd.isna(ratio):
        return "No Data", "#CCCCCC"
    elif ratio <= 0.8:
        return "Low", "#4CAF50"
    elif ratio <= 1.2:
        return "Medium", "#FFC107"
    else:
        return "High", "#F44336"
