#!/usr/bin/env python3

"""
Script that creates subtitle.vtt files using
ccextractor to remove data from each mpeg_ts stream

main():
1. Iterate through channel folders looking for programme folders
   whose end times have completed (start time + duration > now)
2. Check if subtitles.vtt exists in folder with content
   If not, make subtitles.vtt from stream.mpeg2.ts

2022
"""

import logging
import os
import subprocess
from datetime import datetime, timedelta

# Static global variables
FORMAT = "%Y-%m-%d %H-%M-%S"
STORAGE_PATH = os.environ["STORAGE_PATH"]
CODEPTH = os.environ["CODE"]
FOLDERS = os.environ["STORA_FOLDERS"]
CONFIG_FILE = os.path.join(CODEPTH, "stream_config.json")
SCHEDULES = os.path.join(FOLDERS, "schedules/")
TODAY = datetime.now()
YEST = TODAY - timedelta(1)
DATE_PATH = os.path.join(
    STORAGE_PATH, f"{str(TODAY)[0:4]}/{str(TODAY)[5:7]}/{str(TODAY)[8:10]}/"
)
YEST_PATH = os.path.join(
    STORAGE_PATH, f"{str(YEST)[0:4]}/{str(YEST)[5:7]}/{str(YEST)[8:10]}/"
)
TODAY_DATE = f"{str(TODAY)[0:4]}-{str(TODAY)[5:7]}-{str(TODAY)[8:10]}"
YEST_DATE = f"{str(YEST)[0:4]}-{str(YEST)[5:7]}-{str(YEST)[8:10]}"

# Setup logging / yet to be implemented
LOGGER = logging.getLogger("radox_make_subtitles")
HDLR = logging.FileHandler(os.path.join(FOLDERS, "logs/radox_make_subtitles.log"))
FORMATTER = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")
HDLR.setFormatter(FORMATTER)
LOGGER.addHandler(HDLR)
LOGGER.setLevel(logging.INFO)

CHANNELS = [
    "bbconehd",
    "bbctwohd",
    "bbcthree",
    "bbcfourhd",
    "bbcnewshd",
    "cbbchd",
    "cbeebieshd",
    "channel4",
    "five",
    "film4",
    "5star",
    "itv1",
    "itv2",
    "itv3",
    "itv4",
    "more4",
    "e4",
]


def get_end_time(folder, date):
    """
    Cut up folder start time/duration
    and return as datetime object
    """

    tm = folder[0:8]
    duration = folder[-8:]
    print(f"{tm} ---- {duration}")
    dt_str = f"{date} {tm}"
    dt_start = datetime.strptime(dt_str, FORMAT)
    h, m, s = duration.split("-")
    minutes = (
        int(timedelta(hours=int(h), minutes=int(m), seconds=int(s)).total_seconds())
        / 60
    )

    return dt_start + timedelta(minutes=minutes)


def make_vtt(filepath, folder):
    """
    Use subprocess to create VTT file
    """
    try:
        os.chmod(filepath, 0o777)
    except OSError as err:
        print(err)

    outpath = os.path.join(folder, "subtitles.vtt")

    cmd = ["ccextractor", "-out=webvtt", filepath, "-o", outpath]

    try:
        subprocess.call(cmd)
        return True
    except Exception as err:
        LOGGER.warning("Error with subprocess call: %s", err)


def main():
    """
    Iterate today's/yesterday's redux paths looking
    for folders that have end times > now time
    Where found create subtitles.vtt if not
    already present.
    """
    LOGGER.info("MAKE SUBTITLES START ==============================")

    for chnl in CHANNELS:
        spath = os.path.join(DATE_PATH, chnl)
        ypath = os.path.join(YEST_PATH, chnl)
        if not os.path.exists(spath):
            continue
        s_folders = [
            x for x in os.listdir(spath) if os.path.isdir(os.path.join(spath, x))
        ]
        LOGGER.info("Working in channel: %s", chnl)
        for folder in s_folders:
            fpath = os.path.join(spath, folder)
            LOGGER.info("Trying folder: %s", folder)
            dt_end = get_end_time(folder, TODAY_DATE)
            now = datetime.utcnow()
            LOGGER.info("Broadcast end: %s", datetime.strftime(dt_end, FORMAT))
            if now > dt_end:
                files = os.listdir(fpath)
                if "subtitles.vtt" in files:
                    LOGGER.info("SKIPPING: Subtitle already exists")
                    continue
                if "stream.mpeg2.ts" in files:
                    LOGGER.info("Passed end time for broadcast, creating subtitles")
                    streampath = os.path.join(fpath, "stream.mpeg2.ts")
                    status = make_vtt(streampath, fpath)
                    if status:
                        LOGGER.info("Successfully created subtitle.vtt file")

        if not os.path.exists(ypath):
            continue
        y_folders = [
            x for x in os.listdir(ypath) if os.path.isdir(os.path.join(ypath, x))
        ]
        LOGGER.info("Working in channel: %s", chnl)
        for folder in y_folders:
            fpath = os.path.join(ypath, folder)
            LOGGER.info(f"Trying folder: %s", fpath)
            dt_end = get_end_time(folder, YEST_DATE)
            now = datetime.utcnow()
            LOGGER.info("Broadcast end: %s", datetime.strftime(dt_end, FORMAT))
            if now > dt_end:
                files = os.listdir(fpath)
                if "subtitles.vtt" in files:
                    LOGGER.info("SKIPPING: Subtitle already exists")
                    continue
                if "stream.mpeg2.ts" in files:
                    LOGGER.info("Passed end time for broadcast, creating subtitles")
                    streampath = os.path.join(fpath, "stream.mpeg2.ts")
                    status = make_vtt(streampath, fpath)
                    if status:
                        LOGGER.info("Successfully created subtitle.vtt file")

    LOGGER.info("MAKE SUBTITLES END ==============================\ns")


if __name__ == "__main__":
    main()
