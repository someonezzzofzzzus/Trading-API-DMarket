#!/bin/bash
#Script used to extract log files from /bar/log directory of the server where all output of scripts are registered
#and save it into separate directory in the Project/logs directory seperatly for each day
set -e

date=$(date +%F)

mkdir -p /root/GAFNA/Project/logs/$date
cp /var/log/Gem_targets.log /root/GAFNA/Project/logs/$date/
cp /var/log/Gem_sells.log /root/GAFNA/Project/logs/$date/
cp /var/log/Gem_del_sells.log /root/GAFNA/Project/logs/$date/

truncate -s 0 /var/log/Gem_targets.log /var/log/Gem_sells.log /var/log/Gem_del_sells.log
