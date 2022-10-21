# STORA: System for Television Off-air Recording Archiving

The scripts in this repository forms the off-air TV recording code base responsible for preserving UK Television channels 24/7 for the BFI National Television Archive. 

## Overview

To follow.

## Dependencies

These scripts are run from Ubuntu 20.04LTS installed server and rely upon various Linux command line programmes. These include: rsync, flock, pgrep, cat, echo, basename, dirname, find, date and possibly more. You can find out more about these by running the manual (man rsync) or by calling the help page (rsync --help).  

Several open source softwares are used. Please follow the links below to make installations:  
FFmpeg Version 4+ - https://ffmpeg.org/  
VLC Version 3+ - https://videolan.org  
MediaInfo V19.09 + - https://mediaarea.net/mediainfo  
Libdvbtee - https://github.com/mkrufky/libdvbtee  
CCExtractor - https://ccextractor.org/public/general/downloads/  

Python packages:  
VLC Python bindings - https://pypi.org/project/python-vlc/ (import vlc)  
Tenacity - https://pypi.org/project/tenacity/ (import tenacity)  
Requests - https://pypi.org/project/requests/ (import requests)  

## Environmental variable storage  

These scripts are being operated using environmental variables that store all path and key data for the script operations. These environmental variables are persistent so can be called indefinitely. A list of environmental variables functions follow at the bottom of this document.  

## Operational environment  

The scripts write data to a date/channel/programme folder structure. These folders are placed in the designated STORAGE_PATH environmental variable, and an example of the layout follows:  

```bash
media/  
└── data/  
    └── 2022/  
        └── 10/  
            ├── 10/  
            │   ├── 5star/  
            │   │   ├── 09-30-00-123-00-30-00/  
            │   │   │   ├── info.csv  
            │   │   │   ├── stream.mpeg2.ts  
            │   │   │   └── subtitles.vtt  
            │   │   ├── 10-00-00-124-00-60-00/  
            │   │   │   ├── info.csv  
            │   │   │   ├── stream.mpeg2.ts  
            │   │   │   └── subtitles.vtt  
            │   │   └── 11-00-00-125-00-45-00/  
            │   │       ├── info.csv  
            │   │       ├── stream.mpeg2.ts  
            │   │       └── subtitles.vtt  
            │   ├── bbcfourhd/  
            │   │   ...  
            │   ├── bbcnewshd/  
            │   │   ...  
            │   ├── bbconehd/  
            │   │   ...  
            │   ├── bbcthree/  
            │   │   ...  
            │   ├── bbctwohd/  
            │   │   ...  
            │   ├── cbbcshd/  
            │   │   ...  
            │   ├── cbeebieshd/  
            │   │   ...  
            │   ├── channel4/  
            │   │   ...  
            │   ├── citv/  
            │   │   ...  
            │   ├── film4/  
            │   │   ...  
            │   ├── five/  
            │   │   ...  
            │   ├── itv1/  
            │   │   ...  
            │   ├── itv2/  
            │   │   ...  
            │   ├── itv3/  
            │   │   ...  
            │   ├── itv4/  
            │   │   ...  
            │   └── more4/  
            │       ...
            ├── 11/  
            │   ...  
            └── 12/  
                ...  
```

## Supporting crontab actions  

The scripts are to be driven from a server /etc/crontab, some launch at specific times of the day, and others continually throughout the day with the use of Flock locks. Locks prevent the scripts from running multiple versions at once and overburdening the server. The crontab calls the scripts via Linux Flock lock files (called from /usr/bin/flock shown below). These are manually created in the /var/run folder and should be created by the username listed in the crontab. It is common for the lock files to disappear when a server is rebooted, etc so the flock_rebuild script manages the recreation of Flock files if missing.  

Crontab entries for recordings scripts and supporting STORA scripts:  

### STORA RECORDING SCHEDULED AT MIDNIGHT EACH NIGHT  
    58    23    *    *    *       username      ${PYENV}  ${CODE}epg_channel_recorder.py 'channel4' >> ${STORAGE_PATH}$(date --date='tomorrow' +\%Y/\%m/\%d)/channel4/recording.log 2>&1  
    58    23    *    *    *       username      ${PYENV}  ${CODE}epg_channel_recorder.py 'film4' >> ${STORAGE_PATH}$(date --date='tomorrow' +\%Y/\%m/\%d)/film4/recording.log 2>&1  
    58    23    *    *    *       username      ${PYENV}  ${CODE}epg_channel_recorder.py 'more4' >> ${STORAGE_PATH}$(date --date='tomorrow' +\%Y/\%m/\%d)/more4/recording.log 2>&1  

### STORA RESTART CHECKS, EVERY MINUTE AND RESTART IF SCRIPT NOT RUNNING  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcone.lock  ${CODE}restart_rs/script_restart_bbcone.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbctwo.lock  ${CODE}restart_rs/script_restart_bbctwo.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcthree.lock  ${CODE}restart_rs/script_restart_bbcthree.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcfour.lock  ${CODE}restart_rs/script_restart_bbcfour.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcnews.lock  ${CODE}restart_rs/script_restart_bbcnews.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_cbbc.lock  ${CODE}restart_rs/script_restart_cbbc.sh
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_cbeebies.lock  ${CODE}restart_rs/script_restart_cbeebies.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_channel4.lock  ${CODE}restart_epg/script_restart_channel4.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_film4.lock  ${CODE}restart_epg/script_restart_film4.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_more4.lock  ${CODE}restart_epg/script_restart_more4.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv1.lock  ${CODE}restart_rs/script_restart_itv1.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv2.lock  ${CODE}restart_rs/script_restart_itv2.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv3.lock  ${CODE}restart_rs/script_restart_itv3.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv4.lock  ${CODE}restart_rs/script_restart_itv4.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_citv.lock  ${CODE}restart_rs/script_restart_citv.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_five.lock  ${CODE}restart_rs/script_restart_five.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_5star.lock  ${CODE}restart_rs/script_restart_5star.sh 

### STORA SUPPORTING SCRIPTS  
    */1   *     *    *    *       username      ${CODE}flock_rebuild.sh  
    

## THE SCRIPTS  

To follow.  
