import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import json
import pytz
from geopy.geocoders import OpenCage # New Import
from geopy.distance import great_circle # New Import

# --- API Keys ---

PIRATE_WEATHER_API_KEY = "lmTROGhlgrRkf7IzzTOm37PcyPg4xKoK" # Your actual API key goes here
if PIRATE_WEATHER_API_KEY == "YOUR_PIRATE_WEATHER_API_KEY":
    print("WARNING: Please replace 'YOUR_PIRATE_WEATHER_API_KEY' with your actual API key from pirate-weather.apiable.io to get weather data.")

OPENCAGE_API_KEY = "455daa915a4744acb649dc96f6f4a4d6" # Your actual OpenCage API key goes here
if OPENCAGE_API_KEY == "YOUR_OPENCAGE_API_KEY":
    print("WARNING: Please replace 'YOUR_OPENCAGE_API_KEY' with your actual OpenCage API key to use ZIP code search.")


# Define the local timezone (used for all output and calculations)
LOCAL_TIMEZONE = pytz.timezone('America/New_York')

# Define the date range (e.g., today and the next two days for a good plot)
today = datetime.now()
end_date = today + timedelta(days=2) # Get data for today and the next two days
start_date_str = today.strftime("%Y%m%d")
end_date_str = end_date.strftime("%Y%m%d")


#ZIP Code to Station Search
def get_coordinates_from_zip(zip_code, api_key):
    """
    Converts a ZIP code to latitude and longitude using OpenCage Geocoding API.
    """
    geolocator = OpenCage(api_key)
    try:
        # REMOVED 'countrycode="us"' as it causes an error with your geopy version
        location = geolocator.geocode(zip_code)
        if location:
            return (location.latitude, location.longitude)
        else:
            print(f"Could not find coordinates for ZIP code: {zip_code}")
            return None
    except Exception as e:
        print(f"Error getting coordinates for {zip_code}: {e}")
        return None

def find_closest_station(target_lat, target_lon, all_stations_df):
    """
    Finds the closest NOAA tide station to a given latitude and longitude.

    Args:
        target_lat (float): Latitude of the target location.
        target_lon (float): Longitude of the target location.
        all_stations_df (pd.DataFrame): DataFrame containing NOAA station data
                                        with 'id', 'name', 'lat', 'lon' columns.

    Returns:
        tuple: (station_id, station_name, station_lat, station_lon) of the closest station,
               or (None, None, None, None) if no stations are available.
    """
    if all_stations_df is None or all_stations_df.empty:
        print("No NOAA stations available to find the closest one.")
        return None, None, None, None

    target_coords = (target_lat, target_lon)
    
    closest_station = None
    min_distance = float('inf')

    # Convert DataFrame to a list of tuples for efficient iteration
    # This avoids repeated .iterrows() which can be slow for large DFs
    # And ensures we're only working with the necessary columns
    station_records = all_stations_df[['id', 'name', 'lat', 'lon']].to_records(index=False)

    for record in station_records:
        station_id, station_name, station_lat, station_lon = record
        
        station_coords = (station_lat, station_lon)
        distance = great_circle(target_coords, station_coords).miles # Distance in miles

        if distance < min_distance:
            min_distance = distance
            closest_station = (station_id, station_name, station_lat, station_lon)

    if closest_station:
        print(f"DEBUG: Closest station found: {closest_station[1]} (ID: {closest_station[0]}) at {min_distance:.2f} miles.")
        return closest_station
    else:
        print("No closest station could be determined.")
        return None, None, None, None
    
def get_noaa_tide_stations():
    """
    Fetches a list of all NOAA tide stations with their IDs and coordinates.
    """
    stations_url = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
    try:
        response = requests.get(stations_url, timeout=10)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        stations_data = response.json()

        stations_list = []
        
        # --- DEBUGGING PRINTS ---
        print(f"DEBUG: NOAA API response received. Top-level keys: {list(stations_data.keys())}")
        if 'stations' not in stations_data:
            print("DEBUG: 'stations' key is MISSING from NOAA response. This is unexpected.")
            return None
        if not isinstance(stations_data['stations'], list):
            print("DEBUG: 'stations' value is NOT a list. This is unexpected.")
            return None
        print(f"DEBUG: 'stations' list contains {len(stations_data['stations'])} items.")
        # --- END DEBUGGING PRINTS ---

        total_stations_processed = 0
        active_valid_stations_count = 0

        for station in stations_data['stations']:
            total_stations_processed += 1
            is_active_raw = station.get('active') # Get raw value
            lat_raw = station.get('lat')
            lng_raw = station.get('lng') # Use lng as confirmed

            # --- CRITICAL FIX: Modified logic for 'is_active_pass' ---
            # A station passes the 'active' check if its 'active' field is explicitly True,
            # OR if its 'active' field is None (as observed in the truncated data).
            # It only fails if 'active' is explicitly False.
            is_active_pass = (is_active_raw is True) or (is_active_raw is None)

            has_lat = lat_raw is not None
            has_lng = lng_raw is not None

            # Debugging prints for a few problematic stations (first 5 and last 5)
            # This print statement is only triggered if the station IS BEING EXCLUDED.
            if not (is_active_pass and has_lat and has_lng):
                if total_stations_processed <= 5 or total_stations_processed > len(stations_data['stations']) - 5:
                    print(f"DEBUG: Station {station.get('id', 'N/A')}: Active={is_active_raw} (Pass:{is_active_pass}), Lat={lat_raw} (Valid:{has_lat}), Lng={lng_raw} (Valid:{has_lng}) - Excluded.")

            if is_active_pass and has_lat and has_lng:
                active_valid_stations_count += 1
                stations_list.append({
                    'id': station['id'],
                    'name': station['name'],
                    'lat': lat_raw,
                    'lon': lng_raw # Store as 'lon' in DataFrame for consistency with geopy/elsewhere
                })

        print(f"DEBUG: Finished processing stations. Total processed: {total_stations_processed}, Included in list: {active_valid_stations_count}")

        if not stations_list:
            print("NOAA API returned data, but no active stations with valid coordinates were found.")
            return None
        return pd.DataFrame(stations_list)

    except requests.exceptions.Timeout:
        print(f"Timeout Error: Request to NOAA station list API timed out after 10 seconds.")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error fetching NOAA stations: {e} - Response content: {e.text[:500]}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error fetching NOAA stations: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"An unknown error occurred while fetching NOAA stations: {e}")
        return None
    except ValueError as e: # Catch JSON decoding errors
        print(f"Error parsing JSON from NOAA station list: {e}")
        print(f"Problematic response content (first 500 chars): {response.text[:500]}")
        return None
    
# Set default values to Sharptown, MD
your_station_id = "8571858"
station_name = "Sharptown, Nanticoke River, MD"
sharptown_latitude = 38.3970
sharptown_longitude = -75.7600

# Attempt to find station via ZIP code if API key is provided
if OPENCAGE_API_KEY != "YOUR_OPENCAGE_API_KEY":
    zip_code_input = input("Enter a ZIP code to find the closest tide station (e.g., 21871 for Sharptown, MD): ")
    if zip_code_input:
        print(f"Searching for closest tide station to ZIP code {zip_code_input}...")
        target_lat, target_lon = get_coordinates_from_zip(zip_code_input, OPENCAGE_API_KEY)

        if target_lat is not None and target_lon is not None:
            all_noaa_stations = get_noaa_tide_stations()
            if all_noaa_stations is not None:
                found_id, found_name, found_lat, found_lon = \
                    find_closest_station(target_lat, target_lon, all_noaa_stations)

                if found_id: # If a station was successfully found
                    your_station_id = found_id
                    station_name = found_name
                    sharptown_latitude = found_lat
                    sharptown_longitude = found_lon
                    print(f"Closest station found: {station_name} (ID: {your_station_id}) at Lat: {sharptown_latitude:.4f}, Lon: {sharptown_longitude:.4f}")
                else:
                    print("Could not find a closest station. Using default Sharptown, MD station.")
            else:
                print("Failed to retrieve NOAA station list. Using default Sharptown, MD station.")
        else:
            print("Failed to convert ZIP code to coordinates. Using default Sharptown, MD station.")
    else:
        print("No ZIP code entered. Using default Sharptown, MD station.")
else:
    print("\nNo OpenCage API Key provided. Using default Sharptown, MD station.")

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
        "units": "english",  # or "metric"
        "time_zone": time_zone,
        "interval": interval,
        "format": "json"
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        if "predictions" in data:
            df = pd.DataFrame(data["predictions"])
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
        elif "data" in data:
            df = pd.DataFrame(data["data"])
            df['t'] = pd.to_datetime(df['t'])
            # --- NEW ROBUST FIX: Strip timezone information if it exists ---
            if df['t'].dt.tz is not None:
                df['t'] = df['t'].dt.tz_localize(None)
            # --- END NEW ROBUST FIX ---
            df.rename(columns={'t': 'datetime', 'v': 'height_ft'}, inplace=True)
            df['height_ft'] = pd.to_numeric(df['height_ft'], errors='coerce')
            df.dropna(subset=['height_ft'], inplace=True)
            df['tide_type'] = ''
            return df[['datetime', 'height_ft', 'tide_type']]
        else:
            print(f"No tidal data found for station {station_id} with the given parameters.")
            print(f"API Response: {data}")
            return None

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response content: {response.text}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {e}")
        return None
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
    except ValueError as e:
        print(f"Error parsing JSON: {e}")
        print(f"Response content: {response.text}")
        return None

def get_pirate_weather_report(api_key, latitude, longitude, time_unix=None, units="us"):
    """
    Pulls weather data from the Pirate Weather API.
    If time_unix is provided, gets data for that specific time (historical/current).
    If time_unix is None, gets the current forecast (including hourly/daily data).

    Args:
        api_key (str): Your Pirate Weather API key.
        latitude (float): Latitude of the location.
        longitude (float): Longitude of the location.
        time_unix (int, optional): Unix timestamp for the desired weather report. Defaults to None.
                                  If None, a general forecast including hourly/daily data is retrieved.
        units (str): Units for the weather data (e.g., "us", "si", "ca", "uk").

    Returns:
        dict: A dictionary containing the weather data, or None if an error occurs.
    """
    if time_unix is None:
        # This endpoint returns current, minutely, hourly, and daily data for the location
        url = f"https://api.pirateweather.net/forecast/{api_key}/{latitude},{longitude}"
        # We generally want hourly and daily, so exclude only minutely and flags
        params = {"units": units, "exclude": "minutely,alerts,flags"}
    else:
        # This endpoint is for specific historical or very recent past/current time lookups.
        # Future times with this specific timestamp endpoint cause the "Requested Time is in the Future" error.
        url = f"https://api.pirateweather.net/forecast/{api_key}/{latitude},{longitude},{time_unix}"
        # For a specific time, we primarily want the 'currently' block
        params = {"units": units, "exclude": "minutely,hourly,daily,alerts,flags"}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.HTTPError as e:
        print(f"Pirate Weather HTTP Error: {e}")
        print(f"Pirate Weather Response content: {response.text}")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"Pirate Weather Connection Error: {e}")
        return None
    except requests.exceptions.Timeout as e:
        print(f"Pirate Weather Timeout Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"An error occurred with Pirate Weather: {e}")
        return None
    except ValueError as e:
        print(f"Error parsing Pirate Weather JSON: {e}")
        print(f"Pirate Weather Response content: {response.text}")
        return None

# %%
# --- Get High/Low Tide Predictions (for labeling points on graph and weather lookup) ---
print(f"Fetching high/low tide predictions for {station_name} from {start_date_str} to {end_date_str}...")
hilo_tide_predictions_df = get_tide_data(
    station_id=your_station_id,
    start_date=start_date_str,
    end_date=end_date_str,
    product="predictions",
    datum="MLLW",
    time_zone="lst",
    interval="hilo"
)

# --- Get Hourly Tide Predictions (not needed for text output, but keeping if you process it later) ---
print(f"\nFetching hourly tide predictions for {station_name} from {start_date_str} to {end_date_str} (optional, for processing)...")
hourly_predictions_df = get_tide_data(
    station_id=your_station_id,
    start_date=start_date_str,
    end_date=end_date_str,
    product="predictions",
    datum="MLLW",
    time_zone="lst",
    interval="h"
)

# --- Safeguard: Ensure datetime columns are naive before localizing ---
if hilo_tide_predictions_df is not None:
    if hilo_tide_predictions_df['datetime'].dt.tz is not None:
        print("DEBUG: hilo_tide_predictions_df 'datetime' column found to be tz-aware upon return. Stripping timezone.")
        hilo_tide_predictions_df['datetime'] = hilo_tide_predictions_df['datetime'].dt.tz_localize(None)
    hilo_tide_predictions_df['datetime'] = hilo_tide_predictions_df['datetime'].dt.tz_localize(LOCAL_TIMEZONE, ambiguous='infer', nonexistent='shift_forward')


if hourly_predictions_df is not None:
    if hourly_predictions_df['datetime'].dt.tz is not None:
        print("DEBUG: hourly_predictions_df 'datetime' column found to be tz-aware upon return. Stripping timezone.")
        hourly_predictions_df['datetime'] = hourly_predictions_df['datetime'].dt.tz_localize(None)
    hourly_predictions_df['datetime'] = hourly_predictions_df['datetime'].dt.tz_localize(LOCAL_TIMEZONE, ambiguous='infer', nonexistent='shift_forward')


# --- Process and Display Tide Predictions (Text Output) ---
if hilo_tide_predictions_df is not None:
    print(f"\n--- High and Low Tide Predictions for {station_name} ---")
    print(hilo_tide_predictions_df.to_string(index=False))

    current_time = datetime.now(LOCAL_TIMEZONE)
    future_tides = hilo_tide_predictions_df[hilo_tide_predictions_df['datetime'] > current_time].copy()

    # --- Get Weather Reports for High Tides ---
    print("\n--- Pirate Weather Reports for High Tides ---")
    if PIRATE_WEATHER_API_KEY != "YOUR_PIRATE_WEATHER_API_KEY":
        print("Fetching general Pirate Weather forecast for the period...")
        general_weather_forecast = get_pirate_weather_report(
            PIRATE_WEATHER_API_KEY,
            sharptown_latitude,
            sharptown_longitude,
            time_unix=None
        )

        if general_weather_forecast and 'hourly' in general_weather_forecast and 'data' in general_weather_forecast['hourly']:
            hourly_weather_data = general_weather_forecast['hourly']['data']
            weather_df = pd.DataFrame(hourly_weather_data)
            weather_df['time'] = pd.to_datetime(weather_df['time'], unit='s', utc=True)
            weather_df['time'] = weather_df['time'].dt.tz_convert(LOCAL_TIMEZONE)

            if not future_tides.empty:
                high_tides_for_weather = future_tides[future_tides['tide_type'] == 'H']
                if not high_tides_for_weather.empty:
                    for index, row in high_tides_for_weather.iterrows():
                        tide_time = row['datetime']

                        closest_weather_idx = (weather_df['time'] - tide_time).abs().idxmin()
                        closest_weather = weather_df.loc[closest_weather_idx]

                        print(f"\nWeather at High Tide ({tide_time.strftime('%Y-%m-%d %I:%M %p %Z')}):")
                        if abs(closest_weather['time'] - tide_time) <= timedelta(hours=1):
                            print(f"  (Matched to forecast for {closest_weather['time'].strftime('%Y-%m-%d %I:%M %p %Z')})")
                            print(f"  Summary: {closest_weather.get('summary', 'N/A')}")
                            print(f"  Temperature: {closest_weather.get('temperature', 'N/A')}°F")
                            print(f"  Feels Like: {closest_weather.get('apparentTemperature', 'N/A')}°F")
                            print(f"  Precipitation Probability: {closest_weather.get('precipProbability', 'N/A') * 100:.0f}%")
                            print(f"  Wind Speed: {closest_weather.get('windSpeed', 'N/A')} mph")
                            print(f"  Humidity: {closest_weather.get('humidity', 'N/A') * 100:.0f}%")
                            print(f"  Pressure: {closest_weather.get('pressure', 'N/A')} mb")
                            print(f"  Dew Point: {closest_weather.get('dewPoint', 'N/A')}°F")
                            print(f"  Visibility: {closest_weather.get('visibility', 'N/A')} miles")
                        else:
                            print(f"  No sufficiently close hourly forecast data found for this high tide.")
                            print(f"  Closest forecast available is for {closest_weather['time'].strftime('%Y-%m-%d %I:%M %p %Z')}")

                else:
                    print("No future High Tides found to fetch weather for.")
            else:
                print("No future tides to fetch weather for.")
        else:
            print("Could not retrieve general weather forecast or hourly data from Pirate Weather.")
            if general_weather_forecast:
                print(f"Pirate Weather API Response (Partial): {list(general_weather_forecast.keys())}")
            else:
                print("General weather forecast retrieval failed.")
    else:
        print("Skipping Pirate Weather requests. Please provide your API key.")


    # --- Find and Display Next High/Low Tide (Text Output, after weather) ---
    if not future_tides.empty:
        if not future_tides[future_tides['tide_type'] == 'H'].empty:
            next_high_tide = future_tides[future_tides['tide_type'] == 'H'].sort_values(by='datetime').iloc[0]
            if pd.notna(next_high_tide['height_ft']):
                print(f"\nNext High Tide: {next_high_tide['datetime'].strftime('%Y-%m-%d %I:%M %p %Z')} (Height: {next_high_tide['height_ft']:.2f} ft)")
            else:
                print(f"\nNext High Tide: {next_high_tide['datetime'].strftime('%Y-%m-%d %I:%M %p %Z')} (Height: N/A ft)")
        else:
            print("\nNo future High Tides found in the data.")

        if not future_tides[future_tides['tide_type'] == 'L'].empty:
            next_low_tide = future_tides[future_tides['tide_type'] == 'L'].sort_values(by='datetime').iloc[0]
            if pd.notna(next_low_tide['height_ft']):
                print(f"Next Low Tide: {next_low_tide['datetime'].strftime('%Y-%m-%d %I:%M %p %Z')} (Height: {next_low_tide['height_ft']:.2f} ft)")
            else:
                print(f"Next Low Tide: {next_low_tide['datetime'].strftime('%Y-%m-%d %I:%M %p %Z')} (Height: N/A ft)")
        else:
            print("No future Low Tides found in the data.")
    else:
        print("\nNo future tide predictions available for the specified date range.")
else:
    print("Failed to retrieve high/low tide data for text output.")

