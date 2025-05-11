import matplotlib.pyplot as plt
import geopandas as gpd
import os
import streamlit as st

@st.cache_data
def create_static_map(shapefile_path):
    """Create a static map of Nigeria using the provided shapefile"""
    try:
        # Read the shapefile
        gdf = gpd.read_file(shapefile_path)
        
        # Ensure the CRS is WGS 84 (EPSG:4326)
        if gdf.crs is None or gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
            
        # Create figure and axes
        fig, ax = plt.subplots(1, 1, figsize=(10, 10))
        
        # Plot the map with light gray boundaries
        gdf.boundary.plot(ax=ax, linewidth=0.5, color='gray')
        
        # Plot the polygons with a light blue color and no edge
        gdf.plot(ax=ax, color='lightblue', alpha=0.5, edgecolor='gray', linewidth=0.1)
        
        # Remove axis
        ax.set_axis_off()
        
        # Add title
        plt.title("Nigeria - Local Government Areas (LGAs)", fontsize=15)
        
        # Adjust figure layout
        plt.tight_layout()
        
        return fig
    except Exception as e:
        st.error(f"Error creating static map: {e}")
        return None