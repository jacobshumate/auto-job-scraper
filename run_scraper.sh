#!/bin/bash

# Define paths
PYTHON_INTERPRETER=/usr/local/bin/python
SCRIPT_PATH=/home/scraperuser/app/main.py
CONFIG_PATH=/home/scraperuser/app/data/config.json
LOG_PATH=/home/scraperuser/app/data/main.log

# Run the Python script and log the output
$PYTHON_INTERPRETER $SCRIPT_PATH $CONFIG_PATH >> $LOG_PATH 2>&1

# Optionally, you can add error handling or notifications here
if [ $? -ne 0 ]; then
  echo "Script failed at $(date)" >> /home/scraperuser/app/data/error.log
fi
