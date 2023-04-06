#!/bin/bash -x

# Receive channel name from crontab launch and populate $CHANNEL
# Look for pid number of script, if running exit, if not, relaunch.

DATE=$(date +%Y/%m/%d)
CHANNEL="$1"

if pgrep -f "epg_assessment_channel_recorder.py ${CHANNEL}";
  then
    echo "SCRIPT IS ALREADY RUNNING. Exiting."
    exit 0
  else
    echo "** SCRIPT NOT RUNNING. LAUNCHING NOW"
    DATETIME=$(date +%Y-%m-%d_%H:%M:%S)
    touch "${STORAGE_PATH}${DATE}/${CHANNEL}/restart_${DATETIME}.txt"
    "${PYENV}" "${CODE}epg_assessment_channel_recorder.py" "$CHANNEL" >> "${STORA_FOLDERS}logs/${CHANNEL}_vlc_recording.log" 2>&1
fi
