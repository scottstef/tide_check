# my_tide_app/services/geocoding.py

import pandas as pd
import requests
from geopy.geocoders import OpenCage
from geopy.distance import great_circle
import json # Import json for potential file loading/saving in debug

# Import API key from config
from config import OPENCAGE_API_KEY

def get_coordinates_from_zip(zip_code):
    """
    Converts a ZIP code to latitude and longitude using OpenCage Geocoding API.
    """
    if OPENCAGE_API_KEY == "YOUR_OPENCAGE_API_KEY":
        print("WARNING: OpenCage API Key not set. Cannot perform ZIP code lookup.")
        return None, None

    geolocator = OpenCage(OPENCAGE_API_KEY)
    try:
        location = geolocator.geocode(zip_code)
        if location:
            return (location.latitude, location.longitude)
        else:
            print(f"Could not find coordinates for ZIP code: {zip_code}")
            return None, None
    except Exception as e:
        print(f"Error getting coordinates for {zip_code}: {e}")
        return None, None

def get_noaa_tide_stations():
    """
    Fetches a list of all NOAA tide stations with their IDs and coordinates.
    Includes robust error handling and filtering for active stations with valid coordinates.
    """
    stations_url = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
    stations_data = None

    try:
        response = requests.get(stations_url, timeout=10) # Added timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        stations_data = response.json()

        # Debugging prints for initial response structure
        print(f"DEBUG: NOAA API response received. Top-level keys: {list(stations_data.keys())}")
        if 'stations' not in stations_data:
            print("DEBUG: 'stations' key is MISSING from NOAA response. This is unexpected.")
            return None
        if not isinstance(stations_data['stations'], list):
            print("DEBUG: 'stations' value is NOT a list. This is unexpected.")
            return None
        print(f"DEBUG: 'stations' list contains {len(stations_data['stations'])} items.")

        stations_list = []
        total_stations_processed = 0
        active_valid_stations_count = 0

        for station in stations_data['stations']:
            total_stations_processed += 1
            is_active_raw = station.get('active')
            lat_raw = station.get('lat')
            lng_raw = station.get('lng') 

            # A station passes the 'active' check if its 'active' field is explicitly True,
            # OR if its 'active' field is None (as observed in some NOAA data).
            # It only fails if 'active' is explicitly False.
            is_active_pass = (is_active_raw is True) or (is_active_raw is None)

            has_lat = lat_raw is not None
            has_lng = lng_raw is not None
            
            # Debugging prints for individual stations (first few only, if excluded)
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
            print("NOAA API returned data, but no active stations with valid coordinates were found after filtering.")
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
