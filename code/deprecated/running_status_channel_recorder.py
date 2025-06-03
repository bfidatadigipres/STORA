#!/usr/bin/env python3

"""
A script to capture RTP network streams using VLC
taking prompts from UDP EIT table 'runningStatus' data.
Has to be run in virtual environment to access VLC Python
bindings and Tenacity.

main():
1. Launches recording then monitors EIT 'runningStatus'
   data for change in the '4' running category.
   Uses libdvbtee to grab Network Service ID.
   Loops continually while 'active'. To turn 'active' to False,
   control_json needs changing and script exits.
2. When a change is found in current recording, the script
   stops current VLC media instance, initialises a new
   stream recording in new folder path.
3. Starts the recording again and continues monitoring
   'runningStatus' for another change.

Developed with inspiration from a Py2 script found on code.activestate.com:
https://code.activestate.com/recipes/579096-vlcpy-stream-capture-scheduler-script/

Joanna White
2022
"""

import ast
import itertools
import json
import os
import subprocess
import sys
import time
from datetime import datetime

import vlc
from tenacity import retry

# Global variables
CHANNEL = sys.argv[1]
STORA_PATH = os.environ["STORAGE_PATH"]
CODEPTH = os.environ["CODE"]
CONFIG_FILE = os.path.join(CODEPTH, "stream_config.json")
CONFIG_UDP = os.path.join(CODEPTH, "stream_config_udp.json")
CONTROL = os.path.join(CODEPTH, "stora_control.json")
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


def write_print(text):
    """
    Create new log if need then write
    supplied text to it with newline
    """

    now = datetime.utcnow().strftime("%Y/%m/%d")
    log_path = os.path.join(STORA_PATH, now, CHANNEL)
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    f = open(os.path.join(log_path, "recording.log"), "a")
    f.write(f"{text}\n")
    f.close()


def time_print(text, dt=None):
    """
    Print to STDOUT with a datetime prefix. If no timestamp is provided,
    the current date and time will be used. Captured for stream logs
    """

    if dt is None:
        now = datetime.utcnow()
        dt = now.strftime("%H:%M:%S")

    write_print(f"{dt}  {text}")


def indent_print(text):
    """
    Print to STDOUT with an indent matching the timestamp printout in
    time_Print(). Captured for stream logs
    """

    write_print(f"\t    {text}")


def main():
    """
    While loop set to active (unless check_control() changes status)
    checks channel's EIT runningStatus and eventId continually for change.
    When change found, stop current recording and initialise new one
    using the UNIX start time and calculated duration from UNIX end time
    """

    if len(sys.argv) != 2:
        time_print(
            f"Script exit: sys.argv has not received correct arguments to select channel: {sys.argv}"
        )
        sys.exit("SCRIPT EXIT: SYSARG HAS NOT RECEIVED CORRECT ARGUMENTS")

    time_print(f"{CHANNEL} script launch - recording start")

    # Get channel streams
    rtp = fetch_rtp()
    udp = fetch_udp()
    print(rtp, udp)
    active = True
    event_list = []

    while active:

        # Fetch events from channel's UDP EIT table
        events = get_events(udp)

        # Separate to running(4)/not_running(1)
        running, not_running = read_eit(events)

        # Stop event_list getting big, delete first
        if len(event_list) > 5:
            del event_list[0]

        for key, val in running.items():
            if key not in event_list:
                # Add current eventId to event_list
                event_list.append(key)
                time_print(f"New running EventId: {key}")
                time_print(f"Event list updated: {event_list}")
                prog_info = val.split(", ")

                # Initialise recording path - needs date paths adding
                outfile = initialise_ts(prog_info[1], key, prog_info[0])

                if len(event_list) > 1:
                    # Stop existing recording
                    time_print(f"Ending recording for previous programme")
                    player.stop()  # Stop playback
                    player.release()  # Close the player
                    inst.release()  # Destroy the instance

                # Start new recording using initialised outfile as destination
                time_print(f"Initialising recording for path: {outfile}")
                (inst, player, media) = record_stream(rtp, outfile)
                player.play()
                indent_print(f"Started recording: {prog_info[4]} ({CHANNEL})")
                indent_print(
                    f"{prog_info[1]} to {prog_info[2]} - duration {prog_info[0]}"
                )

            else:
                continue

        check = check_control()
        if check == False:
            time_print("Script exit requested by stora_control.json")
            time_print(f"Ending current recording following exit request.")
            player.stop()
            player.release()
            inst.release()
            active = False


@retry
def get_events(udp):
    """
    Dump libdvbtee EIT data to dict
    then pass back to main. Retry if fails.
    """

    cmd = [DVBTEE, "-i", udp, "-t2", "-j"]

    capture = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    capture = capture.decode("latin1").splitlines()

    data = [x for x in capture if x.startswith("NET_SVC_ID#")]
    if not data:
        raise Exception

    try:
        split_d = data[0].split(": [")[1].rstrip("]")
        split_data = split_d.replace(":false,", ":False,")
        split_data_clean = split_data.replace(":true,", ":True,")
        jdata = ast.literal_eval(split_data_clean)
        return jdata
    except IndexError:
        raise Exception


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
        except (IndexError, KeyError):
            event_id = ""
        try:
            title = events["events"][num]["descriptors"][0]["name"]
            title = title.replace("\x86", "")
            title = title.replace("\x87", "")
            title = title.replace("Â", "")
            print(title)
        except (IndexError, KeyError):
            title = ""
        try:
            length = events["events"][num]["lengthSec"]
        except (IndexError, KeyError):
            length = ""
        try:
            run_stat = events["events"][num]["runningStatus"]
        except (IndexError, KeyError):
            run_stat = ""
        try:
            ts_start = events["events"][num]["unixTimeBegin"]
            start = datetime.utcfromtimestamp(ts_start).strftime(FTIME)
        except (IndexError, KeyError):
            ts_start = ""
        try:
            ts_end = events["events"][num]["unixTimeEnd"]
            end = datetime.utcfromtimestamp(ts_end).strftime(FTIME)
        except (IndexError, KeyError):
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


def initialise_ts(start_time, event_id, duration):
    """
    Create new folder for programme recording
    from start time, event id and duration
    """

    now = datetime.utcnow().strftime("%Y/%m/%d")

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
        "--demux=dump", f"--demuxdump-file={outfile}", "--demuxdump-append"
    )
    player = inst.media_player_new()
    media = inst.media_new(instream)
    media.get_mrl()
    player.set_media(media)
    return (inst, player, media)


if __name__ == "__main__":
    main()
