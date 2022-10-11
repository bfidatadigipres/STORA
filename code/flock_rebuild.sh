#!/bin/bash

#############################################
# CHECK IF FLOCK FILES EXIST, IF NOT RECREATE
#############################################

LOCKS=( "/var/run/schedule_checks.lock"
        "/var/run/schedule_checks_eit.lock"
        "/var/run/restart_bbcone.lock"
        "/var/run/restart_bbctwo.lock"
        "/var/run/restart_bbcthree.lock"
        "/var/run/restart_bbcfour.lock"
        "/var/run/restart_bbcnews.lock"
        "/var/run/restart_cbbc.lock"
        "/var/run/restart_cbeebies.lock"
        "/var/run/restart_channel4.lock"
        "/var/run/restart_more4.lock"
        "/var/run/restart_film4.lock"
        "/var/run/restart_itv1.lock"
        "/var/run/restart_itv2.lock"
        "/var/run/restart_itv3.lock"
        "/var/run/restart_itv4.lock"
        "/var/run/restart_citv.lock"
        "/var/run/restart_five.lock"
        "/var/run/restart_5star.lock"
)

for lock in "${LOCKS[@]}" ; do
    if [[ -f "$lock" ]];then
        true
    else
        sudo touch "$lock"
    fi
done
