#!/usr/bin/env python3

'''
Script to check stream now/next information
and update schedule if changes occur.

main():
1. Begin iteration of CHANNEL keys and build
   path to today's date/channel STORA recordings.
2. Load today's schedule to memory as dict.
3. Compile list of folders, iterate list to locate
   folder that is currently recording.
4. Extract CHANNEL UDP address and capture EIT
   for both 'now' (running status 4) and 'next' (1).
5. Check 'now' EIT data to see if matches with
   current schedule entry
   - Yes, items match and script skips to next CHANNEL
   - No, because start time absent from schedule,
     skips onto next CHANNEL
   - No, because there is data mismatch. New EIT
     data is swapped for existing schedule entry.
     Move onto step 6
6. Check if 'next' EIT data is present:
   - Yes, 'next' data is compiled into a new schedule
     entry. Remaining schedule items in dictionary checked
     against 'next' start datetime object. If any schedule
     datetimes are lt/et next datetime they are removed.
     The schedule is rebuilt into a new schedule feature
     the next programme in the queue.
   - No, no 'next' data compiled.
7. Re-opens schedule and saves to second dict, then
   compares the old dictionary schedule with the new.
   If there are changes the JSON schedule is opened
   and the new dictionary data is overwritten.

Joanna White
2022
'''

import os
import ast
import json
import time
import logging
import subprocess
from datetime import datetime, timedelta
import tenacity

# Static global variables
STORAGE_PATH = os.environ['STORAGE_PATH']
CODEPTH = os.environ['CODE']
CONFIG_FILE = os.path.join(CODEPTH, 'stream_config.json')
CONFIG_UDP = os.path.join(CODEPTH, 'stream_config_udp.json')
SCHEDULES = os.path.join(CODEPTH, 'schedules/')
SAMPLES = os.path.join(CODEPTH, 'samples/')
STORA_CONTROL = os.path.join(CODEPTH, 'stora_control.json')
TODAY = datetime.utcnow()
START = TODAY.strftime('%Y-%m-%d')
DATE_PATH = os.path.join(STORAGE_PATH, f"{START[0:4]}/{START[5:7]}/{START[8:10]}/")
DATE = f"{START[0:4]}-{START[5:7]}-{START[8:10]}"
FORMAT = '%Y-%m-%d %H:%M:%S'
FDATE = '%Y-%m-%d'
FTIME = '%H-%M-%S'
DVBTEE = os.environ['DVBTEE']

# Setup logging / yet to be implemented
LOGGER = logging.getLogger('stream_schedule_checks')
HDLR = logging.FileHandler(os.path.join(CODEPTH, 'logs/stream_schedule_checks_eit.log'))
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
            'citv': 'CITV',
            'five': 'Channel 5 HD',
            '5star': '5STAR',
            'itv1': 'ITV HD',
            'itv2': 'ITV2',
            'itv3': 'ITV3',
            'itv4': 'ITV4',
            # 'channel4': 'Channel 4 HD',
            # 'film4': 'Film4',
            'more4': 'More4'
}


def check_control():
    '''
    Check control JSON for script exit
    '''

    with open(STORA_CONTROL) as control:
        j = json.load(control)
        if not j['stora_qnap04']:
            logging.info("Script run prevented by stora_control.json. Script exiting.")
            sys.exit("Script run prevented by stora_control.json. Script exiting.")


def fetch_udp(channel):
    '''
    Return UDP stream for channel
    '''

    with open(CONFIG_UDP, 'r') as file:
        cjson = json.load(file)

    for key, val in cjson.items():
        if key == channel:
            return val


@tenacity.retry(stop=tenacity.stop_after_attempt(5))
def get_events(udp):
    '''
    Dump libdvbtee EIT data to dict
    then pass back to main
    '''

    cmd = [
        DVBTEE,
        '-i', udp,
        '-t5', '-j'
    ]

    capture = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    capture = capture.decode('latin1').splitlines()
    data = [x for x in capture if x.startswith('NET_SVC_ID#')]

    if not data:
        print("Problem with data retrieved")
        return None
    elif '"runningStatus":4' not in str(data) and '"runningStatus":1' not in str(data):
        print("Both runningStatus missing from stream data")
        return None
    else:
        try:
            split_d = data[0].split(': [')[1].rstrip(']')
            split_data = split_d.replace(':false,', ':False,')
            split_data_clean = split_data.replace(':true,', ':True,')
            jdata = ast.literal_eval(split_data_clean)
            return jdata
        except IndexError as err:
            print(err)
            return None


def read_eit(events):
    '''
    Search through event data
    clean up title, description entries
    then return dictionaries for running
    and not running entries
    '''

    running = {}
    not_running = {}

    for num in range(0, 2):
        try:
            event_id = events['events'][num]['eventId']
        except (IndexError, KeyError, TypeError):
            event_id = ''
        try:
            title = events['events'][num]['descriptors'][0]['name']
            title = title.replace('\x86', '')
            title = title.replace('\x87', '')
            title = title.replace('Â', '')
        except (IndexError, KeyError, TypeError):
            title = ''
        try:
            desc = events['events'][num]['descriptors'][0]['text']
            desc = desc.replace('\x86', '')
            desc = desc.replace('\x87', '')
            desc = desc.replace('Â', '')
        except (IndexError, KeyError, TypeError):
            desc = ''
        try:
            run_stat = events['events'][num]['runningStatus']
        except (IndexError, KeyError, TypeError):
            run_stat = ''
        try:
            ts_start = events['events'][num]['unixTimeBegin']
            start = datetime.utcfromtimestamp(ts_start).strftime(FTIME)
        except (IndexError, KeyError, TypeError):
            ts_start = ''
        try:
            ts_end = events['events'][num]['unixTimeEnd']
            end = datetime.utcfromtimestamp(ts_end).strftime(FTIME)
        except (IndexError, KeyError, TypeError):
            ts_end = ''

        if ts_end and ts_start:
            seconds = int(ts_end) - int(ts_start)
            duration = str(time.strftime(FTIME, time.gmtime(seconds)))
        else:
            duration = ''
        if str(run_stat) == '4':
            running[event_id] = f"{duration}, {start}, {end}, {run_stat}, {title}, {desc}"
        if str(run_stat) == '1':
            not_running[event_id] = f"{duration}, {start}, {end}, {run_stat}, {title}, {desc}"

    return running, not_running


def configure_duration(duration):
    '''
    Take %H-%M-%S duration
    convert to integer minutes
    '''

    hour, mins, sec = duration.split('-')
    minutes = int(timedelta(hours=int(hour), minutes=int(mins), seconds=int(sec)).total_seconds()) // 60
    return minutes


def get_datetime(folder, date):
    '''
    Cut up folder start time/duration
    and return as datetime object
    '''

    tm = folder[0:8]
    tm = tm.replace('-', ':')
    duration = folder[-8:]
    dt_str = f"{date} {tm}"
    dt_start = datetime.strptime(dt_str, FORMAT)
    hour, mins, sec = duration.split('-')
    minutes = int(timedelta(hours=int(hour), minutes=int(mins), seconds=int(sec)).total_seconds()) / 60

    return dt_start + timedelta(minutes=minutes)


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


def get_next_dct(start, chnl, duration, title):
    '''
    Create new dictionary entry for 'next'
    '''

    if start and chnl and duration and title:
        next_dct = {}
        next_dct['start'] = start
        next_dct['duration'] = duration
        next_dct['channel'] = chnl
        next_dct['programme'] = title
        return next_dct


def check_remaining_schedule(schedule, sched_time, index, total_index):
    '''
    With next programme's end time as sched_time,
    check if any remaining schedule range
    have sched_time > start time.
    If so, remove as no longer relevant.
    '''

    delete_list = []
    index = index + 1

    dt = datetime.strptime(sched_time, FORMAT)
    for num in range(index, total_index):
        dct = schedule[num]
        start = dct["start"]
        sched_start = datetime.strptime(start, FORMAT)
        if dt > sched_start:
            print(f"Schedule to be deleted: {dct}")
            delete_list.append(schedule[num])

    for item in delete_list:
        schedule.remove(item)
    return schedule


def main():
    '''
    Iterate channels, extract schedule to dictionary
    Collect UDP EIT data and fetch to variables
    Replace in schedule where durations don't match *now*
    Update *next* where different and remove schedules
    that are no longer relevant
    '''

    check_control()

    # Temp start for limited channel access
    for chnl in CHANNELS.keys():
        # Get paths
        chnl_path = os.path.join(DATE_PATH, chnl)
        if not os.path.exists(chnl_path):
            continue
        print(f"Channel being checked {chnl}")

        # Get channel's UDP address
        chnl_udp = fetch_udp(chnl)
        print(chnl_udp)

        # Load today's schedule (list of dicts)
        schedule_path = os.path.join(SCHEDULES, f"{chnl}_schedule_{DATE}.json")
        schedule = []
        schedule = open_schedule(schedule_path)
        folders = [d for d in os.listdir(chnl_path) if os.path.isdir(os.path.join(chnl_path, d))]

        for folder in folders:
            # Skip if programme over, out of scope for extending
            rec_end = get_datetime(folder, DATE)
            now = datetime.now()
            if now > rec_end:
                continue

            # Extract EIT data for active programme
            data = get_events(chnl_udp)
            if not data:
                print(f"No EIT retrieved available for this stream: {chnl}")
                continue
            data_dct = read_eit(data)

            if len(data_dct) != 2:
                continue
            running = data_dct[0]

            if len(running) == 0:
                continue
            for items in running.values():
                rsplit = items.split(', ')

            # Collect data to vars
            now_dur = rsplit[0]
            now_start = rsplit[1]
            now_end = rsplit[2]
            now_title = rsplit[4]
            now_duration = configure_duration(now_dur)
            print(f"UTC entry: Title {now_title} - Datetime {DATE} {now_start} - Duration {now_duration}")
            now_dt = f"{DATE} {now_start.replace('-',':')}"

            # Retrieve schedule indexes for entries with matching start time
            index = [i for i, x in enumerate(schedule) if now_dt in str(x)]
            if len(index) < 1:
                continue
            elif len(index) > 1:
                LOGGER.warning("More than one matching time found: %s", index)
                continue

            # Compare data to schedule and look for mismatch - must return [{dicts}]
            mismatched = []
            mismatched = check_for_match(schedule[index[0]], now_title, now_dt, now_duration, chnl)
            if not mismatched:
                continue

            # Here replace index of dict with new returned one
            LOGGER.info("STREAM_SCHEDULE_CHECKS - %s - %s =====================", chnl, folder)
            LOGGER.info("UTC Entry: %s %s, %s mins, %s", DATE, now_start, now_duration, now_title)
            LOGGER.info("MISMATCH FOUND IN DATA: \nOriginal schedule:\n%s\nNew schedule:\n%s", schedule[index[0]], mismatched)
            print(f"Replacing:\n {schedule[index[0]]}\n-----------\n{mismatched}")
            schedule[index[0]] = mismatched

            # Check if remaining programmes in schedule and action 'next' updates
            next_index = index[0] + 1

            # Collect EIT data for next programme
            not_running = data_dct[1]

            if next_index < len(schedule) and len(not_running) == 1:

                for items in not_running.values():
                    nrsplit = items.split(', ')

                next_dur = nrsplit[0]
                next_start = nrsplit[1]
                next_end = nrsplit[2]
                next_title = nrsplit[4]
                next_duration = configure_duration(next_dur)

                print(f"UTC entry: Title {next_title} - Datetime {DATE} {next_start} - Duration {next_duration}")
                LOGGER.info("UTC Entry: %s %s, %s mins, %s", DATE, next_start, next_duration, next_title)
                next_dt_start = f"{DATE} {next_start.replace('-',':')}"
                next_dt_end = f"{DATE} {next_end.replace('-',':')}"
                print(f"******* NEXT INDEX: {next_index} LENGTH OF SCHED: {len(schedule)} *********")

                # Assess if schedule should have 'next' inserted or updated
                next_dt_udp = datetime.strptime(next_dt_end, FORMAT)
                next_dt_sched = datetime.strptime(schedule[next_index]['start'], FORMAT)
                next_schedule_mins = int(schedule[next_index]['duration'])

                if next_dt_udp >= next_dt_sched or next_schedule_mins <= 5:
                    # Next schedule to be inserted
                    new_schedule = []
                    for num in range(0, next_index):
                        new_schedule.append(schedule[num])
                    next_sched = get_next_dct(next_dt_start, chnl, next_duration, next_title)
                    new_schedule.append(next_sched)
                    LOGGER.info("Inserting new dictionary entry for next item: %s", next_sched)
                    for num in range(next_index, len(schedule)):
                        new_schedule.append(schedule[num])
                    # Remove shcedule items that might be overlapping
                    new_schedule = check_remaining_schedule(new_schedule, next_dt_start, next_index, len(new_schedule))

                else:
                    # Update the next item's start time instead
                    next_duration = configure_duration(next_dur)
                    schedule[next_index].update({"start": f"{next_dt_start}"})
                    LOGGER.info("New start time for next programme: %s", next_dt_start)
                    # Remove schedule items that have been replaced by different start time
                    new_schedule = check_remaining_schedule(schedule, next_dt_start, next_index, len(schedule))

            orig_sched = []
            orig_sched = open_schedule(schedule_path)

            if orig_sched != new_schedule:
                LOGGER.info("********* ORIGINAL SCHEDULE:\n%s", orig_sched)
                LOGGER.info("********* NEW SCHEDULE:\n%s", new_schedule)

                # Overwrite schedule dumping new dict to same filename
                with open(schedule_path, 'w') as jsf:
                    json.dump(new_schedule, jsf, indent=4)

            LOGGER.info("STREAM_SCHEDULE_CHECKS END - %s - %s =====================\n", chnl, folder)


if __name__ == '__main__':
    main()
