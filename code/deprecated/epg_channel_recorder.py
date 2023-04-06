#!/usr/bin/env python3

'''
A script to capture network streams using VLC, based on a channel schedule.
Receives the CHANNEL information from launch command argument in crontab.
Has to be run in virtual environment to access Tenacity & VLC Python bindings.

main():
1. Checks CHANNEL argument received by sys.argv[1].
2. Calculates launch time and configures recording date for channels/schedules.
3. Load the day's schedule for channel received and maps all programmes to a
   'recordings' dictionary. Stores last modification time for the schedule.
4. Launches while loop which continues until busy=False, ie no more scheduled
   recordings for today. The loop runs through these steps continually:
   i. Checks schedule for new modification, if altered then reloads schedule
      to accomodate any changes introduced to programme start/end times.
   ii. Checks if any existing recordings end times older than now in the 'handles'
      dictionary which contains details of items currently recording. If so the
      recording is stopped and the item handle is added to a recordings_deleted
      dictionary, and the item is removed from handled dictionary.
   iii. Checks through recordings dictionary items for any programmes
      not yet being recorded and whose start time is older than the time now.
      If found an MPEG TS folder is created and a VLC instance is launched and
      recording begins.
   iv. Deleted any items in recordings_deleted dictionary from recordings
      dictionary.
   v. Calculates if any items remain in handles and recordings dictionary. If no,
      then busy=False and the script exits.
   vi. Checks if stora_control.json requires recording to stop for this channel.
      If active==False, then the VLC recordings are ended immediately and the
      script exits.

Developed with inspiration from a Py2 script found on code.activestate.com:
https://code.activestate.com/recipes/579096-vlcpy-stream-capture-scheduler-script/

Joanna White
2022
'''

import os
import sys
import time
import json
import datetime
import tenacity
import vlc

# Static global variables
CHANNEL = sys.argv[1]
FORMAT = '%Y-%m-%d %H:%M:%S'
STR_PATH = os.environ['STORAGE_PATH']
CODEPTH = os.environ['CODE']
LOG_FILE = os.path.join(CODEPTH, f'logs/epg_channel_recorder_{CHANNEL}.log')
CONFIG_FILE = os.path.join(CODEPTH, 'stream_config.json')
SCHEDULES = os.path.join(CODEPTH, 'schedules/')
SAMPLES = os.path.join(CODEPTH, 'samples/')
STORA_CONTROL = os.path.join(CODEPTH, 'stora_control.json')


def check_control():
    '''
    This is a method to stop the recording when
    channel == False in STORA_CONTROl
    '''

    with open(STORA_CONTROL, 'r') as file:
        cjson = json.load(file)

    for key, val in cjson.items():
        if key == CHANNEL:
            return val


def time_calc():
    '''
    Checks if script launch is just before
    midnight or on recording day
    '''

    now = str(datetime.datetime.now())
    if ' 23:5' in now:
        return str(datetime.date.today() + datetime.timedelta(days=1))

    return str(datetime.date.today())


def write_print(text):
    '''
    Write data to LOG_FILE
    '''

    with open(LOG_FILE, 'a') as file:
        file.write(f"{text}\n")


def time_print(text, date_time=None):
    '''
    Print to STDOUT with a datetime prefix. If no timestamp is provided,
    the current date and time will be used.
    '''

    if date_time is None:
        now = datetime.datetime.utcnow()
        date_time = now.strftime('%H:%M:%S')

    write_print(f"{date_time}  {text}")


def indent_print(text):
    '''
    Print to STDOUT with an indent matching the timestamp printout in
    time_Print(). Capture for stream logs
    '''

    write_print(f"\t    {text}")


def load_channel_config(silent=False):
    '''
    Load the stream configuration file.
    '''

    with open(CONFIG_FILE, 'r') as file:
        cjson = json.load(file)

    for key, val in cjson.items():
        if key == CHANNEL:
            channel_config = {f"{key}": f"{val}"}

    if not silent:
        write_print(f"{channel_config} channel available.")

    return channel_config


@tenacity.retry(stop=tenacity.stop_after_attempt(5))
def load_schedule(sched_path, silent=False):
    '''
    Load the scheduled recordings file
    Tenacity to enable retry if schedule
    presently being overwritten
    '''

    try:
        with open(sched_path, 'r') as file:
            rjson = json.load(file)
        recordings = len(rjson)
        if not silent:
            write_print(f"{recordings} recordings scheduled.")
        return rjson
    except Exception as err:
        print(err)


@tenacity.retry(stop=tenacity.stop_after_attempt(5))
def get_mod_time(mod_time_prev, date):
    '''
    Retrieve modification time
    of current schedule, seconds since
    epoch time of file.
    '''

    schedule = os.path.join(SCHEDULES, f"{CHANNEL}_schedule_{date}.json")
    mod_time = os.path.getmtime(schedule)
    if mod_time != mod_time_prev:
        return mod_time


def parse_schedule(schedule, channels):
    '''
    Parse the schedule and return recordings dictionary
    with one entry per programme including RTP url, channel
    start, end times, programme title and SID.
    '''

    recordings = {}
    schedules = len(schedule)

    for jsn in range(0, schedules):
        entry = schedule[jsn]

        # Recording start time
        start = entry['start']
        date_time = datetime.datetime.strptime(start, FORMAT)
        channel = entry['channel']

        # Get programme name
        programme = None

        if 'programme' in entry:
            programme = entry['programme']

        address = ''
        for key, val in channels.items():
            if key == CHANNEL:
                address = val

        address_split = address.split(',')
        pid = f"{start} {channel}"

        # Check for an endtime or a duration
        endtime = None
        offset = None

        if 'end' in entry:
            endtime = datetime.datetime.strptime(entry['end'], FORMAT)

        if 'duration' in entry:
            duration = entry['duration']
            offset = date_time + datetime.timedelta(minutes=duration)

        # Check to see which gives the longer recording - the duration or end timestamp
        if offset is not None and endtime is not None:
            if offset > endtime:
                endtime = offset

        elif offset is not None:
            endtime = offset

        elif endtime is None and offset is None:
            # No valid duration/end time in JSON schedule try stream 'now'/'next' duration retrieval
            write_print(f"End or duration missing for scheduled recording {date_time} ({channel}).")
            continue

        elif endtime is not None and endtime < date_time:
            # End is earlier than the start!
            write_print(f"End timestamp earlier than start! Cannot record {date_time} ({channel}).")

        recordings[pid] = {
            'url': address_split[0],
            'channel': channel,
            'start': date_time,
            'duration': duration,
            'end': endtime,
            'programme': programme,
            'sid': address_split[1]
        }

    return recordings


def initialise_ts(chnl_path, start_time, duration):
    '''
    Uses programme start time and duration to
    build a new programme folder in chnl_path directory.
    Returns path for new stream.mpeg2.ts file.
    '''

    start_str = start_time.strftime(FORMAT)
    start = start_str[11:].replace(':', '-')
    seconds = duration * 60
    dur = time.strftime('%H-%M-%S', time.gmtime(seconds))
    dur = str(dur)

    # Folder creation for new mpeg file
    fname = f"{start}-{CHANNEL}-{dur}"
    if not os.path.exists(os.path.join(chnl_path, fname)):
        os.makedirs(os.path.join(chnl_path, fname))
        print(f"Created new directory {fname}")

    return os.path.join(chnl_path, fname, 'stream.mpeg2.ts')


def record_stream(instream, outfile):
    '''
    Record the network stream to the output file.
    Create VLC instance that creates demuxdump-append
    to stream, in case recording is a restart.
    '''

    inst = vlc.Instance('-vv', '--demux=dump', f"--demuxdump-file={outfile}", "--demuxdump-append")
    player = inst.media_player_new() # Create a player instance
    media = inst.media_new(instream)
    media.get_mrl()
    player.set_media(media)
    return (inst, player, media)


@tenacity.retry(stop=tenacity.stop_after_attempt(5))
def initialise(sched_path, silent=False):
    '''
    Load the channel list and scheduled recordings.
    Tenacity to manage moments when schedule absent.
    '''

    channels = load_channel_config(silent) # Get the available channels
    schedule = load_schedule(sched_path, silent) # Get the schedule
    recordings = parse_schedule(schedule, channels) # Parse the schedule information

    if recordings:
        return recordings


def reload_schedule(sched_path, existing, running):
    '''
    Schedule reload only necessary if schedule
    checks scripts have updated recordings based
    on new duration timings
    '''

    now = datetime.datetime.utcnow() # Get the current timestamp
    revised = initialise(sched_path, True) # Get the revised schedule silently

    # Get the schedule id for each of the running recordings
    running_ids = {}
    for runs in running:
        sid = running[runs]['sid']
        running_ids[sid] = runs

    # Get the schedule id for each of the upcoming recordings
    upcoming_ids = {}
    for item in existing:
        sid = existing[item]['sid']
        upcoming_ids[sid] = item

    # Number of new entries
    new_rec = 0

    # Compare the revised schedule against the existing
    for revs in revised:
        data = revised[revs]
        sched_id = data['sid']
        endtime = data['end']

        # If this recording is already running
        if sched_id in running_ids:
            handle = running_ids[sched_id]

            # Check if it's the same channel and programme
            chnl = (data['channel'] == running[handle]['channel'])
            prog = (data['programme'] == running[handle]['programme'])

            # If it's the same channel and programme, check if we need to revise the end time
            if prog and chnl and endtime != running[handle]['end']:
                time_print('Changed end time for running recording:')

                if data['programme'] is not None:
                    indent_print(f"{data}(programme)s ({data}(channel)s)")
                else:
                    indent_print(f"{handle}")

                indent_print(f"{running[handle]['end'].strftime(FORMAT)} to {endtime.strftime(FORMAT)}")

                running[handle]['end'] = endtime

        # Otherwise, it's not a currently-running recording
        # We only want to consider programmes that haven't finished yet
        elif endtime > now:
            if sched_id in upcoming_ids:
                ids = upcoming_ids[sched_id]

                # Remove the old data so that it can be replaced with the new
                temp = existing.pop(ids, None)

                # Check if it's the same channel and programme
                chnl = (data['channel'] == temp['channel'])
                prog = (data['programme'] == temp['programme'])

                # Only notify a change if it's the same programme
                if temp != data and chnl and (prog or temp['programme'] is None):
                    time_print('Changes made to scheduled recording:')

                    if data['programme'] is not None:
                        indent_print("{data}(programme)s ({data}(channel)s)")
                    else:
                        indent_print(f"{ids}")

            else:
                new_rec += 1

            existing[revs] = data

    if new_rec > 0:
        time_print(f"Added {new_rec} new scheduled recordings.")

    return (existing, running)


def main():
    '''
    Launches just before midnight with tomorrows's date from cron
    to select correct schedule. Iterates through continually until
    no schedule entries remain. Exits upon completion.
    '''

    if len(sys.argv) != 2:
        time_print("Missing channel argument. Script cannot run!")
        sys.exit()

    # Calculates time to accommodate pre-midnight launch
    date = time_calc()
    date_path = os.path.join(STR_PATH, f"{date[0:4]}/{date[5:7]}/{date[8:10]}/")
    chnl_path = os.path.join(date_path, CHANNEL)

    # Get schedule name for day
    schedule = os.path.join(SCHEDULES, f"{CHANNEL}_schedule_{date}.json")
    mod_time = os.path.getmtime(schedule)
    recordings = initialise(schedule)
    handles = {}
    busy = True

    while busy:
        # Check for schedule modification change
        new_mod_time = get_mod_time(mod_time, date)
        if new_mod_time:
            # Update modification time and reload_schedule
            mod_time = new_mod_time
            (recordings, handles) = reload_schedule(schedule, recordings, handles)
            write_print("Schedules reloaded due to modification update")

        handles_deleted = recordings_deleted = []
        now = datetime.datetime.utcnow()
        # Check existing recordings
        hs = handles.keys()
        for h in hs:
            data = handles[h]
            end = data['end']
            channel = data['channel']
            programme = data['programme']
            if now > end:
                time_print(f"Finished recording {programme} ({channel}).")
                try:
                    data['player'].stop() # Stop playback
                    data['player'].release() # Close the player
                    data['inst'].release() # Destroy the instance
                    handles_deleted.append(h)
                except Exception as err:
                    time_print("Unable to destroy player reference due to error:")
                    write_print(str(err))

        # Deletion of handles item in dictionary
        if len(handles_deleted) > 0:
            for hd in handles_deleted:
                if hd in handles.keys():
                    print(f"=== HANDLE FOR DELETION {hd}")
                    del handles[hd]

        # Loop through the schedule
        rs = recordings.keys()
        for r in rs:
            data = recordings[r] # Schedule entry details
            start = data['start']
            duration = data['duration']
            end = data['end']
            channel = data['channel']
            programme = data['programme']
            # If we're not recording the stream but we're between the
            # start and end times for the programme, record it

            if r not in handles and (now > start):
                if now < end:
                    # Determine a suitable output filename
                    fn = initialise_ts(chnl_path, start, duration)
                    # Create the VLC instance and player
                    (inst, player, media) = record_stream(data['url'], fn)

                    # Store the handle to the VLC instance and relevant data
                    handles[r] = {
                        'inst': inst,
                        'player': player,
                        'media': media,
                        'end': end,
                        'programme': programme,
                        'channel': channel,
                        'sid': data['sid']
                    }

                    # Start the stream and hence the recording
                    player.play()
                    time_print("Started recording:")
                    indent_print(f"{programme} ({channel})")
                    indent_print(f"{start.strftime(FORMAT)} to {end.strftime(FORMAT)}")

                else:
                    time_print("Missed scheduled recording:")
                    indent_print(f"{programme} ({channel})")
                    indent_print(f"{start.strftime(FORMAT)} to {end.strftime(FORMAT)}")
                    write_print(f"*** Deleting key: {r}")

                # Remove the item from the schedule to prevent it being
                # processed again
                recordings_deleted.append(r)

        # Deletion of recording dictionary entry
        if len(recordings_deleted) > 0:
            for rd in recordings_deleted:
                try:
                    print(f"=== RECORDING FOR DELETION {rd}")
                    del recordings[rd]
                except KeyError:
                    pass

        # Count remaining keys/handles for today's schedule
        k = len(handles.keys()) + len(recordings.keys())
        busy = k > 0
        # Exit after last recording complete
        # Crontab independently launches next script for next day's schedule
        if not busy:
            time_print("Exiting...\n")

        check = check_control()
        if check == False:
            time_print("Script exit requested by stora_control.json")
            time_print("Ending current recording following exit request.")
            player.stop()
            player.release()
            inst.release()
            sys.exit("stora_control.json requests script exits")


if __name__ == '__main__':
    main()
