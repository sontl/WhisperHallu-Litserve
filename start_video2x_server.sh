#!/bin/bash

# Configuration
APP_NAME="video2x_server.py"
PID_FILE="/tmp/video2x.pid"
LOG_DIR="./logs"
PYTHON_ENV="prodenv/bin/python"

# Create log directory if it doesn't exist
mkdir -p $LOG_DIR

# Function to start the service
start_service() {
    echo "Starting video2x service..."
    # Start the process and save PID
    nohup $PYTHON_ENV $APP_NAME >> "$LOG_DIR/video2x.$(date +%Y%m%d).out" 2>&1 & 
    echo $! > $PID_FILE
    echo "Service started with PID $(cat $PID_FILE)"
}

# Function to stop the service
stop_service() {
    if [ -f $PID_FILE ]; then
        echo "Stopping video2x service..."
        kill $(cat $PID_FILE)
        pkill -f video2x_server.py
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