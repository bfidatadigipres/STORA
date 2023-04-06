#!/bin/bash -x

# Look for pid number of script, if running exit, if not, relaunch.

DATE=$(date +%Y/%m/%d)

if pgrep -f 'running_status_channel_recorder.py film4';
  then
    echo "SCRIPT IS ALREADY RUNNING. Exiting."
    exit 1
  else
    echo "** SCRIPT NOT RUNNING. LAUNCHING NOW"
    DATETIME=$(date +%Y-%m-%d_%H:%M:%S)
    touch "${STORAGE_PATH}${DATE}/film4/restart_${DATETIME}.txt"
    "${CODE}ENV/bin/python3" "${CODE}running_status_channel_recorder.py" "film4" >> "${CODE}logs/film4_vlc_recording.log" 2>&1
fi
