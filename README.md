# Global Entry Appointment Finder

Inspired by the many other Global Entry appointment scanners/checkers/notifiers/bots, this project differentiates itself by allowing you to **specify both the dates and times that work for you**. Almost all existing sites will only notify you of the `n` earliest slots that open up for a given location which is not always helpful since people have personal committments and not all times actually fit their schedules.

By using global-entry-appointment-finder, you can be notified *only* when an appointment that works for you becomes available. This can be especially helpful if you live far from a Global Entry enrollment center and want to be able to enroll while traveling domestically. Just set the dates/times when you'll be passing by/near an enrollment center, and you'll get a notification if something opens up!

Currently, this project is not as feature rich in terms of notification options as other existing services (only SMS supported right now, no desktop or email notifications as of now), but I am planning on continuing support for the tool in the interim future.

NOTE: This tool can also be used for NEXUS, SENTRI, and FAST: see the section "Support for other TTPs". Please also see [goes-notify](https://github.com/Drewster727/goes-notify#location-codes-for-other-trusted-traveler-programs) for some potential gotchas regarding `locationIds` if using a different Trusted Traveler Program (TTP). I have also duplicated the links from goes-notify in this repo just in case under "Location Ids".

# Getting Started
**TL;DR For those intereseted in Global Entry, this tool works mostly out of the box. You only need to follow the instructions in this section, select your locations/dates, and create a Twilio account to receive texts. You don't need to concern yourself with other settings/sections.**

Pull the repo and install the python dependencies by running:
```
pip install -r requirements.txt
```
Under `configs/`, create a copy of `user_options.example.json` named `user_options.json`. I tried to include an enrollment center which had plenty of appointments open for the specified date range (at least until July rolls around), so at this point you can test to make sure the script works by running:
```
cd src/
python scanner.py
```
This should run the script indefinitely until quit by the user. If you want to schedule a local chron job to run the script automatically instead, you can set the following variables in `scanner_constants.py`:
```
USING_AWS_LAMBDA: bool = True
DEBUG_AWS_LAMBDA_LOCAL: bool = True
```
And then schedule your local chron job accordingly.

Read the "User Options" section and the "Setting Up Twilio" section to customize the settings to your needs and set up SMS notifications. If you are more technically comfortable, you can follow the instructions in "Setting up AWS Lambda" so that you don't have to run the script locally and keep your computer on.

# User Options
By default most user configurable settings can be found in files under `configs/` as well as `src/scanner_constants.py`

`user_options.json`
- `dateTimeFormat`: Don't change for now, placeholder for customization in the future
- `email`: Unused for now, email implementation is a WIP.
- `phoneNumber`: Your phone number for SMS notifications.
- `twilioNumber`: See "Setting up Twilio"
- `twilioSID`: See "Setting up Twilio"
- `twilioAuth`: See "Setting up Twilio"
- `refreshTime`: Unused for now, placeholder for future
- `locations`: A list of locations
    - name: NOT consumed by script, but can be helpful in visually keeping track of things
    - `locationId`: must be specified; should get this from locations.json
    - `dateRanges`: List of date ranges
        - `startDate`: The first day in the date range
        - `endDate`: The last day in the date range (inclusive)
        - `dailyStartTime`: The earliest appointment that works for you on EACH day in the date range.
        - `dailyEndTime`: The latest appointment that works for you on EACH day in the date range.
        - Example: startDate: "2022-04-29", endDate: "2022-04-30", dailyStartTime: "19:00", dailyEndTime: "23:59" means any apppoints on April 29th 2022 or April 30th 2022 which are between 7:00PM and 11:59PM. The options are inputted this way since we assume that availability on weekdays is approximately the same. 
        - TODO: Support for specifying weekend times and automatically handling very large date ranges will potentially come later. For now, please enter weekdays and weekends as separate date ranges (yes, this is potentially a lot of ranges for a large timeframe).

`src/scanner_constants.py`
- `SELECTED_TTP`: One of "Global Entry", "NEXUS", "SENTRI", "FAST Mexico", "FAST Canada"
- `USING_AWS_LAMBDA`: Set to True if running on AWS Lambda.
- `DEBUG_AWS_LAMBDA_LOCAL`: A debug flag for debugging AWS Lambda runs locally.
- `S3_BUCKET`: The name of your S3 bucket. Used when running in AWS Lambda.
- `S3_PATH`: Your path under which you want to save the previously seen appointments when running on AWS Lambda. You can choose whatever you want for this.
- `*_PATH`: Remaining path constants for config files/log file.
- `*_API`: Can change the link used if the TTP API changes
- `SCHEDULER_PARAMS`: Most likely you will not need to edit this. Please do not increase "limit" to too high of a value to avoid inundating the TTP servers.

# Setting up Twilio
1. Sign up for a free account here https://www.twilio.com/try-twilio
2. On your twilio dashboard, make sure to generate your free phone number
3. Modify the `twilioNumber`, `twilioSID`, `twilioAuth` strings in `user_options.json` to reflect the values on your Twilio dashboard.

# Setting up AWS Lambda [Optional]
I will not outline the exact details here. Some digging around in the docs to figure out specifics may be necessary, but here are the basic steps:

1. Create a free tier account, create a new lambda, create an S3 bucket
1. In `scanner_constants.py` set `USING_AWS_LAMBDA = True` and `S3_BUCKET` to your created bucket's name. Set `S3_PATH` to whatever you want (or leave it empty).
1. Go to your lambda's page, and add all code and json files to the lambda (make sure to click "Deploy" to save changes). If you haven't run the script locally yet, make sure you do so once to generate `configs/raw_locations.json` and `configs/locations.json` as the script will not do so for you on Lambda (this is to minimize S3 requests as the Lambda environment is not mutable).
1. From your lambda's page, add layers for `twilio` and `pandas` packages. You can get pandas by adding the AWSDataWrangler layer provided by Amazon, but you can also get both packages by adding an ARN through here: https://github.com/keithrozario/Klayers. Otherwise follow the instructions here to create your own layer: https://www.gcptutorials.com/post/how-to-use-pandas-in-aws-lambda
1. Go to IAM and add permissions for your lambda to access S3.
1. At this point you can go to your lambda's page and click "Test" and make sure that the lambda runs as expected.
1. Go back to your lambda's page and add a CloudWatch event which triggers every minute. You can follow the instructions here: https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/RunLambdaSchedule.html
1. On your lambda's page, click on the monitor tab and make sure your lambda is running every minute by either examining the logs or the graphs. These can take a couple minutes to update for cloudwatch fired events, so please be patient. Check back after around 5 minutes.

# Setting up Email [WIP]
Email support is not yet available.

# Support for other TTPs
By default the scanner is set up for use with Global Entry, but you can pick a different TTP by simply changing the `SELECTED_TTP` field in `src/scanner_constants.py` to your desired TTP. If you've already run the script before, make sure to delete `configs/raw_locations.json` and `configs/locations.json` to force the script to redownload the corresponding files for your updated TTP.

NOTE: If you want to change your `SELECTED_TTP` after deploying on AWS Lambda, please remember to manually reupload the `locations.json` and `raw_locations.json` for your desired TTP as those files are not mutable by the script on Lambda.

# Location Ids
Here you will find the direct links to the most up to date list of locations ids for all trusted traveler programs, courtesy of [goes-notify](https://github.com/Drewster727/goes-notify#location-codes-for-other-trusted-traveler-programs). You can use these if the script is not fetching the list properly; just make sure `locations.json` does not exist and paste the contents of the page into `raw_locations.json`.

- [Global Entry location list](https://ttp.cbp.dhs.gov/schedulerapi/locations/?temporary=false&inviteOnly=false&operational=true&serviceName=Global%20Entry)
- [NEXUS location list](https://ttp.cbp.dhs.gov/schedulerapi/locations/?temporary=false&inviteOnly=false&operational=true&serviceName=NEXUS)
- [SENTRI location list](https://ttp.cbp.dhs.gov/schedulerapi/locations/?temporary=false&inviteOnly=false&operational=true&serviceName=SENTRI)
- [US/Mexico FAST location list](https://ttp.cbp.dhs.gov/schedulerapi/locations/?temporary=false&inviteOnly=false&operational=true&serviceName=U.S.%20%2F%20Mexico%20FAST)
- [US/Canada FAST location list](https://ttp.cbp.dhs.gov/schedulerapi/locations/?temporary=false&inviteOnly=false&operational=true&serviceName=U.S.%20%2F%20Canada%20FAST)

# License
MIT

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Disclaimer
This project is not affiliated in any way with U.S. Customs and Border Protection (CBP).

For the interested, there is a medium sized pitfall with the way the request for the available appointments works. In the SlotsRequest, the following params must be provided:
```
params = {
        "orderBy": "soonest",
        "limit": 100,
        "locationId": locationId,
        "minimum": 1,
}
```
Soonest is the only reasonable ordering, and to prevent spamming the API we should limit the number of slots we request. Here we set it to 100, but you could always change this number if needed. The problem is if the user sets a date range far in the future and there are 100 or more appointments available before the date range, we will not be able to tell if an appointment in the user's preferred date range opens up. Of course, this is a pretty rare use case, and it is not worth optimizing for. All popular Global Entry locations are completely booked for months in the future (some even up to a year in advance at the time of writing). If there were that many open appointments, chances are that you wouldn't be using this tool in the first place!