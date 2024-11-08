#!/bin/bash

# Configuration
APP_NAME="whisperhallu_server.py"
PID_FILE="/tmp/whisperhallu.pid"
LOG_DIR="./logs"
PYTHON_ENV="prodenv/bin/python"

# Load configuration from external file
CONFIG_FILE=".env"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "Error: Configuration file $CONFIG_FILE not found"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p $LOG_DIR

# Function to start the service
start_service() {
    echo "Starting WhisperHallu service..."
    if [ -z "$GLADIA_API_KEY" ]; then
        echo "Error: GLADIA_API_KEY not set in $CONFIG_FILE"
        exit 1
    fi
    # Start the process with environment variable and save PID
    GLADIA_API_KEY=$GLADIA_API_KEY nohup $PYTHON_ENV $APP_NAME >> "$LOG_DIR/nohup.$(date +%Y%m%d).out" 2>&1 & 
    echo $! > $PID_FILE
    echo "Service started with PID $(cat $PID_FILE)"
}

# Function to stop the service
stop_service() {
    if [ -f $PID_FILE ]; then
        echo "Stopping WhisperHallu service..."
        kill $(cat $PID_FILE)
        rm $PID_FILE
        echo "Service stopped"
    else
        echo "PID file not found"
    fi
}

# Function to restart the service
restart_service() {
    stop_service
    sleep 2
    start_service
}

# Handle command line arguments
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac

exit 0 