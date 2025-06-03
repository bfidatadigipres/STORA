#!/usr/bin/env python3

"""
Script that iterates through folders, looking for folders
that do not have an info.csv. Where missing generates one
using the EPG metadata schedule. Run early AM for
yesterday's programmes to aid ingest to DPI.

main():
1. Find yesterday's programme folders where info.csv absent
2. Extract start time/duration from folder name
3. Check yesterday's schedule for start time match
4. Call up programme information from PA TV API
5. Make up list of data: title, description, date, starttime, duration
5. Use csv to create CSV file and dump data to it
6. Save alongside stream called 'info.csv'

Joanna White
2022
"""

import csv
import json
import logging
import os
import subprocess
from datetime import datetime, timedelta

import requests
import tenacity

# Static global variables
FORMAT = "%Y-%m-%d %H:%M:%S"
TFORM = "%Y-%m-%dT%H:%M:%S"
STORAGE_PATH = os.environ["STORAGE_PATH"]
STORA_PTH = os.environ["STORA_PATH"]
CODEPTH = os.environ["CODE"]
CONFIG_FILE = os.path.join(CODEPTH, "stream_config.json")
TODAY = datetime.now()
YEST = TODAY - timedelta(1)
YEST_PATH = os.path.join(
    STORAGE_PATH, f"{str(YEST)[0:4]}/{str(YEST)[5:7]}/{str(YEST)[8:10]}/"
)
YEST_DATE = f"{str(YEST)[0:4]}-{str(YEST)[5:7]}-{str(YEST)[8:10]}"
# USE THESE FOR FORCING ALTERNATIVE DATES
# YEST_PATH = os.path.join(STORAGE_PTH, '2022/07/21')
# YEST_DATE = '2022-07-21'

# Setup logging
LOGGER = logging.getLogger("make_info_from_schedule")
HDLR = logging.FileHandler(os.path.join(CODEPTH, "logs/make_info_from_schedule.log"))
FORMATTER = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")
HDLR.setFormatter(FORMATTER)
LOGGER.addHandler(HDLR)
LOGGER.setLevel(logging.INFO)

# PATV API details including unique identifiers for in-scope channels
URL = os.environ["PATV_URL"]
HEADERS = {"accept": "application/json", "apikey": os.environ["PATV_KEY"]}

# Dictionary of Redux channel names and unique EPG retrieval paths
API_KEY = {
    "bbconehd": os.environ["PA_BBCONE"],
    "bbctwohd": os.environ["PA_BBCTWO"],
    "bbcthree": os.environ["PA_BBCTHREE"],
    "bbcfourhd": os.environ["PA_BBCFOUR"],
    "bbcnewshd": os.environ["PA_BBCNEWS"],
    "cbbchd": os.environ["PA_CBBC"],
    "cbeebieshd": os.environ["PA_CBEEBIES"],
    "itv1": os.environ["PA_ITV1"],
    "itv2": os.environ["PA_ITV2"],
    "itv3": os.environ["PA_ITV3"],
    "itv4": os.environ["PA_ITV4"],
    "citv": os.environ["PA_CITV"],
    "channel4": os.environ["PA_CHANNEL4"],
    "more4": os.environ["PA_MORE4"],
    "film4": os.environ["PA_FILM4"],
    "five": os.environ["PA_FIVE"],
    "5star": os.environ["PA_5STAR"],
}

CHANNELS = {
    "bbconehd": "BBC One HD",
    "bbctwohd": "BBC Two HD",
    "bbcthree": "BBC Three HD",
    "bbcfourhd": "BBC Four HD",
    "bbcnewshd": "BBC NEWS HD",
    "cbbchd": "CBBC HD",
    "cbeebieshd": "CBeebies HD",
    "citv": "CITV",
    "channel4": "Channel 4 HD",
    "five": "Channel 5 HD",
    "film4": "Film4",
    "5star": "5STAR",
    "itv1": "ITV HD",
    "itv2": "ITV2",
    "itv3": "ITV3",
    "itv4": "ITV4",
    "more4": "More4",
}


@tenacity.retry(wait=tenacity.wait_random(min=50, max=60))
def check_api():
    """
    Run standard check with today's date on BBC One HD
    """

    params = {
        "channelId": f"{os.environ['PA_BBCONE']}",
        "start": f"{YEST_DATE}T21:00:00",
        "end": "{YEST_DATE}T23:00:00",
        "aliases": "True",
    }

    req = requests.request("GET", URL, headers=HEADERS, params=params, timeout=12)
    if req.status_code == 200:
        return True
    else:
        LOGGER.info("PATV API return status code: %s", req.status_code)
        raise tenacity.TryAgain


def fetch(chnl, start, end):
    """
    Retrieval of EPG metadata here
    """

    for key, val in API_KEY.items():
        if chnl == key:
            value = val
    print(f"API KEY: {value}")
    try:
        params = {
            "channelId": f"{value}",
            "start": start,
            "end": end,
            "aliases": "True",
        }
        LOGGER.info("fetch(): %s", params)
        req = requests.request("GET", URL, headers=HEADERS, params=params)
        dct = json.loads(req.text)
        return dct
    except Exception as err:
        print("fetch(): **** PROBLEM: Cannot fetch EPG metadata.")
        LOGGER.critical("**** PROBLEM: Cannot fetch EPG metadata. **** \n%s", err)
        return None


def get_folder_time(folder):
    """
    Cut up folder start time/duration
    and return as datetime object
    """

    tm = folder[0:8]
    duration = folder[-8:]
    tm = tm.replace("-", ":")
    dt_str = f"{YEST_DATE} {tm}"
    dt_start = datetime.strptime(dt_str, FORMAT)
    dt_end = dt_start + timedelta(minutes=10)
    return dt_end.strftime(TFORM), dt_start.strftime(TFORM), duration


def configure_data(data, start, duration, stream_duration, chnl):
    """
    Cut up metadata string and format for CSV write
    Get stream duration here and make sure written to
    second duration field.
    """

    for key, val in CHANNELS.items():
        if key == chnl:
            chnl = val
    if type(data) == list:
        data = data[0]

    try:
        title = data["item"][0]["title"]
        description = data["item"][0]["summary"]["medium"]
    except (IndexError, TypeError, KeyError):
        title, description = "", ""

    if not title:
        return None

    info_list = [
        f"{chnl}",
        f"{title}",
        f"{description}",
        f"{start[:10]}",
        f"{start[11:]}",
        f"{duration.replace('-', ':')}",
        f"{stream_duration}",
    ]
    return info_list


def get_metadata(fpath):
    """
    Mediainfo retrieval of duration and reform to HH:MM:SS
    """

    cmd = [
        "mediainfo",
        "--Language=raw",
        "--Full",
        '--Inform="General;%Duration/String3%"',
        fpath,
    ]
    cmd[3] = cmd[3].replace('"', "")
    duration = subprocess.check_output(cmd)
    duration = duration.decode("utf-8")
    print(duration)
    if len(duration) > 8:
        return str(duration)[:8]


def main():
    """
    Iterate today's/yesterday's redux paths looking
    for folders that have end times > now time
    Where found create info.csv if not
    already present
    """

    LOGGER.info("MAKE INFO FROM SCHEDULE START ==============================")

    for chnl in CHANNELS.keys():
        ypath = os.path.join(YEST_PATH, chnl)

        try:
            y_folders = [
                x for x in os.listdir(ypath) if os.path.isdir(os.path.join(ypath, x))
            ]
        except Exception:
            y_folders = []

        if not y_folders:
            continue
        for folder in y_folders:
            print(f"Channel {chnl}, Folder {folder}")
            fpath = os.path.join(ypath, folder)
            dt_end, dt_start, duration = get_folder_time(folder)
            files = os.listdir(fpath)

            if "info.csv" in files:
                continue

            LOGGER.info("Folder found without info.csv in %s: %s", chnl, folder)
            json_data = fetch(chnl, dt_start, dt_end)
            if "stream.mpeg2.ts" in files:
                filepath = os.path.join(fpath, "stream.mpeg2.ts")
                actual_duration = get_metadata(filepath)

            if not actual_duration:
                actual_duration = duration

            match_data = configure_data(
                json_data, dt_start, duration, actual_duration, chnl
            )
            if not match_data:
                LOGGER.info("No matching EPG programme for this folder")
                continue
            LOGGER.info("Matched data found: %s", match_data)

            # Create info.csv and write data to it
            csv_path = os.path.join(fpath, "info.csv")
            LOGGER.info("Writing data to %s", csv_path)
            write_to_csv(csv_path, match_data)

    LOGGER.info("MAKE INFO FROM SCHEDULE END ==============================\n")


def write_to_csv(pth, data):
    """
    Open CSV and write new data string to it
    """

    with open(pth, "a+", newline="") as cfile:
        csv_out = csv.writer(cfile)
        csv_out.writerows([data])
    cfile.close()


if __name__ == "__main__":
    main()
