#!/usr/bin/env python3

'''
Targeting yesterday's REDUX folders in channels only
Copying each data to designated STORA folder for ingest
to CID DPI.

Script functions:
1. Iterate through channels and complete following tasks:
   i/ ensure channel paths exists (where Redux may have failed)
   ii/ within channel path build list of programme channels and
       create effective rsync paths by trimming training '/'
   iii/ Check if destination path exists with date/channel requirements
   iv/ rsync (with deletion of source) to destination named as source


Joanna White
2022
'''

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import subprocess

# Global paths
RDX_PATH = os.environ['REDUX_PATH']
CODEPTH = os.environ['CODE']
STORA_PTH = os.environ['STORA_PATH']
LOG_FILE = os.path.join(CODEPTH, 'logs/redux_channel_move.log')
CONFIG_FILE = os.path.join(CODEPTH, 'stream_config.json')
STORA_CONTROL = os.path.join(CODEPTH, 'stora_control.json')
RSYNC_LOG = os.environ['RSYNC_LOGS']

# Date variables
TODAY = datetime.now()
YEST = TODAY - timedelta(1)
YESTERDAY = int(YEST.strftime('%d'))
DATE_PATH = os.path.join(RDX_PATH, f"{str(YEST)[:4]}/{str(YEST)[5:7]}/{str(YEST)[8:10]}/")
STORA = os.path.join(STORA_PTH, f"{str(YEST)[:4]}/{str(YEST)[5:7]}/{str(YEST)[8:10]}/")
# DATE_PATH = os.path.join(RDX_PATH, "2022/07/21/")
# STORA = os.path.join(STORA_PTH, "2022/07/21/")

# Setup logging
logging.basicConfig(filename=LOG_FILE, filemode='a', \
                    format='%(asctime)s\t%(levelname)s\t%(message)s', level=logging.INFO)
CHANNELS = [
    '5star',
    'bbcfourhd',
    'bbcnewshd',
    'bbconehd',
    'bbctwohd',
    'bbcthree',
    'five',
    'itv1',
    'itv2',
    'itv3',
    'itv4',
#    'channel4', # No Redux
#    'more4', # No Redux
    'cbbchd',
    'cbeebieshd',
    'citv',
    'film4'
]

def check_control():
    '''
    Check control JSON for downtime request
    '''
    with open(STORA_CONTROL) as control:
        j = json.load(control)
        if not j['stora_qnap04']:
            logging.info("Script run prevented by stora_control.json. Script exiting.")
            sys.exit("Script run prevented by stora_control.json. Script exiting.")


def main():
    '''
    Iterate list of CHANNEL folders for yesterday
    Copy to STORA/YYYY/MM/DD path with delete of original
    '''
    check_control()
    for chnl in CHANNELS:
        fpath = os.path.join(DATE_PATH, chnl)
        if not os.path.exists(fpath):
            logging.info("Skipping: Path missing from Redux: %s", fpath)
            continue

        folders = [d for d in os.listdir(fpath) if os.path.isdir(os.path.join(fpath, d))]
        logging.info("START MOVE_CONTENT.PY =============== %s", fpath)

        for folder in folders:
            folderpath = os.path.join(fpath, folder)
            logging.info("Targeting folder path: %s", folderpath)
            if not os.path.exists(STORA):
                os.makedirs(STORA, exist_ok=True)
                logging.info("Creating new folder paths in STORA QNAP: %s", STORA)

            fpath1 = folderpath.rstrip('/')
            fpath2 = os.path.join(STORA, chnl)
            fpath2 = fpath2.rstrip('/')

            logging.info("Okay to copy to STORA QNAP and delete successful copies")
            logging.info("Copying %s to %s", fpath1, fpath2)
            rsync(fpath1, fpath2, chnl)

    logging.info("END MOVE_CONTENT.PY ============================================")


def rsync(fpath1, fpath2, chnl):
    '''
    Move Folders using rsync
    With archive and additional checksum
    Output moves to logs and remove source
    files from Redux path
    '''

    folder = os.path.split(fpath1)[1]
    log_path = os.path.join(RSYNC_LOG, f"{str(YEST)[:4]}/{str(YEST)[5:7]}/{str(YEST)[8:10]}/", chnl)
    if not os.path.exists(log_path):
        os.makedirs(log_path, exist_ok=True)
    new_log = Path(os.path.join(log_path, f"{folder}_move.log"))
    new_log.touch(exist_ok=True)

    rsync_cmd = [
        'rsync', '--remove-source-files', '-acrvvh',
        '--info=FLIST2,COPY2,PROGRESS2,NAME2,BACKUP2,STATS2',
        '--perms', '--chmod=a+rwx',
        '--no-owner', '--no-group', '--ignore-existing',
        fpath1, fpath2,
        f'--log-file={new_log}'
    ]

    try:
        logging.info("rsync(): Beginning rsync move")
        subprocess.call(rsync_cmd)
    except Exception as err:
        logging.error("rsync(): Move command failure! %s", err, exc_info=True)


if __name__ == "__main__":
    main()
