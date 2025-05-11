import requests
import pandas as pd

def fetch_open_meteo_forecast(lat, lon, days=7):
    url = f"https://flood-api.open-meteo.com/v1/flood?latitude={lat}&longitude={lon}&daily=river_discharge_max&forecast_days={days}&timeformat=iso8601"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    dates = data["daily"]["time"]
    values = data["daily"]["river_discharge_max"]
    df = pd.DataFrame({"date": dates, "discharge_max": values})
    return df

def fetch_open_meteo_historical(lat, lon, date):
    url = f"https://flood-api.open-meteo.com/v1/flood?latitude={lat}&longitude={lon}&daily=river_discharge_max&start_date={date}&end_date={date}&timeformat=iso8601"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    dates = data["daily"]["time"]
    values = data["daily"]["river_discharge_max"]
    df = pd.DataFrame({"date": dates, "discharge_max": values})
    return df