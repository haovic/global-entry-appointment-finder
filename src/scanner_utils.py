"""
scanner_utils.py
user: vhao
date: 03-27-2022

Automatically queries the TTP.gov website to find appointments for the
specified dates/times and notifies user when appointments meeting the 
critera are available.
"""


from typing import Any, Dict, List, Optional, Set

import asyncio
import copy
import functools
import json
import os
import requests
import traceback
import pandas as pd
from collections import defaultdict
from datetime import datetime
from random import random
from requests.adapters import HTTPAdapter, Retry
from twilio.rest import Client as TwilioClient
from urllib3.exceptions import MaxRetryError
from scanner_constants import (
    SCHEDULER_API,
    SCHEDULER_PARAMS,
    SELECTED_TTP,
    SELECTED_TTP_LINK,
    DEBUG_AWS_LAMBDA_LOCAL, 
    USING_AWS_LAMBDA,
    PREV_SEEN_APPTS_PATH,
    USER_OPTIONS_PATH,
    RAW_LOCATIONS_PATH,
    LOCATIONS_PATH,
)
from scanner_logger import getScannerLogger
from scanner_types import (
    LocationOptions,
    TwilioOptions,
    UserOptions
)


logger = getScannerLogger(__name__)


# Maps locationIds to a list of appointment start times
# formatted as datetime strings
prev_seen_appts: Dict[str, List[str]] = defaultdict(list)
twilio_client: Optional[TwilioClient] = None


def pretty_fmt_req(req) -> str:
    if req.headers.items():
        return ('{}\r\n{}'.format(
            req.method + ' ' + req.url,
            '\r\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        ))
    else:
        return ('{}'.format(
            req.method + ' ' + req.url,
        ))


# Formats raw locations JSON into something user readable
def pretty_fmt_locations(raw_locations: List[Dict]) -> str:
    state_to_location = defaultdict(list)
    for location in raw_locations:
        state = location["state"]
        state_to_location[state].append({
            "name": location["name"],
            "shortName": location["shortName"],
            "locationId": location["id"],
        })
    return json.dumps(state_to_location, indent=4, sort_keys=True)


# Populates prev_seen_appts from file.
def get_prev_seen_appointments() -> None:
    global prev_seen_appts
    path = PREV_SEEN_APPTS_PATH
    if USING_AWS_LAMBDA and not DEBUG_AWS_LAMBDA_LOCAL:
        from scanner_lambdas_utils import lambda_read
        try:
            prev_seen_appts = defaultdict(list, json.loads(lambda_read(path)))
            # Write it back to local in case we failed to retrieve 
            # from local
            put_prev_seen_appointments(writethrough=False)
        except Exception as e:
            # While not being able to read the file could cause spam,
            # we have no way of knowing if this is the first time running
            # the script or if the user has simply deleted the file.
            logger.warning(
                "Unable to load previously seen appointments from file. If this "
                "is the first time running the lambda or if the file was deleted "
                "on purpose, this warning can be safely ignored. Otherwise spam "
                "may occur; please be careful."
            )
    else:
        try:
            with open(path, "r") as f:
                prev_seen_appts = defaultdict(list, json.load(f))
        except Exception as e:
            logger.warning(
                "".join(traceback.format_exception(None, e, e.__traceback__))
            )
            logger.warning("Unable to load previously seen appointments.")

    logger.debug(f"prev_seen_appts:\n{prev_seen_appts}")

""""
Note: This MUST execute synchronously to prevent later updates
to prev_seen_appts from being overwritten by an earlier update
as we overwite the entire file instead of appending.

Args:
    locationId: location id
    appointments: list of datetime strings to add to prev_seen_appts
    writethrough: When using AWS Lambda, whether or not to write to S3 
"""
def put_prev_seen_appointments(
    locationId: int, 
    appointments: List[str], 
    writethrough: bool = True
) -> None:
    # Update global var
    prev_seen_appts[str(locationId)].extend(appointments)

    path = PREV_SEEN_APPTS_PATH
    json_string = json.dumps(prev_seen_appts, indent=4, sort_keys=True)
    if USING_AWS_LAMBDA and not DEBUG_AWS_LAMBDA_LOCAL:
        from scanner_lambdas_utils import lambda_write
        try:
            lambda_write(path, json_string, writethrough=writethrough)
        except Exception as e:
            logger.fatal(
                f"SERIOUS ISSUE: Unable to write previously seen appointments to "
                "S3. This could cause a ton of spam. Please stop the lambda "
                "trigger event ASAP."
            )
            raise e
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(json_string)


def get_user_options() -> UserOptions:
    get_prev_seen_appointments()

    user_options_dict = None
    with open(USER_OPTIONS_PATH, "r") as f:
        user_options_dict = json.load(f)

    locationid_to_name = {}
    with open(LOCATIONS_PATH, "r") as f:
        locations_dict = json.load(f)
        for _, locations in locations_dict.items():
            for location in locations:
                locationId = location["locationId"]
                locationName = location["name"]
                locationid_to_name[locationId] = locationName

    if user_options_dict:

        dtfmt = user_options_dict["dateTimeFormat"]
        location_options_list: List[LocationOptions] = []
        # Parse LocationOptions
        for user_loc_options in user_options_dict["locations"]:
            locationId = user_loc_options["locationId"]
            locationName = locationid_to_name[locationId]
            dateToTimeRanges = defaultdict(list)
            for user_date_range in user_loc_options["dateRanges"]:
                startDate = user_date_range["startDate"]
                endDate = user_date_range["endDate"]
                dailyStartTime = user_date_range["dailyStartTime"]
                dailyEndTime = user_date_range["dailyEndTime"]

                date_range = pd.date_range(start=startDate, end=endDate)
                for date in date_range:
                    date_str = date.strftime("%Y-%m-%d")
                    start_time = datetime.strptime(
                        date_str + " " + dailyStartTime, dtfmt)
                    end_time = datetime.strptime(
                        date_str + " " + dailyEndTime, dtfmt)
                    time_range = (start_time, end_time)
                    dateToTimeRanges[date_str].append(time_range)

            location_options_list.append(
                LocationOptions(locationId, locationName, dateToTimeRanges))

        email = user_options_dict["email"]
        phone_number = user_options_dict["phoneNumber"]
        twilio_options = TwilioOptions(
            user_options_dict["twilioNumber"],
            user_options_dict["twilioSID"],
            user_options_dict["twilioAuth"],
        )
        if twilio_options.number and twilio_options.sid and twilio_options.auth:
            global twilio_client
            twilio_client = TwilioClient(
                twilio_options.sid, twilio_options.auth
            )

        user_options = UserOptions(
            email=email,
            phoneNumber=phone_number,
            twilioOptions=twilio_options,
            locationOptionsList=location_options_list,
        )
        logger.debug(f"Got the following user options:\n{user_options}")
        return user_options
    else:
        logger.fatal(
            "Could not load user options, please ensure the file"
            "user_options.json exists in the same directory as the script"
        )
        exit(1)


# Gets TTP locations and writes to file
def get_locations() -> None:
    if not os.path.isfile(LOCATIONS_PATH):
        logger.info(
            f"{LOCATIONS_PATH} not found, regenerating locations from "
            "raw locations..."
        )

        if not os.path.isfile(RAW_LOCATIONS_PATH):
            logger.info(f"{RAW_LOCATIONS_PATH} not found, getting raw "
            "locations from TTP website")
            try:
                res = requests.get(SELECTED_TTP_LINK)
                os.makedirs(os.path.dirname(RAW_LOCATIONS_PATH), exist_ok=True)
                with open(RAW_LOCATIONS_PATH, "w") as f:
                    json.dump(res.json(), f, indent=4, sort_keys=True)
            except Exception as e:
                logger.fatal(
                    "Failed to get raw locations list, if this continues "
                    "to occur, please try to retrieve them manually"
                )
                raise e

        with open(RAW_LOCATIONS_PATH, "r") as f:
            raw_locations = json.load(f)

        os.makedirs(os.path.dirname(LOCATIONS_PATH), exist_ok=True)
        with open(LOCATIONS_PATH, "w") as f:
            f.write(pretty_fmt_locations(raw_locations))


# Creates a Session with a given retry strategy
def create_session() -> requests.Session:
    retry_strategy = Retry(
        total=3,
        backoff_factor=5,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["GET"]
    )
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=retry_strategy))
    return session


async def send_request(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict] = None,
    session: Optional[requests.Session] = None,
) -> requests.Response:
    if not session:
        session = create_session()

    prepared = requests.Request(
        'GET', url, params=params, headers=headers).prepare()
    pretty_request = pretty_fmt_req(prepared)
    logger.debug(f"Sending request: {pretty_request}")

    while True:
        print("DEBUG")
        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(
                None, functools.partial(session.send, prepared, timeout=5)
            )
            break
        except MaxRetryError:
            if USING_AWS_LAMBDA:
                raise RuntimeError(
                    "Max retries reached on AWS lambda, will NOT retry after sleep"
                )

            logger.warning(
                "Maximum retries for this request reached, sleeping "
                f"for 5 minutes ({pretty_request})"
            )
            await asyncio.sleep(5*60)

    if res.ok:
        return res
    elif res.status_code >= 400 and res.status_code < 500:
        logger.fatal(
            f"Request failed with status code {res.status_code}. "
            "Some potentially fatal user error occured. Perhaps the "
            "site API has changed?")
        raise RuntimeError("Request failed with client error")
    elif res.status_code >= 500:
        logger.fatal(
            f"Request failed with status code {res.status_code}. "
            "Server may be experiencing significant issues"
        )
        raise RuntimeError("Request failed with non-retryable server error")


async def notify(
    location_options: LocationOptions,
    user_options: UserOptions,
    appointment_times: Set[datetime],
) -> None:
    locationId = location_options.locationId
    location_name = location_options.name
    email = user_options.email
    phone_number = user_options.phoneNumber
    twilio_number = user_options.twilioOptions.number

    new_appointments = appointment_times - \
        set(prev_seen_appts[str(locationId)])
    sorted_appointments = list(new_appointments)
    sorted_appointments.sort()
    if sorted_appointments:
        logger.info(
            f"Scanner {locationId}: Found new appointments for {location_name}! "
            f"Appointment times: {sorted_appointments}."
        )

        at_least_one_success = False
        if email:
            logger.info(
                f"Scanner {locationId}: Sending email to {email} "
                "to notify user..."
            )
            # TODO
            at_least_one_success = True

        if phone_number and twilio_client is not None:
            logger.info(
                f"Scanner {locationId}: Sending text to {phone_number} "
                "to notify user..."
            )
            truncate = min(len(sorted_appointments), 3)
            body = (
                f"[{SELECTED_TTP} SCANNER]: Preferred appointment(s) available!\n"
                f"Appointment Location: {location_name}\n"
                f"Appointment Times: {sorted_appointments[:truncate]}"
            )
            if len(sorted_appointments) > truncate:
                body += (
                    f" as well as {len(sorted_appointments) - truncate} more! "
                    f"To see all times, please check the {SELECTED_TTP} website."
                )

            message = twilio_client.messages.create(
                body=body,
                from_=twilio_number,
                to=phone_number,
            )
            logger.debug(
                f"Successfully sent text with message sid {message.sid}")

            # We assume success since not using StatusCallback URL
            at_least_one_success = True

        if at_least_one_success:
            logger.debug(
                f"Scanner {locationId}: User was successfully notified by "
                "at least one means. Will no longer notify for these times."
            )
            # Must writethrough since /tmp is ephemeral
            # Since this only triggers upon user notif, and user notifs
            # are grouped by region, it is pretty unlikely that we will
            # exhaust the 2000 PUT requests/month limit for free tier.
            put_prev_seen_appointments(
                locationId, sorted_appointments, writethrough=True
            )
        else:
            logger.warning(
                f"Scanner {locationId}: User was not notified in any way. "
                "Please make sure your email or phone number and twilio "
                "information are set up properly."
            )
    else:
        logger.info(
            f"Scanner {locationId}: All appointments found have already "
            "been sent to the user before. Will not notify again."
        )


async def scan(
    session: requests.Session,
    location_options: LocationOptions,
    user_options: UserOptions,
) -> None:
    locationId = location_options.locationId
    date_to_time_ranges = location_options.dateToTimeRanges

    # Sleep a random amount to prevent stampeding the servers
    # when script starts and also offsets each thread a slight
    # amount when requesting again
    max_sleeptime = 2 if USING_AWS_LAMBDA else 10
    sleeptime: float = random() * max_sleeptime
    logger.info(
        f"Scanner {locationId}: Sleeping for {sleeptime} seconds "
        "before starting..."
    )
    await asyncio.sleep(sleeptime)
    
    # Set the locationId for the request
    params = copy.deepcopy(SCHEDULER_PARAMS)
    params["locationId"] = locationId

    # Continuously send requests until we get a non-retryable error
    # or the script is stopped by user
    while True:
        try:
            logger.info(f"Scanner {locationId}: Checking for appointments...")
            res = await send_request(SCHEDULER_API, params=params, session=session)
            available_appointments = res.json()
            logger.info(
                f"Scanner {locationId}: Found {len(available_appointments)} "
                "available appointments"
            )

            valid_appointments = set()
            for appointment in available_appointments:
                appt_start = appointment["startTimestamp"]
                appt_start_dt = datetime.strptime(appt_start, "%Y-%m-%dT%H:%M")
                date_str = appt_start_dt.strftime("%Y-%m-%d")

                # Check if there are any timeranges for the given date
                if date_str in date_to_time_ranges:
                    for time_range in date_to_time_ranges[date_str]:
                        if (
                            appt_start_dt >= time_range[0] and
                            appt_start_dt <= time_range[1]
                        ):
                            valid_appointments.add(
                                appt_start_dt.strftime("%Y-%m-%d %H:%M")
                            )

            if valid_appointments:
                await notify(location_options, user_options, valid_appointments)
            else:
                logger.info(
                    f"Scanner {locationId}: None of found appointments satisfy "
                    "requirements"
                )

            if USING_AWS_LAMBDA:
                logger.info(f"Scanner {locationId} finished")
                break

            # Sleep 1 minute before checking again
            delay = 60
            logger.info(
                f"Scanner {locationId}: Sleeping for {delay} seconds...")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.fatal(
                "".join(traceback.format_exception(None, e, e.__traceback__))
            )
            logger.fatal(
                f"Scanner for locationId: {locationId} encountered a "
                "non-retryable error. Will NOT scan for this location "
                "anymore. Please restart the script to scan for this "
                "location again."
            )
            break


async def launch_scanners(user_options: UserOptions):
    location_options_list = user_options.locationOptionsList
    scanner_tasks = []
    session = create_session()
    for location_options in location_options_list:
        logger.info(
            f"Launching scanner for locationId: {location_options.locationId}")
        scanner_tasks.append(
            asyncio.create_task(
                scan(session, location_options, user_options)
            )
        )

    await asyncio.gather(*scanner_tasks)
    logger.info("All scanner tasks finished, stopping...")
