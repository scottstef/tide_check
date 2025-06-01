# my_tide_app/services/noaa.py

import requests
import pandas as pd
from datetime import datetime, timedelta, timezone # Keep timezone here for safety, though it's used elsewhere


def get_tide_data(station_id, start_date, end_date, product="predictions", datum="MLLW", time_zone="lst", interval="hilo"):
    """
    Pulls tidal data from the NOAA CO-OPS API.

    Args:
        station_id (str): The 7-character NOAA tide station ID.
        start_date (str): Start date in YYYYMMDD format.
        end_date (str): End date in YYYYMMDD format.
        product (str): Type of data (e.g., "predictions", "high_low").
        datum (str): Tidal datum (e.g., "MLLW", "MSL").
        time_zone (str): Time zone for data (e.g., "lst", "gmt").
        interval (str): Interval for predictions (e.g., "hilo" for high/low, "h" for hourly).

    Returns:
        pandas.DataFrame: A DataFrame containing the tidal data, or None if an error occurs.
    """
    base_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"

    params = {
        "product": product,
        "application": "PythonSharptownTideTracker",
        "station": station_id,
        "begin_date": start_date,
        "end_date": end_date,
        "datum": datum,
        "units": "english",
        "time_zone": time_zone,
        "interval": interval,
        "format": "json"
    }

    try:
        response = requests.get(base_url, params=params, timeout=10) # Added timeout
        response.raise_for_status()
        data = response.json()

        if "predictions" in data:
            df = pd.DataFrame(data["predictions"])
            # FORCE TO BE NAIVE ON CREATION
            df['t'] = pd.to_datetime(df['t'], utc=False).dt.tz_localize(None)
            df.rename(columns={'t': 'datetime', 'v': 'height_ft'}, inplace=True)

            df['height_ft'] = pd.to_numeric(df['height_ft'], errors='coerce')
            df.dropna(subset=['height_ft'], inplace=True)

            if 'type' in df.columns:
                df.rename(columns={'type': 'tide_type'}, inplace=True)
                return df[['datetime', 'tide_type', 'height_ft']]
            else:
                df['tide_type'] = ''
                return df[['datetime', 'tide_type', 'height_ft']]
        elif "data" in data: # This branch is less common for tide predictions but kept for robustness
            df = pd.DataFrame(data["data"])
            # FORCE TO BE NAIVE ON CREATION
            df['t'] = pd.to_datetime(df['t'], utc=False).dt.tz_localize(None)
            df.rename(columns={'t': 'datetime', 'v': 'height_ft'}, inplace=True)
            df['height_ft'] = pd.to_numeric(df['height_ft'], errors='coerce')
            df.dropna(subset=['height_ft'], inplace=True)
            df['tide_type'] = ''
            return df[['datetime', 'height_ft', 'tide_type']]
        else:
            print(f"No tidal data found for station {station_id} with the given parameters.")
            print(f"API Response: {data}")
            return None

    except requests.exceptions.Timeout:
        print(f"Timeout Error: Request to NOAA tide data API timed out after 10 seconds.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e} - Response content: {e.response.text[:500]}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    except ValueError as e:
        print(f"Error parsing JSON: {e}")
        print(f"Response content: {response.text[:500]}")
        return None
