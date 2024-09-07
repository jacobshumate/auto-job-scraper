#!/bin/bash

# Define paths
PYTHON_INTERPRETER=/usr/local/bin/python
SCRIPT_PATH=/home/scraperuser/app/main.py
CONFIG_PATH=/home/scraperuser/app/data/config.json
RESET_VPN=-reset_vpn
LOG_PATH=/home/scraperuser/app/data/log/main.log
ERROR_LOG_PATH=/home/scraperuser/app/data/log/error.log

# Run the Python script and log the output
$PYTHON_INTERPRETER $SCRIPT_PATH $CONFIG_PATH $RESET_VPN >> $LOG_PATH 2>&1

# Optionally, you can add error handling or notifications here
if [ $? -ne 0 ]; then
  echo "Script failed at $(date)" >> $ERROR_LOG_PATH
fi
