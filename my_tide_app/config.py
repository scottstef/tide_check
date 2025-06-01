# my_tide_app/config.py

import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv # For loading secrets from .env file
import boto3
from botocore.exceptions import ClientError
import json
import sys

# Load environment variables from .env file (for local development fallback)
load_dotenv()


# Get AWS region from environment variable (passed to Docker container)
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Define your secret names matching what you uploaded with upload_secrets.py
SECRETS_MANAGER_PREFIX = "my-tide-app/" # Must match the prefix used in upload_secrets.py
PIRATE_WEATHER_SECRET_NAME = f"{SECRETS_MANAGER_PREFIX}PIRATE_WEATHER_API_KEY"
OPENCAGE_SECRET_NAME = f"{SECRETS_MANAGER_PREFIX}OPENCAGE_API_KEY"
FLASK_SECRET_KEY_NAME = f"{SECRETS_MANAGER_PREFIX}FLASK_SECRET_KEY"

# Function to get secret from AWS Secrets Manager
def get_secret_from_secrets_manager(secret_name, region_name):
    """
    Retrieves a secret from AWS Secrets Manager.
    """
    try:
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )

        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        print(f"Error fetching secret '{secret_name}' from Secrets Manager: {e}", file=sys.stderr)
        return None # Return None if there's an error
    else:
        if 'SecretString' in get_secret_value_response:
            return get_secret_value_response['SecretString']
        else:
            # For binary secrets, decode to utf-8
            return get_secret_value_response['SecretBinary'].decode('utf-8')

# Attempt to fetch from Secrets Manager first, then fallback to environment variables
PIRATE_WEATHER_API_KEY = get_secret_from_secrets_manager(PIRATE_WEATHER_SECRET_NAME, AWS_REGION)
if PIRATE_WEATHER_API_KEY is None:
    PIRATE_WEATHER_API_KEY = os.environ.get("PIRATE_WEATHER_API_KEY", "YOUR_PIRATE_WEATHER_API_KEY_DEFAULT")
    print(f"PIRATE_WEATHER_API_KEY loaded from environment variable or default.", file=sys.stderr)
else:
    print(f"PIRATE_WEATHER_API_KEY loaded from AWS Secrets Manager.", file=sys.stderr)


OPENCAGE_API_KEY = get_secret_from_secrets_manager(OPENCAGE_SECRET_NAME, AWS_REGION)
if OPENCAGE_API_KEY is None:
    OPENCAGE_API_KEY = os.environ.get("OPENCAGE_API_KEY", "YOUR_OPENCAGE_API_KEY_DEFAULT")
    print(f"OPENCAGE_API_KEY loaded from environment variable or default.", file=sys.stderr)
else:
    print(f"OPENCAGE_API_KEY loaded from AWS Secrets Manager.", file=sys.stderr)


SECRET_KEY = get_secret_from_secrets_manager(FLASK_SECRET_KEY_NAME, AWS_REGION)
if SECRET_KEY is None:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "A_VERY_STRONG_DEFAULT_KEY_FOR_DEV_ONLY")
    print(f"FLASK_SECRET_KEY loaded from environment variable or default.", file=sys.stderr)
else:
    print(f"FLASK_SECRET_KEY loaded from AWS Secrets Manager.", file=sys.stderr)


# --- Default Location (Sharptown, MD) ---
DEFAULT_STATION_ID = "8571858"
DEFAULT_STATION_NAME = "Sharptown, Nanticoke River, MD"
DEFAULT_LATITUDE = 38.3970
DEFAULT_LONGITUDE = -75.7600

# --- Timezone Configuration ---
LOCAL_TIMEZONE = pytz.timezone('America/New_York')
