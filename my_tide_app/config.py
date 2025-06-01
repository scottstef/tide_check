# my_tide_app/config.py

import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---

PIRATE_WEATHER_API_KEY = os.environ.get("PIRATE_WEATHER_API_KEY", "PIRATE_WEATHER_API_KEY")
OPENCAGE_API_KEY = os.environ.get("OPENCAGE_API_KEY", "OPENCAGE_API_KEY") 
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "FLASK_SECRET_KEY")


# --- Default Location (Sharptown, MD) ---
DEFAULT_STATION_ID = "8571858"
DEFAULT_STATION_NAME = "Sharptown, Nanticoke River, MD"
DEFAULT_LATITUDE = 38.3970
DEFAULT_LONGITUDE = -75.7600

LOCAL_TIMEZONE = pytz.timezone('America/New_York')
