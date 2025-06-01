# my_tide_app/app.py

from flask import Flask, render_template, request, flash, redirect, url_for
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
import pytz

# Import configurations and services
from config import (
    PIRATE_WEATHER_API_KEY, OPENCAGE_API_KEY, SECRET_KEY,
    DEFAULT_STATION_ID, DEFAULT_STATION_NAME,
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE,
    LOCAL_TIMEZONE
)
from services.geocoding import get_coordinates_from_zip, get_noaa_tide_stations, find_closest_station
from services.noaa import get_tide_data
from services.pirate_weather import get_pirate_weather_report

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Helper function to get weather icon (using emojis for simplicity)
def get_weather_icon(summary):
    summary = summary.lower()
    if 'clear' in summary or 'sun' in summary:
        return '☀️' # Sun emoji
    elif 'partly cloudy' in summary:
        return '⛅' # Partly cloudy emoji
    elif 'cloudy' in summary:
        return '☁️' # Cloud emoji
    elif 'rain' in summary or 'drizzle' in summary:
        return '🌧️' # Rain cloud emoji
    elif 'snow' in summary or 'flurries' in summary:
        return '❄️' # Snowflake emoji
    elif 'thunder' in summary or 'storm' in summary:
        return '⛈️' # Thundercloud and rain emoji
    elif 'wind' in summary:
        return '🌬️' # Wind face emoji
    elif 'no forecast' in summary: # Handle the new 'No forecast' case
        return '🚫' # No entry sign
    else:
        return '❓' # Question mark for unknown

@app.route('/', methods=['GET', 'POST'])
def index():
    station_id = DEFAULT_STATION_ID
    station_name = DEFAULT_STATION_NAME
    current_latitude = DEFAULT_LATITUDE
    current_longitude = DEFAULT_LONGITUDE
    
    # Initialize variables for template rendering
    combined_forecast_data = [] # This will be a list of dicts for the table
    next_tide_info = ""
    
    if request.method == 'POST':
        zip_code_input = request.form.get('zip_code')
        if zip_code_input:
            if OPENCAGE_API_KEY == "YOUR_OPENCAGE_API_KEY":
                flash("OpenCage API Key not set. Cannot perform ZIP code lookup. Using default Sharptown, MD.", "warning")
            else:
                target_lat, target_lon = get_coordinates_from_zip(zip_code_input)

                if target_lat is not None and target_lon is not None:
                    all_noaa_stations = get_noaa_tide_stations()
                    if all_noaa_stations is not None:
                        found_id, found_name, found_lat, found_lon = \
                            find_closest_station(target_lat, target_lon, all_noaa_stations)

                        if found_id:
                            station_id = found_id
                            station_name = found_name
                            current_latitude = found_lat
                            current_longitude = found_lon
                            flash(f"Closest station found to {zip_code_input}: {station_name} (ID: {station_id}) at Lat: {current_latitude:.4f}, Lon: {current_longitude:.4f}", "info")
                        else:
                            flash("Could not find a closest station. Using default Sharptown, MD station.", "warning")
                    else:
                        flash("Failed to retrieve NOAA station list. Using default Sharptown, MD station.", "warning")
                else:
                    flash("Failed to convert ZIP code to coordinates. Using default Sharptown, MD station.", "warning")
        else:
            flash("No ZIP code entered. Using default Sharptown, MD station.", "info")

    # --- Date Range for API Calls ---
    today_date = datetime.now(LOCAL_TIMEZONE)
    end_date = today_date + timedelta(days=2) # Get data for today and the next two days
    start_date_str = today_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")

    # --- Get Tide Predictions (Hourly and High/Low) ---
    hourly_predictions_df = get_tide_data(
        station_id=station_id,
        start_date=start_date_str,
        end_date=end_date_str,
        product="predictions",
        datum="MLLW",
        time_zone="lst",
        interval="h" # Request hourly predictions
    )

    hilo_tide_predictions_df = get_tide_data(
        station_id=station_id,
        start_date=start_date_str,
        end_date=end_date_str,
        product="predictions",
        datum="MLLW",
        time_zone="lst",
        interval="hilo" # Request high/low predictions
    )

    # --- Localize Tide Data ---
    if hourly_predictions_df is not None:
        if hourly_predictions_df['datetime'].dt.tz is not None:
            hourly_predictions_df['datetime'] = hourly_predictions_df['datetime'].dt.tz_localize(None)
        hourly_predictions_df['datetime'] = hourly_predictions_df['datetime'].dt.tz_localize(LOCAL_TIMEZONE, ambiguous='infer', nonexistent='shift_forward')
    
    if hilo_tide_predictions_df is not None:
        if hilo_tide_predictions_df['datetime'].dt.tz is not None:
            hilo_tide_predictions_df['datetime'] = hilo_tide_predictions_df['datetime'].dt.tz_localize(None)
        hilo_tide_predictions_df['datetime'] = hilo_tide_predictions_df['datetime'].dt.tz_localize(LOCAL_TIMEZONE, ambiguous='infer', nonexistent='shift_forward')

    # --- Get General Weather Forecast ---
    weather_df = pd.DataFrame() # Initialize empty DataFrame
    if PIRATE_WEATHER_API_KEY != "YOUR_PIRATE_WEATHER_API_KEY":
        general_weather_forecast = get_pirate_weather_report(
            current_latitude,
            current_longitude,
            time_unix=None # Request general forecast
        )
        if general_weather_forecast and 'hourly' in general_weather_forecast and 'data' in general_weather_forecast['hourly']:
            hourly_weather_data = general_weather_forecast['hourly']['data']
            weather_df = pd.DataFrame(hourly_weather_data)
            weather_df['time'] = pd.to_datetime(weather_df['time'], unit='s', utc=True)
            weather_df['time'] = weather_df['time'].dt.tz_convert(LOCAL_TIMEZONE)
            # Rename for consistency
            weather_df.rename(columns={'time': 'datetime', 'summary': 'weather_summary',
                                       'temperature': 'temp_f', 'apparentTemperature': 'feels_like_f',
                                       'precipProbability': 'precip_prob', 'windSpeed': 'wind_speed_mph',
                                       'humidity': 'humidity_percent', 'pressure': 'pressure_mb',
                                       'dewPoint': 'dew_point_f', 'visibility': 'visibility_miles'}, inplace=True)
            # Convert percentage fields
            weather_df['precip_prob'] = weather_df['precip_prob'] * 100
            weather_df['humidity_percent'] = weather_df['humidity_percent'] * 100
        else:
            flash("Could not retrieve general weather forecast or hourly data from Pirate Weather.", "warning")
    else:
        flash("Skipping Pirate Weather requests. Please provide your API key.", "warning")

    # --- Prepare Combined Data for Template ---
    if hourly_predictions_df is not None:
        # Create a list of all relevant tide events (hourly and high/low)
        all_tide_events = []
        if hourly_predictions_df is not None:
            for idx, row in hourly_predictions_df.iterrows():
                all_tide_events.append({
                    'datetime': row['datetime'],
                    'height_ft': row['height_ft'],
                    'type': 'hourly',
                    'tide_type_hilo': None # Not a specific H/L event
                })
        
        if hilo_tide_predictions_df is not None:
            for idx, row in hilo_tide_predictions_df.iterrows():
                all_tide_events.append({
                    'datetime': row['datetime'],
                    'height_ft': row['height_ft'],
                    'type': f"{row['tide_type'].lower()}_tide", # 'h_tide' or 'l_tide'
                    'tide_type_hilo': row['tide_type'] # 'H' or 'L'
                })
        
        # Sort all events by datetime
        all_tide_events.sort(key=lambda x: x['datetime'])

        # Build the final display data list
        row_counter = 0
        for event in all_tide_events:
            event_datetime = event['datetime']
            event_type = event['type']
            event_height = event['height_ft']
            tide_type_hilo = event['tide_type_hilo']

            # Find closest weather data for this event
            weather_summary = 'N/A'
            temp_f = np.nan
            precip_prob = np.nan
            wind_speed_mph = np.nan
            humidity_percent = np.nan
            weather_icon = '❓' # Default icon for unknown/no data

            if not weather_df.empty:
                # Check if event_datetime is within the range of available weather data
                if weather_df['datetime'].min() <= event_datetime <= weather_df['datetime'].max():
                    time_diff = (weather_df['datetime'] - event_datetime).abs()
                    closest_weather_idx = time_diff.idxmin()
                    closest_weather = weather_df.loc[closest_weather_idx]
                    
                    # Only use weather if it's reasonably close (e.g., within 30 minutes)
                    if time_diff.loc[closest_weather_idx] <= timedelta(minutes=30):
                        weather_summary = closest_weather.get('weather_summary', 'N/A')
                        temp_f = closest_weather.get('temp_f', np.nan)
                        precip_prob = closest_weather.get('precip_prob', np.nan)
                        wind_speed_mph = closest_weather.get('wind_speed_mph', np.nan)
                        humidity_percent = closest_weather.get('humidity_percent', np.nan)
                        weather_icon = get_weather_icon(weather_summary)
                    else:
                        # Closest weather is too far, treat as no forecast for this specific point
                        weather_summary = 'No forecast'
                        weather_icon = get_weather_icon(weather_summary) # Will return '🚫'
                else:
                    # Event datetime is outside the entire weather forecast range
                    weather_summary = 'No forecast'
                    weather_icon = get_weather_icon(weather_summary) # Will return '🚫'
            else:
                # No weather data was retrieved at all
                weather_summary = 'No forecast'
                weather_icon = get_weather_icon(weather_summary) # Will return '🚫'


            # Determine row class for styling
            row_class = ""
            if event_type == 'h_tide':
                row_class = "row-high-tide"
            elif event_type == 'l_tide':
                row_class = "row-low-tide"
            else: # Hourly tide
                row_class = "row-hourly-odd" if row_counter % 2 == 0 else "row-hourly-even"
                row_counter += 1 # Only increment for hourly rows to maintain alternating pattern

            combined_forecast_data.append({
                'Time': event_datetime.strftime('%Y-%m-%d %I:%M %p %Z'),
                'Tide_Event': tide_type_hilo if tide_type_hilo else '',
                'Tide_Height': f"{event_height:.2f} ft" if pd.notna(event_height) else '',
                'Weather_Icon': weather_icon,
                'Weather_Summary': weather_summary,
                'Temp': f"{temp_f:.1f}°F" if pd.notna(temp_f) else '',
                'Precip_Prob': f"{precip_prob:.0f}%" if pd.notna(precip_prob) else '',
                'Wind': f"{wind_speed_mph:.1f} mph" if pd.notna(wind_speed_mph) else '',
                'Humidity': f"{humidity_percent:.0f}%" if pd.notna(humidity_percent) else '',
                'row_class': row_class
            })
        
        if not combined_forecast_data:
            flash("No combined tide and weather forecast data available for the specified date range.", "info")

        # Determine next high/low tide for display (separate from the main table)
        current_time_for_comparison = datetime.now(LOCAL_TIMEZONE)
        future_tides = hilo_tide_predictions_df[hilo_tide_predictions_df['datetime'] > current_time_for_comparison].copy()
        
        if not future_tides.empty:
            next_high_tide = future_tides[future_tides['tide_type'] == 'H'].sort_values(by='datetime').iloc[0] if not future_tides[future_tides['tide_type'] == 'H'].empty else None
            next_low_tide = future_tides[future_tides['tide_type'] == 'L'].sort_values(by='datetime').iloc[0] if not future_tides[future_tides['tide_type'] == 'L'].empty else None

            if next_high_tide is not None:
                next_tide_info += f"<p><strong>Next High Tide:</strong> {next_high_tide['datetime'].strftime('%Y-%m-%d %I:%M %p %Z')} (Height: {next_high_tide['height_ft']:.2f} ft)</p>"
            if next_low_tide is not None:
                next_tide_info += f"<p><strong>Next Low Tide:</strong> {next_low_tide['datetime'].strftime('%Y-%m-%d %I:%M %p %Z')} (Height: {next_low_tide['height_ft']:.2f} ft)</p>"
        else:
            next_tide_info = "<p>No future high/low tide predictions available for the specified date range.</p>"

    else:
        flash("Failed to retrieve hourly tide data. Cannot generate combined forecast.", "error")

    return render_template(
        'index.html',
        station_name=station_name,
        combined_forecast_data=combined_forecast_data, # Pass the list of dicts
        next_tide_info=next_tide_info
    )

if __name__ == '__main__':
    app.run(debug=True)
