## STORA: System for Television Off-air Recording and Archiving

The scripts in this repository form the off-air TV recording codebase responsible for recording and preserving 18 UK Television channels 24 hours a day, 7 day a week. The BFI National Archive is the body designated by Ofcom (UK communications regulator) as the National Television Archive, under the provision in the Broadcasting Act, 1990, and in that capacity we have provision to record, preserve and make accessible off-air television.


### Overview

These scripts manage the recording of live television, accessing FreeSat using Real-time Transport Protocol (RTP) for the recordings and User Datagram Protocol (UDP) to access Digital Video Broadcasting (DVB) Service Information Event Information Table (EIT). The streams have variable EIT data so two different approaches to recording the off-air content is required.  

Both of these methods are now included in a single off-air recording script called 'epg_assessment_channel_record.py'. The two approaches are outlined below:  
- Electronic Programme Guide (EPG) data downloaded daily from PATV Metadata Services Ltd. From this a recording schedule is generated for each channel, the script loops over this schedule starting/stopping until no more remain. Should programme's duration extend, such as for live events, scripts update new schedule timings and the recording script sees this modification time change and refreshes the recording script which alters the stop/start times accordingly.  This EPG schedule recording runs until all items on the schedule have completed and only launches where the RunningStatus data cannot be found in the UDP stream.  
- UDP EIT data is used to download the current airing programme's EventID, and the RunningStatus number (4 is running, 1 is not running). When an EventID changes and that programme has a RunningStatus '4' then the script stops the existing recording and starts the next. The EIT data also supplies start time and duration information to assist with creating the correct folder path for the recording to be placed in. This approach runs on an infite loop that can be stopped using a control.json document, or it switches to the previous EPG schedule recording method if the UDP stream data fails.  

The script checks the channel_timings.json document to see when a script's EIT data should be checked. This document ensures that false EIT failures are not found when a channel is not broadcasting. The script defaults to first attempting to find UDP EIT data, launching the EPG schedule method only after fifteen consective failures to reach the EIT data.  


### Dependencies

These scripts are run from Ubuntu 20.04LTS server and rely upon various Linux command line programmes. These include: rsync, flock, pgrep, cat, echo, basename, dirname, find, date... You can find out more about these programmes by launching the manual (man rsync) or by calling the help page (rsync --help).  

Several open source softwares and Python packages are used, in addition to Python standard library. Please follow the links below for installation guidance:  
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

These scripts are being operated using environmental variables that store all path and key data for the script operations. These environmental variables are persistent so can be called indefinitely. They are imported to Python scripts near the beginning using ```os.environ['VARIABLE']```, and are called in shell scripts like ```"${VARIABLE}" "$VARIABLE"```. They are saved to the /etc/environment file.  


### Operational environment  

The scripts write data to a date/channel/programme folder structure. These folders are placed in the designated STORAGE_PATH environmental variable, and an example of the layout follows:  

```bash
media/  
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

The scripts are launched from /etc/crontab. The restart scripts launch each minute to check if a script is running. If not it will restart it with the use of Flock locks. Locks prevent the scripts from running multiple versions at once and overburdening the server. The crontab calls the scripts via Linux Flock lock files (called from /usr/bin/flock shown below). These are manually created in the /var/run folder and should be created by the username listed in the crontab. It is common for the lock files to disappear when a server is rebooted, etc so the flock_rebuild script manages the recreation of Flock files if missing. Crontab entries for recordings scripts and supporting STORA scripts:  

##### STORA RESTART CHECKS, EVERY MINUTE AND RESTART IF SCRIPT NOT RUNNING  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcone.lock  ${CODE}restart/script_restart.sh 'bbconehd'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbctwo.lock  ${CODE}restart/script_restart.sh 'bbctwohd'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcthree.lock  ${CODE}restart/script_restart.sh 'bbcthree'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcfour.lock  ${CODE}restart/script_restart.sh 'bbcfourhd'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_bbcnews.lock  ${CODE}restart/script_restart.sh 'bbcnewshd'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_cbbc.lock  ${CODE}restart/script_restart.sh 'cbbchd'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_cbeebies.lock  ${CODE}restart/script_restart.sh 'cbeebieshd'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_channel4.lock  ${CODE}restart/script_restart.sh 'channel4'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_film4.lock  ${CODE}restart/script_restart.sh 'film4'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_more4.lock  ${CODE}restart/script_restart.sh 'more4'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv1.lock  ${CODE}restart/script_restart.sh 'itv1'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv2.lock  ${CODE}restart/script_restart.sh 'itv2'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv3.lock  ${CODE}restart/script_restart.sh 'itv3'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_itv4.lock  ${CODE}restart/script_restart.sh 'itv4'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_citv.lock  ${CODE}restart/script_restart.sh 'citv'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_five.lock  ${CODE}restart/script_restart.sh 'five'  
    *     *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/restart_5star.lock  ${CODE}restart/script_restart.sh '5star'  

##### STORA SUPPORTING SCRIPTS  

    2     *     *    *    *       username      ${PYENV}  ${CODE}fetch_stora_schedule.py > /tmp/python_cron1.log 2>&1
    */10  *     *    *    *       username      ${PYENV}  ${CODE}make_subtitles.py > /tmp/python_cron2.log 2>&1
    */10  *     *    *    *       username      ${PYENV}  ${CODE}get_stream_info.py > /tmp/python_cron3.log 2>&1
    */5   *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/schedule_checks.lock  ${PYENV} ${CODE}stream_schedule_checks.py > /tmp/python_cron4.log 2>&1
    */3   *     *    *    *       username      /usr/bin/flock -w 0 --verbose /var/run/schedule_checks_eit.lock  ${PYENV} ${CODE}stream_schedule_checks_eit.py > /tmp/python_cron4b.log 2>&1
    50    1     *    *    *       username      ${PYENV}  ${CODE}make_info_from_schedule.py > /tmp/python_cron5.log 2>&1
    30    2     *    *    *       username      ${PYENV}  ${CODE}stora_channel_move_qnap04.py > /tmp/python_cron6.log 2>&1
    */1   *     *    *    *       username      ${CODE}flock_rebuild.sh  
    

### THE CODEBASE  

To find out more about each script then please read the block comments at the beginning, and any comments that may appear in the code that explains a function or action. The codebase can be broken into four groups with specific functions:  

#### Schedule management  
These scripts control the creation of the EPG schedules, and also manage updating them when stream durations differ from the EPG echedule.  

fetch_stora_schedule.py - https://github.com/bfidatadigipres/STORA/blob/main/code/fetch_stora_schedule.py  
stream_schedule_checks.py - https://github.com/bfidatadigipres/STORA/blob/main/code/stream_schedule_checks.py  
stream_schedule_checks_eit.py - https://github.com/bfidatadigipres/STORA/blob/main/code/stream_schedule_checks_eit.py  

#### Stream recording  
These scripts facilitate recording of the RTP stream for each channel. They cut up the schedule into programmes and store them into the correct date and channel paths. Folders of shell scripts manage the restarting of any channel scripts that stop running for any specific reasons.  

epg_assessment_channel_record.py - https://github.com/bfidatadigipres/STORA/blob/main/code/epg_assessment_channel_recorder.py  
Script restart shell script supplied with channel argument - https://github.com/bfidatadigipres/STORA/blob/main/code/restart/  

Now deprecated:  
running_status_channel_recorder.py - https://github.com/bfidatadigipres/STORA/blob/main/code/running_status_channel_recorder.py  
Running Status script restart shell scripts - https://github.com/bfidatadigipres/STORA/blob/main/code/restart_rs/  
epg_channel_recorder.py - https://github.com/bfidatadigipres/STORA/blob/main/code/epg_channel_recorder.py  
EPG script restart shell scripts - https://github.com/bfidatadigipres/STORA/blob/main/code/restart_epg/  

#### Ingest preparation  
These scripts prepare the programmes for ingest to BFI National archive Digital Preservation Infrastructure by creating necessary files 'info.csv' and 'subtitles.vtt', and also by moving each day's programmes to designated NAS storage from where they are ingested.  

get_stream_info.py - https://github.com/bfidatadigipres/STORA/blob/main/code/get_stream_info.py  
make_subtitles.py - https://github.com/bfidatadigipres/STORA/blob/main/code/make_subtitles.py  
make_info_from_schedule.py - https://github.com/bfidatadigipres/STORA/blob/main/code/make_info_from_schedule.py  
stora_channel_move.py - https://github.com/bfidatadigipres/STORA/blob/main/code/stora_channel_move_qnap04.py  

#### Supporting documents
There are three supporting JSON documents required by the scripts to access the stream data, and to check if there is any requirement for actions to cease. The stream_config files will likely be combined at the next code refactoring.  

channel_timings.json - https://github.com/bfidatadigipres/STORA/blob/main/code/channel_timings.json  
stora_control.json - https://github.com/bfidatadigipres/STORA/blob/main/code/stora_control.json  
stream_config.json - https://github.com/bfidatadigipres/STORA/blob/main/code/stream_config.json  
stream_config_udp.json - https://github.com/bfidatadigipres/STORA/blob/main/code/stream_config_udp.json  


Thank you! Any comments, questions or feedback happily received.
