#!/usr/bin/env python3

'''
Script that iterates through folders, looking for stream.mpeg2.ts
files, then extract UTC metadata and descriptions.

main():
1. Create list of folders for yesterday's and today's recordings
2. Iterate each list, extract programme start time and duration
   and check if end time is less than time. If not skip.
3. Use mediainfo to capture all lines UTC metadata lines that
   feature 'Running' in the data, and check for UTC start time
   matches with folder start time.
4. If yes, extract metadata into list of title, description etc.
   If no, then skip this file as metadata may be inaccurate
5. Use pandas to create CSV file and dump data to it, save
   alongside stream in file called 'info.csv'

2022
'''

import os
import csv
import logging
import subprocess
from datetime import datetime, timedelta

# Static global variables
FORMAT = '%Y-%m-%d %H-%M-%S'
STORAGE_PATH = os.environ['STORAGE_PATH']
STORA_PTH = os.environ['STORA_PATH']
CODEPTH = os.environ['CODE']
FOLDERS = os.environ['STORA_FOLDERS']
CONFIG_FILE = os.path.join(CODEPTH, 'stream_config.json')
TODAY = datetime.now()
YEST = TODAY - timedelta(1)
DATE_PATH = os.path.join(STORAGE_PATH, f"{str(TODAY)[0:4]}/{str(TODAY)[5:7]}/{str(TODAY)[8:10]}/")
YEST_PATH = os.path.join(STORAGE_PATH, f"{str(YEST)[0:4]}/{str(YEST)[5:7]}/{str(YEST)[8:10]}/")
TODAY_DATE = f"{str(TODAY)[0:4]}-{str(TODAY)[5:7]}-{str(TODAY)[8:10]}"
YEST_DATE = f"{str(YEST)[0:4]}-{str(YEST)[5:7]}-{str(YEST)[8:10]}"

# Setup logging
LOGGER = logging.getLogger('get_stream_info')
HDLR = logging.FileHandler(os.path.join(FOLDERS, 'logs/get_stream_info.log'))
FORMATTER = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
HDLR.setFormatter(FORMATTER)
LOGGER.addHandler(HDLR)
LOGGER.setLevel(logging.INFO)

CHANNELS = {'bbconehd': 'BBC One HD',
            'bbctwohd': 'BBC Two HD',
            'bbcthree': 'BBC Three HD',
            'bbcfourhd': 'BBC Four HD',
            'bbcnewshd': 'BBC NEWS HD',
            'cbbchd': 'CBBC HD',
            'cbeebieshd': 'CBeebies HD',
            'channel4': 'Channel 4 HD',
            'five': 'Channel 5 HD',
            'film4': 'Film4',
            '5star': '5STAR',
            'itv1': 'ITV HD',
            'itv2': 'ITV2',
            'itv3': 'ITV3',
            'itv4': 'ITV4',
            'e4': 'E4',
            'more4': 'More4'}


def get_end_time(folder, date):
    '''
    Cut up folder start time/duration
    and return as datetime object
    '''

    tm = folder[0:8]
    duration = folder[-8:]
    dur = duration.replace('-', ':')
    print(f"{tm} ---- {duration}")
    dt_str = f"{date} {tm}"
    dt_start = datetime.strptime(dt_str, FORMAT)
    hours, mins, secs = duration.split('-')
    minutes = int(timedelta(hours=int(hours), minutes=int(mins), seconds=int(secs)).total_seconds()) / 60
    dt_end = dt_start + timedelta(minutes=minutes)
    return (dt_end, dt_start, dur)


def get_metadata(filepath):
    '''
    Use subprocess to capture list of 'Running'
    '''

    cmd = [
        'mediainfo',
        filepath
    ]

    try:
        mdata = subprocess.check_output(cmd)
    except Exception as err:
        LOGGER.warning("Error with subprocess call: %s", err)

    running_list = []
    if mdata:
        mdata = mdata.decode()
        mdata = mdata.split('\n')
        for m in mdata:
            if 'Running' in str(m) or 'Not running' in str(m):
                running_list.append(m)

        return running_list


def configure_data(metadata, channel, actual_duration):
    '''
    Cut up metadata string and format for CSV write
    '''

    for key, val in CHANNELS.items():
        if key == channel:
            chnl = val

    if type(metadata) == list:
        metadata = metadata[0]

    data = metadata.split(' / ')
    if len(data) == 6:
        utc = data[0].split('     ')[0]
        time = utc.split(' ')[1].strip()
        date = utc.split(' ')[0].strip()
        title = data[0].split('en:')[-1].strip()
        title = title.replace('\x86', '')
        title = title.replace('\x87', '')
        desc = data[1].split('en:')[-1].strip()
        duration = data[-2].strip()
        if not actual_duration:
            actual_duration = duration
        return [chnl, title, desc, date, time, duration, actual_duration]
    else:
        return None


def check_times(mdata, dt_start):
    '''
    Get dt_start time from folder
    and metadata 'Running list'
    Check they match
    '''

    start = dt_start.strftime('%Y-%m-%d %H:%M:%S')
    if str(start) not in str(mdata):
        return None
    return mdata


def get_duration(fpath):
    '''
    Mediainfo retrieval of duration and reform to HH:MM:SS
    '''

    cmd = [
        'mediainfo', '--Language=raw',
        '--Full', '--Inform="General;%Duration/String3%"',
        fpath
    ]
    cmd[3] = cmd[3].replace('"', '')
    duration = subprocess.check_output(cmd)
    duration = duration.decode('utf-8')
    print(duration)
    if len(duration) > 8:
        return str(duration)[:8]


def main():
    '''
    Iterate today's/yesterday's redux paths looking
    for folders that have end times > now time
    Where found create info.csv if not
    already present
    '''

    LOGGER.info("GET STREAM INFO START ==============================")

    for chnl in CHANNELS.keys():
        spath = os.path.join(DATE_PATH, chnl)
        ypath = os.path.join(YEST_PATH, chnl)

        try:
            s_folders = [x for x in os.listdir(spath) if os.path.isdir(os.path.join(spath, x))]
            s_folders.sort()
            num_fold = len(s_folders) - 1
        except Exception:
            s_folders = []

        # Ensure last folder is never processed (allow for full duration)
        for num in range(0, num_fold):
            folder = s_folders[num]
            running_data = []
            actual_duration = ''
            fpath = os.path.join(spath, folder)
            dt_end, dt_start, duration = get_end_time(folder, TODAY_DATE)
            now = datetime.utcnow()
            if now > dt_end:
                files = os.listdir(fpath)
                if 'info.csv' in files:
                    continue
                if 'stream.mpeg2.ts' in files:
                    LOGGER.info("Working in channel: %s", chnl)
                    LOGGER.info("Trying folder: %s", fpath)
                    LOGGER.info("Broadcast end: %s", datetime.strftime(dt_end, FORMAT))
                    LOGGER.info("Passed end time for broadcast, checking for metadata 'Running' data")
                    streampath = os.path.join(fpath, 'stream.mpeg2.ts')
                    try:
                        os.chmod(streampath, 0o777)
                    except OSError as err:
                        print(err)
                    actual_duration = get_duration(streampath)
                    running_data = get_metadata(streampath)
                    if not running_data:
                        LOGGER.warning("No 'Running' metadata found in this folderpath: %s", streampath)
                        continue

            match = ''
            if len(running_data) > 1:
                LOGGER.info("Multiple 'Running' outputs, checking which matches folder start time")
                LOGGER.info("%s", running_data)
                # Run comparison
                for d in running_data:
                    match = check_times(d, dt_start)
                    if match:
                        break
            elif len(running_data) == 1:
                LOGGER.info("Single 'Running' output, confirming it matches folder start time")
                LOGGER.info("%s", running_data)
                match = check_times(running_data, dt_start)

            if not match:
                continue
            match_data = configure_data(match, chnl, actual_duration)
            LOGGER.info("Matched data found: %s", match_data)
            # Create info.csv and write data to it
            csv_path = os.path.join(fpath, 'info.csv')
            LOGGER.info("Writing data to: %s", csv_path)
            if match_data:
                write_to_csv(csv_path, match_data)

        try:
            y_folders = [x for x in os.listdir(ypath) if os.path.isdir(os.path.join(ypath, x))]
            y_folders.sort()
            num_fold = len(y_folders) - 1
        except Exception:
            y_folders = []

        if not y_folders:
            continue

        # Ensure last folder is never processed (allow for full duration)
        for num in range(0, num_fold):
            folder = y_folders[num]
            actual_duration = ""
            running_data = []
            fpath = os.path.join(ypath, folder)
            dt_end, dt_start, duration = get_end_time(folder, YEST_DATE)
            now = datetime.utcnow()
            if now > dt_end:
                files = os.listdir(fpath)
                if 'info.csv' in files:
                    continue
                if 'stream.mpeg2.ts' in files:
                    LOGGER.info("Working in channel: %s", chnl)
                    LOGGER.info("Trying folder: %s", fpath)
                    LOGGER.info("Broadcast end: %s", datetime.strftime(dt_end, FORMAT))
                    LOGGER.info("Passed end time for broadcast, checking for metadata 'Running' data")
                    streampath = os.path.join(fpath, 'stream.mpeg2.ts')
                    actual_duration = get_duration(streampath)
                    running_data = get_metadata(streampath)
                    if not running_data:
                        LOGGER.warning("No 'Running' metadata found in this folderpath: %s", streampath)
                        continue
            if len(running_data) > 1:
                LOGGER.info("Multiple 'Running' outputs, checking which matches folder start time")
                LOGGER.info("%s", running_data)
                # Run comparison
                for d in running_data:
                    match = check_times(d, dt_start)
                    if match:
                        break
            elif len(running_data) == 1:
                LOGGER.info("Single 'Running' output, confirming it matches folder start time")
                LOGGER.info("%s", running_data)
                match = check_times(running_data, dt_start)

            if not match:
                continue
            match_data = configure_data(match, chnl, actual_duration)
            LOGGER.info("Matched data found: %s", match_data)
            # Create info.csv and write data to it
            csv_path = os.path.join(fpath, 'info.csv')
            LOGGER.info("Writing data to %s", csv_path)
            write_to_csv(csv_path, match_data)

    LOGGER.info("GET STREAM INFO END ==============================\n")


def write_to_csv(pth, data):
    '''
    Open CSV and write new data string to it
    '''

    with open(pth, 'a+', newline='') as cfile:
        csv_out = csv.writer(cfile)
        csv_out.writerows([data])
    cfile.close()


if __name__ == '__main__':
    main()
