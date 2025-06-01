# my_tide_app/services/pirate_weather.py

import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# Import API key from config
from config import PIRATE_WEATHER_API_KEY

def get_pirate_weather_report(latitude, longitude, time_unix=None, units="us"):
    """
    Pulls weather data from the Pirate Weather API.
    If time_unix is provided, gets data for that specific time (historical/current).
    If time_unix is None, gets the current forecast (including hourly/daily data).

    Args:
        latitude (float): Latitude of the location.
        longitude (float): Longitude of the location.
        time_unix (int, optional): Unix timestamp for the desired weather report. Defaults to None.
                                  If None, a general forecast including hourly/daily data is retrieved.
        units (str): Units for the weather data (e.g., "us", "si", "ca", "uk").

    Returns:
        dict: A dictionary containing the weather data, or None if an error occurs.
    """
    if PIRATE_WEATHER_API_KEY == "YOUR_PIRATE_WEATHER_API_KEY":
        print("WARNING: Pirate Weather API Key not set. Cannot fetch weather data.")
        return None

    if time_unix is None:
        url = f"https://api.pirateweather.net/forecast/{PIRATE_WEATHER_API_KEY}/{latitude},{longitude}"
        params = {"units": units, "exclude": "minutely,alerts,flags"}
    else:
        url = f"https://api.pirateweather.net/forecast/{PIRATE_WEATHER_API_KEY}/{latitude},{longitude},{time_unix}"
        params = {"units": units, "exclude": "minutely,hourly,daily,alerts,flags"}

    try:
        response = requests.get(url, params=params, timeout=10) # Added timeout
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.Timeout:
        print(f"Pirate Weather Timeout Error: Request timed out after 10 seconds.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"Pirate Weather HTTP Error: {e} - Response content: {e.response.text[:500]}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"Pirate Weather Connection Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred with Pirate Weather: {e}")
        return None
    except ValueError as e:
        print(f"Error parsing Pirate Weather JSON: {e}")
        print(f"Pirate Weather Response content: {response.text[:500]}")
        return None
