#!/usr/bin/env python3

'''
Script to check stream now/next information
and update schedule if changes occur.

main():
1. Begin by iterating today's programme recordings
   but only those whose end time has passed.
2. Using subprocess extract list of data for 'Running'
   and 'Not running' UTC fields from mediainfo metadata
3. Indentify if the 'Running' programme has matching
   start time to scheduled item, and same channel
4. Compare title and duration for matches
5. If both match, skip to next
6. If duration does not match but title does:
   a. Extend duration and update schedule 'now'
   b. Calculate new start time for 'next' programme
   c. Check 'Not Running' metadata for matching
      item with new 'next' start time
   d. Extract duration, channel and programme name
      and generate new schedule dictionary
   e. Replace scheduled index with new 'next' dict
   f. Update logs with programme 'EXTENSION'
7. If duration does match but title does not:
   a. Leave as does not impact schedule recording
      or info.csv creation
8. If duration and title do not match:
   a - e. Same as 6 but with title changes
   f. Update logs with programme 'SUBSTITUTE'

Joanna White
2022
'''

import os
import json
import logging
import subprocess
from datetime import datetime, timedelta

# Static global variables
STORAGE_PATH = os.environ['STORAGE_PATH']
CODEPTH = os.environ['CODE']
LOG_FILE = os.path.join(CODEPTH, 'radox_channel_recorder.log')
CONFIG_FILE = os.path.join(CODEPTH, 'stream_config.json')
SCHEDULES = os.path.join(CODEPTH, 'schedules/')
SAMPLES = os.path.join(CODEPTH, 'samples/')
TODAY = datetime.utcnow()
START = TODAY.strftime('%Y-%m-%d')
DATE_PATH = os.path.join(STORAGE_PATH, f"{START[0:4]}/{START[5:7]}/{START[8:10]}/")
DATE = f"{START[0:4]}-{START[5:7]}-{START[8:10]}"
FORMAT = '%Y-%m-%d %H:%M:%S'

# Setup logging / yet to be implemented
LOGGER = logging.getLogger('stream_schedule_checks')
HDLR = logging.FileHandler(os.path.join(CODEPTH, 'logs/stream_schedule_checks.log'))
FORMATTER = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
HDLR.setFormatter(FORMATTER)
LOGGER.addHandler(HDLR)
LOGGER.setLevel(logging.INFO)

CHANNELS = {
#    'bbconehd': 'BBC One HD',
#    'bbctwohd': 'BBC Two HD',
#    'bbcthree': 'BBC Three HD',
#    'bbcfourhd': 'BBC Four HD',
#    'bbcnewshd': 'BBC NEWS HD',
#    'cbbchd': 'CBBC HD',
#    'cbeebieshd': 'CBeebies HD',
#    'citv': 'CITV',
    'channel4': 'Channel 4 HD',
    'film4': 'Film4'
#    'five': 'Channel 5 HD',
#    '5star': '5STAR',
#    'itv1': 'ITV HD',
#    'itv2': 'ITV2',
#    'itv3': 'ITV3',
#    'itv4': 'ITV4',
#    'more4': 'More4'
}


def get_metadata(filepath):
    '''
    Use subprocess to capture list of 'Running'
    and 'Not running' content
    '''

    mdata = []
    if not os.path.exists(filepath):
        print(f"No PATH: {filepath}")

    cmd = ['mediainfo',
           filepath]

    try:
        mdata = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as err:
        print(err.output)

    running_list = []
    if not mdata:
        return None
    mdata = mdata.decode()
    mdata = mdata.split('\n')
    for line in mdata:
        if '/ Running' in str(line):
            running_list.append(line)
        if '/ Not running' in str(line):
            running_list.append(line)

    return running_list


def configure_data(metadata):
    '''
    Cut up metadata string and format for CSV write
    '''

    if type(metadata) == list:
        metadata = metadata[0]

    data = metadata.split(' / ')
    if len(data) == 6:
        utc = data[0].split('     ')[0]
        date = utc.split(' ')[1].strip()
        utc_time = utc.split(' ')[2].strip()
        raw_title = data[0].split('en:')[-1].strip()
        title = ''.join([i if ord(i) < 128 else '' for i in raw_title])
        duration = data[-2].strip()
        # convert duration HH:MM:SS to minutes
        hour, mins, sec = duration.split(':')
        minutes = int(timedelta(hours=int(hour), minutes=int(mins), seconds=int(sec)).total_seconds()) // 60
        date_time = f"{date} {utc_time}"
        return (title, date_time, minutes)
    else:
        return None


def get_datetime(folder, date):
    '''
    Cut up folder start time/duration
    and return as datetime object
    '''

    print(folder)
    tm = folder[0:8]
    tm = tm.replace('-', ':')
    duration = folder[-8:]
    print(f"Folder timings: Start {tm} - Duration {duration}")
    dt_str = f"{date} {tm}"
    dt_start = datetime.strptime(dt_str, FORMAT)
    hour, mins, sec = duration.split('-')
    minutes = int(timedelta(hours=int(hour), minutes=int(mins), seconds=int(sec)).total_seconds()) / 60
    dt_end = dt_start + timedelta(minutes=minutes)
    return dt_end


def open_schedule(schedule_path):
    '''
    Open schedule and return as list of dicts
    '''

    with open(schedule_path) as json_file:
        data = json.load(json_file)
    return data


def check_for_match(sched_dict, utc_title, utc_time, utc_dur, chnl):
    '''
    Check for matching data in key, values of sched_dict
    '''

    s_dur = sched_dict.get('duration')
    s_chnl = sched_dict.get('channel')
    s_prog = sched_dict.get('programme')
    print(sched_dict)
    print(s_prog, s_dur, s_chnl)
    print(utc_title, utc_dur, chnl)
    new_dct = {}
    if chnl != s_chnl:
        return None

    if str(s_dur) != str(utc_dur):
        print(f"Replacing {s_prog} with {utc_title}")
        print(f"New duration is {utc_dur} mins, not {s_dur} minutes")
        new_dct['start'] = utc_time
        new_dct['duration'] = utc_dur
        new_dct['channel'] = chnl
        new_dct['programme'] = utc_title
        return new_dct


def get_next_start_time(utc_dt, utc_dur):
    '''
    Get UTC start time/duration from current recording
    Calculate new start time for next programme
    '''

    dt_start = datetime.strptime(utc_dt, FORMAT)
    utc_dur = int(utc_dur)
    dt_end = dt_start + timedelta(minutes=utc_dur)
    print(dt_end, type(dt_end), dt_end.strftime(FORMAT))
    return dt_end.strftime(FORMAT)


def get_next_dct(next_dt_start, chnl, data=None):
    '''
    Iterate 'Not running' returns looking for new
    start date match, create new dictionary entry
    '''

    print(f"get_next_dct(): Recieved {next_dt_start}, {chnl}, {data}")
    if data is None:
        return None

    title = dt = dur = ''
    for entry in data:
        if next_dt_start in str(entry):
            title, dt, dur = configure_data(entry)
    print("Title retrieved: {title}")

    if title:
        next_dct = {}
        next_dct['start'] = dt
        next_dct['duration'] = dur
        next_dct['channel'] = chnl
        next_dct['programme'] = title
        return next_dct


def check_remaining_schedule(schedule, sched_time, index, total_index):
    '''
    With next item's end time as sched_time,
    check if any remaining schedule range
    have sched_time > start time.
    If so, remove as no longer relevant.
    '''

    delete_list = []
    index = index + 1

    for num in range(index, total_index):
        dct = schedule[num]
        start = dct["start"]
        sched_start = datetime.strptime(start, FORMAT)
        if sched_time > sched_start:
            print(f"Schedule to be deleted: {dct}")
            delete_list.append(schedule[num])

    for item in delete_list:
        schedule.remove(item)
    return schedule


def get_endtime(start, dur):
    '''
    Return endtime formatted:
    YYYY-mm-dd HH:MM:SS strftime
    '''

    sched_start = datetime.strptime(start, FORMAT)
    end_dt = sched_start + timedelta(minutes=int(dur))
    return end_dt


def main():
    '''
    Iterate channels, extract schedule to dictionary
    Test stream metadata and fetch timings
    Replace in schedule where durations don't match
    '''

    # Temp start for limited channel access
    for chnl in CHANNELS.keys():
        # Get paths
        chnl_path = os.path.join(DATE_PATH, chnl)
        if not os.path.exists(chnl_path):
            continue
        print(f"Channel being checked {chnl}")
        # Load today's schedule (list of dicts)
        schedule_path = os.path.join(SCHEDULES, f"{chnl}_schedule_{DATE}.json")
        schedule = open_schedule(schedule_path)
        folders = [d for d in os.listdir(chnl_path) if os.path.isdir(os.path.join(chnl_path, d))]

        for folder in folders:
            # Skip if programme finished recording
            rec_end = get_datetime(folder, DATE)
            now = datetime.now()
            if now > rec_end:
                continue

            filepath = os.path.join(chnl_path, folder, 'stream.mpeg2.ts')
            # Extract metadata lines to data[0] 'Running' and data[1] 'Not running'
            data = get_metadata(filepath)
            if not data:
                print(f"No metadata available for this stream: {filepath}")
                continue

            for entry in data:
                mismatched = []
                # Get UTC stream metadata per entry
                utc_title, utc_dt, utc_dur = configure_data(entry)
                print(f"UTC entry: Title {utc_title} - Datetime {utc_dt} - Duration {utc_dur}")
                # Retrieve schedule indexes for entries with matching start time
                index = [i for i, x in enumerate(schedule) if utc_dt in str(x)]
                if len(index) != 1:
                    continue
                print(f"Schedule datetime match: {schedule[index[0]]}")
                # matched must return [{dicts}]
                mismatched = check_for_match(schedule[index[0]], utc_title, utc_dt, utc_dur, chnl)
                if not mismatched:
                    continue

                # Here replace index of dict with new returned one
                LOGGER.info("STREAM_SCHEDULE_CHECKS START - %s - %s =========================", chnl, folder)
                LOGGER.info("UTC Entry: %s, %s mins, %s", utc_dt, utc_dur, utc_title)
                LOGGER.info("MISMATCH FOUND IN DATA: \nOriginal schedule:\n%s\n\nNew schedule:\n%s", schedule[index[0]], mismatched)
                print(f"Replacing:\n {schedule[index[0]]}\n-----------\n{mismatched}")
                schedule[index[0]] = mismatched

                # Check if remaining programmes in schedule and action 'next' updates
                next_index = index[0] + 1
                print(f"******* NEXT INDEX: {next_index} LENGTH OF SCHED: {len(schedule)} *********")
                if next_index < len(schedule):
                    # Update the next item's start time
                    next_dt_start = get_next_start_time(utc_dt, utc_dur)
                    LOGGER.info("Calculating new start time for next programme: %s", next_dt_start)
                    print(f"Next programme's start time: {next_dt_start}")
                    next_sched = get_next_dct(next_dt_start, chnl, data)
                    print(f"Next schedule: {next_sched}")
                    if not next_sched:
                        LOGGER.info("Next scheduled item absent for new start time %s. Abandoning schedule update.", next_dt_start)
                        continue

                    # Assess if schedule should have 'next' inserted or updated
                    next_dt_sched = datetime.strptime(schedule[next_index]['start'], FORMAT)
                    next_dt_end = get_endtime(next_sched['start'], next_sched['duration'])
                    next_schedule_mins = int(schedule[next_index]['duration'])

                    if next_dt_end <= next_dt_sched or next_schedule_mins <= 5:
                        # Next schedule to be inserted
                        new_schedule = []
                        for num in range(0, next_index):
                            new_schedule.append(schedule[num])
                        new_schedule.append(next_sched)
                        LOGGER.info("Inserting new dictionary entry for next item: %s", next_sched)
                        for num in range(next_index, len(schedule)):
                            new_schedule.append(schedule[num])
                        # Remove shcedule items that might be overlapping
                        new_schedule = check_remaining_schedule(new_schedule, next_dt_end, next_index, len(new_schedule))

                    else:
                        # Update next start time
                        schedule[next_index].update({"start": f"{next_sched['start']}"})
                        LOGGER.info("Next schedule entry updated with start time only from:\n%s", next_sched)
                        # Remove items that have start time before end of next programme
                        new_schedule = check_remaining_schedule(schedule, next_dt_end, next_index, len(schedule))

                    orig_sched = []
                    orig_sched = open_schedule(schedule_path)

                    if orig_sched != new_schedule:
                        LOGGER.info("********* ORIGINAL SCHEDULE:\n%s", orig_sched)
                        LOGGER.info("********* NEW SCHEDULE:\n%s", new_schedule)
                        print(orig_sched)
                        print(new_schedule)

                    # Overwrite schedule dumping new dict to same filename
                    with open(schedule_path, 'w') as jsf:
                        json.dump(new_schedule, jsf, indent=4)

                    LOGGER.info("STREAM_SCHEDULE_CHECKS END - %s - %s ===========================", chnl, folder)


if __name__ == '__main__':
    main()
