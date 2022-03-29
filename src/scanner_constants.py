"""
scanner_constants.py
user: vhao
date: 03-27-2022

Set USING_AWS_LAMBDA to True if running on AWS lambda.
"""

import os

# TTP APIs
SCHEDULER_API = "https://ttp.cbp.dhs.gov/schedulerapi/slots"
locations_api = "https://ttp.cbp.dhs.gov/schedulerapi/locations/?temporary=false&inviteOnly=false&operational=true&serviceName="

# Default scheduler params
SCHEDULER_PARAMS = {
    "orderBy": "soonest",
    "limit": 100,
    "minimum": 1,
}

# TTP to serviceName in link
ttp_to_link_service_name = {
    "Global Entry": "Global%20Entry",
    "NEUXS": "NEXUS",
    "SENTRI": "SENTRI",
    "FAST Mexico": "U.S.%20%2F%20Mexico%20FAST",
    "FAST Canada": "U.S.%20%2F%20Canada%20FAST",
}

# Selected Trusted Traveler Program for scanner to scan for
# If changing this variable, remember to delete config/locations.json
# and config/raw_locations.json so they can be regenerated.
SELECTED_TTP = "Global Entry"
SELECTED_TTP_LINK = locations_api + ttp_to_link_service_name[SELECTED_TTP]

# AWS Lambda related
USING_AWS_LAMBDA: bool = False
DEBUG_AWS_LAMBDA_LOCAL: bool = False
S3_BUCKET: str = ""
S3_PATH: str = ""

# Config and log paths
PREV_SEEN_APPTS_PATH = os.path.join("..", "configs", "prev_seen_appts.json")
USER_OPTIONS_PATH = os.path.join("..", "configs", "user_options.json")
RAW_LOCATIONS_PATH = os.path.join("..", "configs", "raw_locations.json")
LOCATIONS_PATH = os.path.join("..", "configs", "locations.json")
LOGS_PATH = os.path.join("..", "logs", "scanner.log")
