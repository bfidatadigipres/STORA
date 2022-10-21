## STORA: System for Television Off-air Recording and Archiving

The scripts in this repository form the off-air TV recording codebase responsible for preserving 17 UK Television channels 24 hours a day, 7 day a week. The BFI is the body designated by Ofcom (UK communications regulator) as the National Television Archive, under the provision in the Broadcasting Act, 1990. This designation allows us to record, preserve and make accessible TV off-air under section 75 (recordings for archival purposes) of the Copyright, Designs and Patents Act, 1988 and later the Copyright and Rights in Performance Regulations 2014 (under Research, Education, Libraries and Archives).


### Overview

These scripts manage the recording of live television, accessing FreeSat streams using RTP streams for the recordings and UDP streams to access DVB Event Information Tables (EIT). The streams have variable EIT data so two different methods are used to record the off-air content on this basis.  

The first uses Electronic Programme Guide (EPG) data downloaded daily from PATV Metadata Services Ltd. From this a recording schedule is generated for each channel, the script loops over this schedule starting/stopping until no more remain. Should programme's duration extend, such as for live events, scripts update new schedule timings and the recording script sees this modification time change and refreshes the recording script which alters the stop/start times accordingly.  This script runs to close of the schedule, then is restarted from crontab the following day.  

The second script uses the channel's UDP EIT data to download the now/next programme's EventID, and the running status number for each (4 is running now, 1 is not running). When an EventID changes and that programme has a running status 4 then the script stops the existing recording and starts the next. The EIT data also supplies remaining start time and duration information to assist with creating the correct folder path for the recording to be placed in. This script runs on an infite loop that can be stopped using a control.json document.  

There are several other supporting scripts that allow for these recordings to occur, full details of each follow.  


### Dependencies

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


### Environmental variable storage  

These scripts are being operated using environmental variables that store all path and key data for the script operations. These environmental variables are persistent so can be called indefinitely. A list of environmental variables functions follow at the bottom of this document.  

### Operational environment  

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


### Supporting crontab actions  

The scripts are to be driven from a server /etc/crontab, some launch at specific times of the day, and others continually throughout the day with the use of Flock locks. Locks prevent the scripts from running multiple versions at once and overburdening the server. The crontab calls the scripts via Linux Flock lock files (called from /usr/bin/flock shown below). These are manually created in the /var/run folder and should be created by the username listed in the crontab. It is common for the lock files to disappear when a server is rebooted, etc so the flock_rebuild script manages the recreation of Flock files if missing. Crontab entries for recordings scripts and supporting STORA scripts:  

##### STORA RECORDING SCHEDULED AT MIDNIGHT EACH NIGHT  
    58    23    *    *    *       username      ${PYENV}  ${CODE}epg_channel_recorder.py 'channel4' >> ${STORAGE_PATH}$(date --date='tomorrow' +\%Y/\%m/\%d)/channel4/recording.log 2>&1  
    58    23    *    *    *       username      ${PYENV}  ${CODE}epg_channel_recorder.py 'film4' >> ${STORAGE_PATH}$(date --date='tomorrow' +\%Y/\%m/\%d)/film4/recording.log 2>&1  
    58    23    *    *    *       username      ${PYENV}  ${CODE}epg_channel_recorder.py 'more4' >> ${STORAGE_PATH}$(date --date='tomorrow' +\%Y/\%m/\%d)/more4/recording.log 2>&1  

##### STORA RESTART CHECKS, EVERY MINUTE AND RESTART IF SCRIPT NOT RUNNING  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcone.lock  ${CODE}restart_rs/script_restart_bbcone.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbctwo.lock  ${CODE}restart_rs/script_restart_bbctwo.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcthree.lock  ${CODE}restart_rs/script_restart_bbcthree.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcfour.lock  ${CODE}restart_rs/script_restart_bbcfour.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcnews.lock  ${CODE}restart_rs/script_restart_bbcnews.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_cbbc.lock  ${CODE}restart_rs/script_restart_cbbc.sh
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_cbeebies.lock  ${CODE}restart_rs/script_restart_cbeebies.sh  
    *  0-23     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_channel4.lock  ${CODE}restart_epg/script_restart_channel4.sh  
    *  0-23     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_film4.lock  ${CODE}restart_epg/script_restart_film4.sh  
    *  0-23     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_more4.lock  ${CODE}restart_epg/script_restart_more4.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv1.lock  ${CODE}restart_rs/script_restart_itv1.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv2.lock  ${CODE}restart_rs/script_restart_itv2.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv3.lock  ${CODE}restart_rs/script_restart_itv3.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv4.lock  ${CODE}restart_rs/script_restart_itv4.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_citv.lock  ${CODE}restart_rs/script_restart_citv.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_five.lock  ${CODE}restart_rs/script_restart_five.sh  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_5star.lock  ${CODE}restart_rs/script_restart_5star.sh 

##### STORA SUPPORTING SCRIPTS  
    */1   *     *    *    *       username      ${CODE}flock_rebuild.sh  
    

### THE SCRIPTS  

To follow.  
