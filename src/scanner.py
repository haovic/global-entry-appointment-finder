"""
scanner.py
user: vhao
date: 03-27-2022

Automatically queries the ttp.dhs.gov website to find TTP appointments for 
the specified dates/times and notifies user when appointments meeting the critera 
are available.
"""

from scanner_constants import USING_AWS_LAMBDA

import asyncio
from scanner_utils import get_locations, get_user_options, launch_scanners


async def start_scanning():
    # Don't attempt to get locations on lambda, the files are static
    if not USING_AWS_LAMBDA:
        get_locations()

    user_options = get_user_options()
    await launch_scanners(user_options)

if __name__ == "__main__":
    asyncio.run(start_scanning())
