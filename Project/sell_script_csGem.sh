#!/bin/bash
#Bash script that updates Reduced Fees data, executes script to update inventory items and lastly run script
#responsible for gathering data for creation of sell offers and posts those requests
set -e

/usr/bin/python3 /root/GAFNA/Project/Fees_Script.py

set -e

/usr/bin/python3 /root/GAFNA/Project/scripts/6_history_records.py

sleep 2

/usr/bin/python3 /root/GAFNA/Project/sell_script.py
