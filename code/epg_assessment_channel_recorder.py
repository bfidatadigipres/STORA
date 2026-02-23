#!/usr/bin/env python3

"""
A script to capture RTP network streams using VLC
taking prompts from UDP EIT table 'runningStatus' data,
or where absent reverting to EPG schedule recording.
Has to be run in virtual environment to access VLC Python
bindings and Tenacity.

main():
-- running status recording --
1. Launches recording then monitors EIT 'runningStatus'
   data for change in the '4' running category.
   Uses libdvbtee to grab Network Service ID from EIT.
2. EIT not found check, script launches EPG schedule recording if script
   fails to find EIT 15 consecutive attempts (skip to step 6)
3. EIT found so loops continually while 'active'. To turn 'active' to False,
   control_json needs changing and script exits.
4. When a change is found in current recording, the script
   stops current VLC media instance, initialises a new
   stream recording in new folder path.
5. Starts the recording again and continues monitoring
   'runningStatus' for another change. Runs continually without break

launch_epg()
-- epg schedule recording --
6. Calculates launch time and configures recording date for channels/schedules.
7. Load the day's schedule for channel received and maps all programmes to a
   'recordings' dictionary. Stores last modification time for the schedule.
8. Launches while loop which continues until busy=False, ie no more scheduled
   recordings for the day. The loop runs through these steps continually:
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
9. Script completes EPG schedule recording and resets at start of code block in
   main() with rs checks for EIT re-establishment (step 1)

Partially developed with inspiration from a Py2 script found on code.activestate.com:
https://code.activestate.com/recipes/579096-vlcpy-stream-capture-scheduler-script/

Joanna White
2023
"""

import ast
import datetime
import json
import os
import subprocess
import sys
import time

import tenacity
import vlc

# Global variables
CHANNEL = sys.argv[1]
STORA_PATH = os.environ["STORAGE_PATH"]
FOLDERS = os.environ["STORA_FOLDERS"]
LOG_PATH = os.path.join(FOLDERS, f"logs/epg_channel_recorder_{CHANNEL}.log")
SCHEDULES = os.path.join(FOLDERS, "schedules/")
CODEPTH = os.environ["CODE"]
CONFIG_FILE = os.path.join(CODEPTH, "stream_config.json")
CONFIG_UDP = os.path.join(CODEPTH, "stream_config_udp.json")
CONTROL = os.path.join(CODEPTH, "stora_control.json")
TIMINGS = os.path.join(CODEPTH, "channel_timings.json")
DVBTEE = os.environ["DVBTEE"]
FORMAT = "%Y-%m-%d %H:%M:%S"
FTIME = "%H-%M-%S"


def check_control():
    """
    Read control doc and return value
    for supplied channel
    """
    with open(CONTROL, "r") as file:
        cjson = json.load(file)

    for key, val in cjson.items():
        if key == CHANNEL:
            return val


def time_calc():
    """
    Checks if script launch is just before
    midnight or on recording day
    """

    now = str(datetime.datetime.now())
    if " 23:5" in now:
        return str(datetime.date.today() + datetime.timedelta(days=1))

    return str(datetime.date.today())


def channel_timings(chnl):
    """
    Check channel for operational timings
    Return datetime start/stop for checks
    """
    with open(TIMINGS, "r") as t:
        time_data = json.load(t)
    for key, val in time_data.items():
        if chnl == key:
            start_time, duration = val.split(" - ")
    if not start_time:
        return None, None

    start = f"{str(datetime.date.today())} {start_time}"
    start_dt = datetime.datetime.strptime(start, FORMAT)
    end_dt = start_dt + datetime.timedelta(minutes=int(duration))
    return start_dt, end_dt


def fetch_udp():
    """
    Read UDP stream for channel
    """

    with open(CONFIG_UDP, "r") as file:
        cjson = json.load(file)

    for key, val in cjson.items():
        if key == CHANNEL:
            return val


def fetch_rtp():
    """
    Read stream_config and return
    list of items
    """

    with open(CONFIG_FILE, "r") as file:
        cjson = json.load(file)

    for key, val in cjson.items():
        if key == CHANNEL:
            return val.split(", ")[0]


def write_print(text, epg_arg):
    """
    Create new log if need then write
    supplied text to it with newline
    """
    if epg_arg:
        log_path = LOG_PATH
    else:
        now = datetime.datetime.utcnow().strftime("%Y/%m/%d")
        log_path = os.path.join(STORA_PATH, now, CHANNEL)
        if not os.path.exists(log_path):
            os.makedirs(log_path, exist_ok=True)
        log_path = os.path.join(log_path, "recording.log")

    f = open(log_path, "a")
    f.write(f"{text}\n")
    f.close()


def time_print(text, arg, dt=None):
    """
    Print to STDOUT with a datetime prefix. If no timestamp is provided,
    the current date and time will be used. Captured for stream logs
    """

    if dt is None:
        now = datetime.datetime.utcnow()
        dt = now.strftime("%H:%M:%S")

    write_print(f"{dt}  {text}", arg)


def indent_print(text, arg):
    """
    Print to STDOUT with an indent matching the timestamp printout in
    time_Print(). Captured for stream logs
    """

    write_print(f"\t    {text}", arg)


def load_channel_config(silent=False):
    """
    Load the stream configuration file.
    """

    with open(CONFIG_FILE, "r") as file:
        cjson = json.load(file)

    for key, val in cjson.items():
        if key == CHANNEL:
            channel_config = {f"{key}": f"{val}"}

    if not silent:
        write_print(f"{channel_config} channel available.", True)

    return channel_config


@tenacity.retry(stop=tenacity.stop_after_attempt(5))
def load_schedule(sched_path, silent=False):
    """
    Load the scheduled recordings file
    Tenacity to enable retry if schedule
    presently being overwritten
    """

    try:
        os.chmod(sched_path, 0o777)
    except OSError as err:
        write_print(f"Unable to modify permissions: {sched_path}\n{err}")
    try:
        with open(sched_path, "r") as file:
            rjson = json.load(file)
        recordings = len(rjson)
        if not silent:
            write_print(f"{recordings} recordings scheduled.", True)
        return rjson
    except Exception as err:
        print(err)


@tenacity.retry(stop=tenacity.stop_after_attempt(5))
def get_mod_time(mod_time_prev, date):
    """
    Retrieve modification time
    of current schedule, seconds since
    epoch time of file.
    """

    schedule = os.path.join(SCHEDULES, f"{CHANNEL}_schedule_{date}.json")
    mod_time = os.path.getmtime(schedule)
    if mod_time != mod_time_prev:
        return mod_time


def parse_schedule(schedule, channels):
    """
    Parse the schedule and return recordings dictionary
    with one entry per programme including RTP url, channel
    start, end times, programme title and SID.
    """

    recordings = {}
    schedules = len(schedule)

    for jsn in range(0, schedules):
        entry = schedule[jsn]

        # Recording start time
        start = entry["start"]
        date_time = datetime.datetime.strptime(start, FORMAT)
        channel = entry["channel"]

        # Get programme name
        programme = None

        if "programme" in entry:
            programme = entry["programme"]

        address = ""
        for key, val in channels.items():
            if key == CHANNEL:
                address = val

        address_split = address.split(",")
        pid = f"{start} {channel}"

        # Check for an endtime or a duration
        endtime = None
        offset = None

        if "end" in entry:
            endtime = datetime.datetime.strptime(entry["end"], FORMAT)

        if "duration" in entry:
            duration = entry["duration"]
            offset = date_time + datetime.timedelta(minutes=duration)

        # Check to see which gives the longer recording - the duration or end timestamp
        if offset is not None and endtime is not None:
            if offset > endtime:
                endtime = offset

        elif offset is not None:
            endtime = offset

        elif endtime is None and offset is None:
            # No valid duration/end time in JSON schedule try stream 'now'/'next' duration retrieval
            write_print(
                f"End or duration missing for scheduled recording {date_time} ({channel}).",
                True,
            )
            continue

        elif endtime is not None and endtime < date_time:
            # End is earlier than the start!
            write_print(
                f"End timestamp earlier than start! Cannot record {date_time} ({channel}).",
                True,
            )

        recordings[pid] = {
            "url": address_split[0],
            "channel": channel,
            "start": date_time,
            "duration": duration,
            "end": endtime,
            "programme": programme,
            "sid": address_split[1],
        }

    return recordings


def reload_schedule(sched_path, existing, running):
    """
    Schedule reload only necessary if schedule
    checks scripts have updated recordings based
    on new duration timings
    """

    now = datetime.datetime.utcnow()
    revised = initialise(sched_path, True)

    # Get the schedule id for each of the running recordings
    running_ids = {}
    for runs in running:
        sid = running[runs]["sid"]
        running_ids[sid] = runs

    # Get the schedule id for each of the upcoming recordings
    upcoming_ids = {}
    for item in existing:
        sid = existing[item]["sid"]
        upcoming_ids[sid] = item

    new_rec = 0

    # Compare the revised schedule against the existing
    for revs in revised:
        data = revised[revs]
        sched_id = data["sid"]
        endtime = data["end"]

        # If this recording is already running
        if sched_id in running_ids:
            handle = running_ids[sched_id]

            # Check if it's the same channel and programme
            chnl = data["channel"] == running[handle]["channel"]
            prog = data["programme"] == running[handle]["programme"]

            # If it's the same channel and programme, check if we need to revise the end time
            if prog and chnl and endtime != running[handle]["end"]:
                time_print("Changed end time for running recording:", True)

                if data["programme"] is not None:
                    indent_print(f"{data}(programme)s ({data}(channel)s)", True)
                else:
                    indent_print(f"{handle}", True)

                indent_print(
                    f"{running[handle]['end'].strftime(FORMAT)} to {endtime.strftime(FORMAT)}",
                    True,
                )

                running[handle]["end"] = endtime

        # Only consider programmes that haven't finished yet
        elif endtime > now:
            if sched_id in upcoming_ids:
                ids = upcoming_ids[sched_id]

                # Remove the old data so that it can be replaced with the new
                temp = existing.pop(ids, None)

                # Check if it's the same channel and programme
                chnl = data["channel"] == temp["channel"]
                prog = data["programme"] == temp["programme"]

                # Only notify a change if it's the same programme
                if temp != data and chnl and (prog or temp["programme"] is None):
                    time_print("Changes made to scheduled recording:", True)

                    if data["programme"] is not None:
                        indent_print("{data}(programme)s ({data}(channel)s)", True)
                    else:
                        indent_print(f"{ids}", True)

            else:
                new_rec += 1

            existing[revs] = data

    if new_rec > 0:
        time_print(f"Added {new_rec} new scheduled recordings.", True)

    return (existing, running)


def main():
    """
    While loop set to active (unless check_control() changes status)
    checks channel's EIT runningStatus and eventId continually for change.
    When change found, stop current recording and initialise new one
    using the UNIX start time and calculated duration from UNIX end time
    - If EIT runningStatus is lost from stream at any point, the script
    moves on to EPG schedule recording until end of schedule is reached
    and script restarts in main and tries EIT data again.
    """

    if len(sys.argv) != 2:
        time_print(
            f"Script exit: sys.argv has not received correct arguments to select channel: {sys.argv}",
            False,
        )
        sys.exit("SCRIPT EXIT: SYSARG HAS NOT RECEIVED CORRECT ARGUMENTS")

    time_print(f"{CHANNEL} script launch - recording start", False)

    # Get channel streams
    rtp = fetch_rtp()
    udp = fetch_udp()
    start_rec, end_rec = channel_timings(CHANNEL)
    active = True
    event_list = []
    eit_fail = 0

    while active:

        # Fetch events from channel's UDP EIT table
        events = get_events(udp)
        if not events:
            time_print(f"Failed to retrieve events - times: {eit_fail}", False)
            if start_rec <= datetime.datetime.now() <= end_rec:
                eit_fail += 1
            # Look for 15 consistent failures
            if eit_fail == 15:
                time_print("EIT access failed 15 consecutive times.", False)
                time_print(
                    "Launching EPG schedule recorder, creating text file notification.",
                    False,
                )
                now = datetime.datetime.utcnow().strftime("%Y/%m/%d")
                now_txt = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H:%M:%S")
                try:
                    with open(
                        os.path.join(
                            STORA_PATH, now, CHANNEL, f"epgrecording_{now_txt}.txt"
                        ),
                        "a+",
                    ) as fp:
                        pass
                except FileNotFoundError:
                    pass
                launch_epg()
                eit_fail = 0
            continue

        # Prevent build up of occasional failures over day
        eit_fail = 0

        # Separate to running(4)/not_running(1)
        running, not_running = read_eit(events)
        # Stop event_list getting big, delete first
        if len(event_list) > 5:
            del event_list[0]

        for key, val in running.items():
            if key not in event_list:
                # Add current eventId to event_list
                event_list.append(key)
                time_print(f"New running EventId: {key}", False)
                time_print(f"Event list updated: {event_list}", False)
                prog_info = val.split(", ")

                # Initialise recording path - needs date paths adding
                outfile = initialise_ts_rs(prog_info[1], key, prog_info[0])

                if len(event_list) > 1:
                    # Stop existing recording
                    time_print("Ending recording for previous programme", False)
                    player.stop()  # Stop playback
                    player.release()  # Close the player
                    inst.release()  # Destroy the instance
                    indent_print(
                        f"STOP Instance: {inst}, Player: {player}, Media: {media}",
                        False,
                    )

                # Start new recording using initialised outfile as destination
                time_print(f"Initialising recording for path: {outfile}", False)
                inst, player, media = record_stream(rtp, outfile)
                player.play()
                indent_print(
                    f"START Instance: {inst}, Player: {player}, Media: {media}", False
                )
                indent_print(f"Started recording: {prog_info[4]} ({CHANNEL})", False)
                indent_print(
                    f"{prog_info[1]} to {prog_info[2]} - duration {prog_info[0]}", False
                )

            else:
                continue

        check = check_control()
        if check is False:
            time_print("Script exit requested by stora_control.json", False)
            time_print("Ending current recording following exit request.", False)
            player.stop()
            player.release()
            inst.release()
            active = False


def launch_epg():
    """
    import main() from epg recording script here
    Calculates time to accommodate pre-midnight launch
    """
    date = time_calc()
    date_path = os.path.join(STORA_PATH, f"{date[0:4]}/{date[5:7]}/{date[8:10]}/")
    chnl_path = os.path.join(date_path, CHANNEL)

    # Get schedule name for day
    schedule = os.path.join(SCHEDULES, f"{CHANNEL}_schedule_{date}.json")
    mod_time = os.path.getmtime(schedule)
    recordings = initialise(schedule)
    handles = {}
    busy = True
    first = True

    while busy:
        # Check for schedule modification change
        new_mod_time = get_mod_time(mod_time, date)
        if new_mod_time:
            # Update modification time and reload_schedule
            mod_time = new_mod_time
            recordings, handles = reload_schedule(schedule, recordings, handles)
            write_print("Schedules reloaded due to modification update", True)

        handles_deleted = recordings_deleted = []
        now = datetime.datetime.utcnow()
        # Check existing recordings
        hs = handles.keys()
        for h in hs:
            data = handles[h]
            end = data["end"]
            channel = data["channel"]
            programme = data["programme"]
            if now > end:
                time_print(f"Finished recording {programme} ({channel}).", True)
                try:
                    data["player"].stop()  # Stop playback
                    data["player"].release()  # Close the player
                    data["inst"].release()  # Destroy the instance
                    handles_deleted.append(h)
                except Exception as err:
                    time_print("Unable to destroy player reference due to error:", True)
                    write_print(str(err), True)

        # Deletion of handles item in dictionary
        if len(handles_deleted) > 0:
            for hd in handles_deleted:
                if hd in handles.keys():
                    print(f"=== HANDLE FOR DELETION {hd}")
                    del handles[hd]

        # Loop through the schedule
        rs = recordings.keys()
        for r in rs:
            data = recordings[r]  # Schedule entry details
            start = data["start"]
            duration = data["duration"]
            end = data["end"]
            channel = data["channel"]
            programme = data["programme"]
            # If we're not recording the stream but we're between the
            # start and end times for the programme, record it

            if r not in handles and (now > start):
                print(f"if {now} < {end}")
                if now < end:
                    # Determine a suitable output filename
                    fn = initialise_ts(chnl_path, start, duration, first)
                    # Create the VLC instance and player
                    inst, player, media = record_stream(data["url"], fn)

                    # Store the handle to the VLC instance and relevant data
                    handles[r] = {
                        "inst": inst,
                        "player": player,
                        "media": media,
                        "end": end,
                        "programme": programme,
                        "channel": channel,
                        "sid": data["sid"],
                    }

                    # Start the stream and hence the recording
                    player.play()
                    time_print("Started recording:", True)
                    indent_print(f"{programme} ({channel})", True)
                    indent_print(
                        f"{start.strftime(FORMAT)} to {end.strftime(FORMAT)}", True
                    )
                    first = False
                else:
                    time_print("Missed scheduled recording:", True)
                    indent_print(f"{programme} ({channel})", True)
                    indent_print(
                        f"{start.strftime(FORMAT)} to {end.strftime(FORMAT)}", True
                    )
                    write_print(f"*** Deleting key: {r}", True)

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
            time_print("Exiting EPG capture for this schedule...\n", True)

        check = check_control()
        if check is False:
            time_print("Script exit requested by stora_control.json", True)
            time_print("Ending current recording following exit request.", True)
            player.stop()
            player.release()
            inst.release()
            sys.exit("stora_control.json requests script exits")


def get_events(udp):
    """
    Dump libdvbtee EIT data to dict
    then pass back to main. Retry if fails.
    """

    cmd = [DVBTEE, "-i", udp, "-t", "6", "-j"]

    try:
        capture = subprocess.check_output(cmd, timeout=15, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        time_print(f"Failed to retrive DVBTEE:\n{exc}")
        return None

    capture = capture.decode("latin1").splitlines()
    data = [x for x in capture if x.startswith("NET_SVC_ID#")]
    if not data:
        time_print(f"Failed to capture data from UDP:\n{capture}", False)
        return None

    try:
        split_d = data[0].split(": [")[1].rstrip("]")
        split_data = split_d.replace(":false,", ":False,")
        split_data_clean = split_data.replace(":true,", ":True,")
        jdata = ast.literal_eval(split_data_clean)
        return jdata
    except IndexError as exc:
        raise Exception from exc
    except SyntaxError as exc:
        raise Exception from exc
    except Exception as exc:
        raise Exception from exc


def read_eit(events):
    """
    Search through event data
    return running/not running
    dictionary of entries
    """
    running = {}
    not_running = {}
    for num in range(0, 2):
        try:
            event_id = events["events"][num]["eventId"]
            print(event_id)
        except (TypeError, IndexError, KeyError):
            event_id = ""
        try:
            title = events["events"][num]["descriptors"][0]["name"]
            title = title.replace("\x86", "")
            title = title.replace("\x87", "")
            title = title.replace("Â", "")
            print(title)
        except (TypeError, IndexError, KeyError):
            title = ""
        try:
            run_stat = events["events"][num]["runningStatus"]
        except (TypeError, IndexError, KeyError):
            run_stat = ""
        try:
            ts_start = events["events"][num]["unixTimeBegin"]
            start = datetime.datetime.utcfromtimestamp(ts_start).strftime(FTIME)
        except (TypeError, IndexError, KeyError):
            ts_start = ""
        try:
            ts_end = events["events"][num]["unixTimeEnd"]
            end = datetime.datetime.utcfromtimestamp(ts_end).strftime(FTIME)
        except (TypeError, IndexError, KeyError):
            ts_end = ""

        if ts_end and ts_start:
            seconds = int(ts_end) - int(ts_start)
            duration = str(time.strftime(FTIME, time.gmtime(seconds)))
        else:
            duration = ""
        if str(run_stat) == "4":
            running[event_id] = f"{duration}, {start}, {end}, {run_stat}, {title}"
        if str(run_stat) == "1":
            not_running[event_id] = f"{duration}, {start}, {end}, {run_stat}, {title}"

    return running, not_running


def initialise_ts(chnl_path, start_time, duration, first):
    """
    Uses programme start time and duration to
    build a new programme folder in chnl_path directory.
    Returns path for new stream.mpeg2.ts file.
    If first is true, checks for existing folder
    and appends stream to end of existing.
    """

    start_str = start_time.strftime(FORMAT)
    start = start_str[11:].replace(":", "-")
    seconds = duration * 60
    dur = time.strftime("%H-%M-%S", time.gmtime(seconds))
    dur = str(dur)

    # Folder creation for new mpeg file
    fname = f"{start}-{CHANNEL}-{dur}"
    if first:
        folder_check = [x for x in os.listdir(chnl_path) if x.startswith(start)]
        if len(folder_check) == 1:
            print(
                f"Folder exists for this time slot {folder_check[0]}, adding data to existing folder"
            )
            return os.path.join(chnl_path, folder_check[0], "stream.mpeg2.ts")
    if not os.path.exists(os.path.join(chnl_path, fname)):
        os.makedirs(os.path.join(chnl_path, fname))
        print(f"Created new directory {fname}")

    return os.path.join(chnl_path, fname, "stream.mpeg2.ts")


def initialise_ts_rs(start_time, event_id, duration):
    """
    Create new folder for programme recording
    from start time, event id and duration
    Handle midnight items writing to previous
    day folder when they launch before midnight
    """

    now_check = str(datetime.datetime.utcnow())
    if " 23:5" in now_check and "00-00-00" in start_time:
        date_dash = str(datetime.datetime.utcnow() + datetime.timedelta(days=1)).split(
            " ", maxsplit=1
        )[0]
        now = date_dash.replace("-", "/")
    else:
        now = datetime.datetime.utcnow().strftime("%Y/%m/%d")

    # Folder creation for new mpeg file
    fname = f"{start_time}-{event_id}-{duration}"
    fpath = os.path.join(STORA_PATH, now, CHANNEL, fname)
    if not os.path.exists(fpath):
        os.makedirs(fpath)
        print(f"Created new directory {fpath}")
    return os.path.join(fpath, "stream.mpeg2.ts")


def record_stream(instream, outfile):
    """
    Record the network stream to the output file.
    Create VLC instance that launches demux dump and
    appends to stream (if already exists) or creates new
    """

    inst = vlc.Instance(
        "-vv", "--demux=dump", f"--demuxdump-file={outfile}", "--demuxdump-append"
    )
    player = inst.media_player_new()
    media = inst.media_new(instream)
    media.get_mrl()
    player.set_media(media)
    return (inst, player, media)


@tenacity.retry(stop=tenacity.stop_after_attempt(5))
def initialise(sched_path, silent=False):
    """
    Load the channel list and scheduled recordings.
    Tenacity to manage moments when schedule absent.
    """

    channels = load_channel_config(silent)  # Get the available channels
    schedule = load_schedule(sched_path, silent)  # Get the schedule
    recordings = parse_schedule(schedule, channels)  # Parse the schedule information

    if recordings:
        return recordings


if __name__ == "__main__":
    main()
