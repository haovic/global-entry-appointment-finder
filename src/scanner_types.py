"""
scanner_types.py
user: vhao
date: 03-27-2022

Types defined for use by scanner functions.
"""

from typing import Dict, List, Tuple

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TwilioOptions:
    number: str
    sid: str
    auth: str


@dataclass
class LocationOptions:
    locationId: int
    name: str
    # Each date has an entry in dictionary as a string
    # which then maps to the actual time range for that date
    dateToTimeRanges: Dict[str, List[Tuple[datetime, datetime]]]


@dataclass
class UserOptions:
    email: str
    phoneNumber: str
    twilioOptions: TwilioOptions
    locationOptionsList: List[LocationOptions]
