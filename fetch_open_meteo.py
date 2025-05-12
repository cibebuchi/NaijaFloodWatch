# fetch_open_meteo.py
import requests
import pandas as pd

def fetch_open_meteo_forecast(lat, lon, days=7):
    """
    Fetch a multi-day river discharge forecast from Open‑Meteo’s flood API.
    """
    url = (
        f"https://flood-api.open-meteo.com/v1/flood"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=river_discharge_max"
        f"&forecast_days={days}"
        f"&timeformat=iso8601"
    )
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    dates = data["daily"]["time"]
    values = data["daily"]["river_discharge_max"]
    return pd.DataFrame({"date": dates, "discharge_max": values})


def fetch_open_meteo_historical(lat, lon, start_date, end_date=None):
    """
    Fetch observed river discharge for one or a range of dates.
    If end_date is None, it will fetch just start_date.
    """
    if end_date is None:
        end_date = start_date
    url = (
        f"https://flood-api.open-meteo.com/v1/flood"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&daily=river_discharge_max"
        f"&timeformat=iso8601"
    )
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    dates = data["daily"]["time"]
    values = data["daily"]["river_discharge_max"]
    return pd.DataFrame({"date": dates, "discharge_max": values})
