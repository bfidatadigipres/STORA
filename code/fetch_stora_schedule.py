#!/usr/bin/env python3.8

"""
Fetch JSON from PATV EPG metadata API for next four day's shows (not today's)
Overwrite each time and split into channels and place into correct channel/date folder

main():
1. Creates STORA schedules for next four days if not already created
2. Call the API for next four days programming metadata, using fetch():
3. If first fetch fails, fetch(): will retry with tenacity until successful (10 retries)
4. When downloaded outputs to date/channel folder
5. Iterates channel programmes extracting a day schedule for given day/channel
   Populates JSON list with dictionaries containing: start time, duration, channel, programme
   (No handles used for these due to inability for demux dump to overlap)
6. Writes new schedules to json with filename formatted {channel}_schedule_{YYYY-MM-DD}.json
7. Where json list already exists compares data and updates if changes have occurred
8. Places finished schedules for radox recording scripts in schedules/
9. Move schedules over two days old to completed/schedules folder

Joanna White
2022
"""

import datetime
import json
import logging
# Public packages
import os
import shutil

import requests
import tenacity

# Date variables for EPG API calls
TOD = datetime.date.today()
TOM1 = TOD + datetime.timedelta(days=1)
TOM2 = TOM1 + datetime.timedelta(days=1)
TOM3 = TOM2 + datetime.timedelta(days=1)
TOM4 = TOM3 + datetime.timedelta(days=1)
TOM1 = TOM1.strftime("%Y-%m-%d")
TOM2 = TOM2.strftime("%Y-%m-%d")
TOM3 = TOM3.strftime("%Y-%m-%d")
TOM4 = TOM4.strftime("%Y-%m-%d")
START1 = f"{TOM1}T00:00:00"
END1 = f"{TOM1}T23:59:00"
START2 = f"{TOM2}T00:00:00"
END2 = f"{TOM2}T23:59:00"
START3 = f"{TOM3}T00:00:00"
END3 = f"{TOM3}T23:59:00"
START4 = f"{TOM4}T00:00:00"
END4 = f"{TOM4}T23:59:00"
# If a different date period needs targeting use:
#START1 = '2024-11-05T00:00:00'
#END1 = '2024-11-05T23:59:00'

# Global path variables
FORMAT = '%Y-%m-%d'
STORAGE_PATH = os.environ.get('STORAGE_PATH')
FOLDERS = os.environ.get('STORA_FOLDERS')
COMPLETE_PTH = os.environ.get('STORA_COMPLETE')
SCHEDULE_PATH = os.path.join(FOLDERS, 'schedules/')
COMPLETED = os.path.join(COMPLETE_PTH, 'schedules/')
LOG_FILE = os.path.join(FOLDERS, 'logs/fetch_stora_schedule.log')


# TARGET DATE PATHS
DATE_PATH1 = START1[0:4] + "/" + START1[5:7] + "/" + START1[8:10]
DATE_PATH2 = START2[0:4] + "/" + START2[5:7] + "/" + START2[8:10]
DATE_PATH3 = START3[0:4] + "/" + START3[5:7] + "/" + START3[8:10]
DATE_PATH4 = START4[0:4] + "/" + START4[5:7] + "/" + START4[8:10]
PATHS = [
    os.path.join(STORAGE_PATH, DATE_PATH1),
    os.path.join(STORAGE_PATH, DATE_PATH2),
    os.path.join(STORAGE_PATH, DATE_PATH3),
    os.path.join(STORAGE_PATH, DATE_PATH4),
]

# Setup logging
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    format="%(asctime)s\t%(levelname)s\t%(message)s",
    level=logging.INFO,
)

# PATV API details including unique identifiers for in-scope channels
URL = os.environ["PATV_URL"]
HEADERS = {"accept": "application/json", "apikey": os.environ["PATV_KEY"]}

# Dictionary of Redux channel names and unique EPG retrieval paths
CHANNEL = {
    "bbconehd": os.environ['PA_BBCONE'],
    "bbctwohd": os.environ['PA_BBCTWO'],
    "bbcthree": os.environ['PA_BBCTHREE'],
    "bbcfourhd": os.environ['PA_BBCFOUR'],
    "bbcnewshd": os.environ['PA_BBCNEWS'],
    "cbbchd": os.environ['PA_CBBC'],
    "cbeebieshd": os.environ['PA_CBEEBIES'],
    "itv1": os.environ['PA_ITV1'],
    "itv2": os.environ['PA_ITV2'],
    "itv3": os.environ['PA_ITV3'],
    "itv4": os.environ['PA_ITV4'],
    "channel4": os.environ['PA_CHANNEL4'],
    "more4": os.environ['PA_MORE4'],
    "film4": os.environ['PA_FILM4'],
    "five": os.environ['PA_FIVE'],
    "5star": os.environ['PA_5STAR'],
    "e4": os.environ['PA_E4']
}


@tenacity.retry(wait=tenacity.wait_fixed(60))
def fetch(value, pth):
    """
    Retrieval of EPG metadata dependent on date
    """
    if pth[-2:] == START1[8:10]:
        start, end = START1, END1
    elif pth[-2:] == START2[8:10]:
        start, end = START2, END2
    elif pth[-2:] == START3[8:10]:
        start, end = START3, END3
    elif pth[-2:] == START4[8:10]:
        start, end = START4, END4
    else:
        return None
    try:
        params = {"channelId": f"{value}", "start": start, "end": end, "aliases": "True"}
        print(params)
        req = requests.request("GET", URL, headers=HEADERS, params=params, timeout=1200)
        print(req.text, params)
        dct = json.loads(req.text)
        return dct
    except Exception as err:
        print(f"fetch(): {err} **** PROBLEM: Cannot fetch EPG metadata. Tenacity will retry every 60 seconds")
        logging.critical("**** PROBLEM: Cannot fetch EPG metadata. Tenacity will retry every 60 second")
        return None


def main():
    """
    Create json dumps of programming
    Sort into new JSON schedule for off-air recording
    """

    # Checks if all channel folders exist in storage_path
    logging.info("========= FETCH RADOX SCHEDULE START ====================")
    for item in CHANNEL.keys():
        for pth in PATHS:
            item_path = os.path.join(pth, item)
            if not os.path.exists(item_path):
                logging.info("Generating new path for JSON schedules: %s", item_path)
                os.makedirs(item_path, exist_ok=True)
            else:
                continue

    list_of_json = []
    for pth in PATHS:
        # If metadata cannot be retrieved the script continues to next
        logging.info(
            "Requests will now attempt to retrieve the EPG channel metadata for path: %s",
            pth,
        )
        for key, value in CHANNEL.items():
            dct = fetch(value, pth)
            if not dct:
                logging.warning("No Dictionary retrieved for %s - %s", value, pth)
                continue
            fname = retrieve_dct_data(key, pth, dct)
            list_of_json.append(fname)
            if not fname:
                print(f"Data retrieval failed for {key}: {pth}")
                continue

    for item in list_of_json:
        print(item)
        schedule = []
        schedule = schedule_extraction(item)
        # assess schedule for missing duration times
        if "'end': 'None'" in str(schedule):
            logging.warning("* PROBLEM WITH DURATION IN THIS SCHEDULE: %s", item)
        channel_pth = os.path.split(item)[0]
        date_path_split = os.path.split(channel_pth)
        date_path = date_path_split[0]
        if "/video/" in date_path:
            date_only = date_path.split("/video/")[1]
        else:
            date_only = date_path.split("/STORA/")[1]
        date_only = date_only.rstrip("/")
        date_now = date_only.replace("/", "-")
        day_schedule = os.path.join(
            SCHEDULE_PATH, f"{date_path_split[1]}_schedule_{date_now}.json"
        )
        if not os.path.exists(day_schedule):
            logging.info("New schedule being created: %s", day_schedule)
            with open(day_schedule, "w") as f:
                json.dump(schedule, f, indent=4)
        else:
            logging.info(
                "Schedule already exists, checking for mismatched data before replacing: %s",
                day_schedule,
            )
            with open(day_schedule, "r") as inf:
                existing_schedule = json.load(inf)
                if len(schedule) == len(existing_schedule):
                    logging.info(
                        "Length of current schedule and new schedule match. Likely data is good quality"
                    )
                else:
                    os.remove(item)
                    continue

            # If already exists, compare and update any changes
            result = compare_schedule(day_schedule, schedule)
            if "Mismatch" in result:
                logging.info("Schedule does not match, updates required")
                try:
                    os.remove(day_schedule)
                    with open(day_schedule, "w") as f:
                        json.dump(schedule, f, indent=4)
                except Exception:
                    print(f"Unable to delete {day_schedule} or make new one")

        try:
            os.remove(item)
        except Exception as exc:
            raise logging.warning("Unable to remove file %s", item) from exc

    logging.info("Schedule created completed. Cleaning up old schedules.")
    clean_up()
    logging.info("========= FETCH RADOX SCHEDULE END ====================\n")


def retrieve_dct_data(key, pth, dct=None):
    """
    Check if DCT data is None, if not instigate json_split
    """
    if dct is None:
        logging.critical(
            "FAILED: Multiple attempt to retrieve metadata. Script exiting."
        )
        return False
    else:
        logging.info("EPG metadata successfully retrieved. Dumping to channel path")
        fname = os.path.join(pth, key, f"schedule_{key}.json")
        with open(fname, "w") as f:
            json.dump(dct, f, indent=4)
        return fname


def schedule_extraction(json_path):
    """
    For each JSON, open and extract title, date, start and end time
    Use this data to populate a top level channel JSON schedule
    Located in the STORAGE_PATH/CHANNEL
    """
    pth = os.path.split(json_path)[0]
    key = os.path.split(pth)[1]

    with open(json_path) as inf:
        dct = json.load(inf)
    if type(dct) is not dict:
        return False

    channel_schedule = []
    for subdct in dct["item"]:
        title = date_time = duration = ""
        try:
            title = subdct["title"]
        except (IndexError, KeyError, TypeError):
            title = ""
        try:
            date_time = subdct["dateTime"]
        except (IndexError, KeyError, TypeError):
            date_time = ""
        try:
            duration = subdct["duration"]
            duration = int(duration)
        except (IndexError, KeyError, TypeError):
            duration = 0

        # Skip over programmes with '0' duration
        if duration == 0:
            continue

        progdct = build_timings(title, date_time, duration, key)
        channel_schedule.append(progdct)

    return channel_schedule


def build_timings(title, date_time, duration, key):
    """
    Receive timings per programme per schedule
    return list of dictionaries
    """
    data = {}
    fmt = "%Y-%m-%d %H:%M:%S"
    time_start = datetime.datetime.fromisoformat(str(date_time[:23]))
    orig_start = time_start - datetime.timedelta(minutes=0)

    if type(duration) is str:
        data = {
            "start": orig_start.strftime(fmt),
            "duration": 0,
            "channel": key,
            "programme": title,
        }

    if type(duration) is int:
        data = {
            "start": orig_start.strftime(fmt),
            "duration": duration,
            "channel": key,
            "programme": title,
        }

    return data


def compare_schedule(schedule_path, data):
    """
    Open existing schedule and compare current
    schedule to see if it's changed. Map change to logs
    Update different lines of original schedule
    """
    with open(schedule_path) as inf:
        existing_schedule = json.load(inf)
    json1 = existing_schedule
    json2 = data

    if json1 == json2:
        return "Match"
    else:
        mismatch = []
        for i in json1:
            if i not in json2:
                mismatch.append(i)
        return f"Mismatch: {mismatch}"


def clean_up():
    """
    Check schedules folder for schedules older than yesterday
    Where found move them to completed/schedules/ folder
    channel4_schedule_2022-03-03.json
    """

    files = [x for x in os.listdir(SCHEDULE_PATH) if x.endswith("json")]
    for file in files:
        if file.startswith("demonstration"):
            continue
        # Get date from name
        filename = file.split(".")[0]
        file_data = filename.split("_")[2]
        print(file_data)
        if "schedule" in str(file_data):
            continue
        two_days = datetime.datetime.now() - datetime.timedelta(days=2)
        two_days = two_days.strftime(FORMAT)
        dt_date = datetime.datetime.strptime(file_data, FORMAT)
        two_days_ago = datetime.datetime.strptime(two_days, FORMAT)
        print(f"Times: {two_days_ago} > {dt_date}")

        if two_days_ago > dt_date:
            logging.info("Old file found, moving to completed: %s", file)
            current_path = os.path.join(SCHEDULE_PATH, file)
            move_path = os.path.join(COMPLETED, file)
            try:
                shutil.move(current_path, move_path)
            except Exception as exc:
                logging.warning("Couldn't move schedule %s to COMPLETED path", file)
                logging.warning(exc)


if __name__ == "__main__":
    main()
