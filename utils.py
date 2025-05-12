# utils.py
import pandas as pd
import streamlit as st
import json
from shapely.geometry import shape
import plotly.graph_objects as go

@st.cache_data
def load_lga_gdf(path):
    """Load and process LGA GeoJSON data without Fiona or GeoPandas"""
    try:
        with open(path, 'r') as f:
            data = json.load(f)

        features = data['features']
        rows = []

        for feature in features:
            props = feature['properties']
            geom = shape(feature['geometry'])
            centroid = geom.centroid

            lga = props.get('ADM2_NAME') or props.get('NAME_2') or props.get('NAME') or props.get('LGA_NAME') or 'Unknown'
            state = props.get('NAME_1', 'Unknown')

            rows.append({
                'LGA': lga,
                'State': state,
                'lat': centroid.y,
                'lon': centroid.x,
                'geometry': feature['geometry']
            })

        return pd.DataFrame(rows)

    except Exception as e:
        st.error(f"Error loading GeoJSON: {e}")
        return None

@st.cache_data
def load_baseline(path):
    """Load baseline discharge values from CSV"""
    try:
        df = pd.read_csv(path)
        return df.set_index('LGA')['baseline'].to_dict()
    except Exception as e:
        st.error(f"Error loading baseline data: {e}")
        return {}

def create_choropleth_map(gdf, data_column, title):
    """Placeholder for choropleth map (not used)"""
    return None

def generate_time_series_chart(forecast_data, lga, baseline):
    """Generate a Plotly time series chart for forecast data"""
    try:
        if forecast_data is None or forecast_data.empty:
            return None
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=forecast_data['date'],
            y=forecast_data['discharge_max'],
            mode='lines+markers',
            name='Forecast Discharge'
        ))
        if baseline:
            fig.add_trace(go.Scatter(
                x=forecast_data['date'],
                y=[baseline] * len(forecast_data),
                mode='lines',
                name='Baseline',
                line=dict(dash='dash')
            ))
        fig.update_layout(
            title=f"7-Day Forecast for {lga}",
            xaxis_title='Date',
            yaxis_title='Discharge (m³/s)',
            hovermode='x unified'
        )
        return fig
    except Exception as e:
        st.error(f"Error generating time series chart: {e}")
        return None

def determine_risk_level(ratio):
    """Determine flood risk level based on discharge ratio"""
    try:
        if ratio is None:
            return "N/A", "#f7f7f7"
        if ratio <= 0.8:
            return "Low", "#4CAF50"
        elif ratio <= 1.2:
            return "Medium", "#FFC107"
        else:
            return "High", "#F44336"
    except Exception as e:
        st.error(f"Error determining risk level: {e}")
        return "N/A", "#f7f7f7"