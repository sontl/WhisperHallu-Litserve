#!/bin/bash

# Configuration
APP_NAME="video2x_server.py"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="$SCRIPT_DIR/$APP_NAME"
PID_FILE="/tmp/video2x.pid"
LOG_DIR="${VIDEO2X_LOG_DIR:-$SCRIPT_DIR/logs}"
PYTHON_ENV="${VIDEO2X_PYTHON_ENV:-$SCRIPT_DIR/prodenv/bin/python}"

export VIDEO2X_LOG_DIR="$LOG_DIR"

if [ ! -x "$PYTHON_ENV" ]; then
    echo "Python interpreter not found at $PYTHON_ENV" >&2
    exit 1
fi

if [ ! -f "$APP_PATH" ]; then
    echo "Application file not found: $APP_PATH" >&2
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to start the service
start_service() {
    echo "Starting video2x service..."
    # Start the process and save PID
    nohup "$PYTHON_ENV" "$APP_PATH" >> "$LOG_DIR/video2x.$(date +%Y%m%d).out" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Service started with PID $(cat "$PID_FILE")"
}

# Function to stop the service
stop_service() {
    if [ -f "$PID_FILE" ]; then
        echo "Stopping video2x service..."
        kill "$(cat "$PID_FILE")"
        pkill -f "$APP_PATH"
        rm "$PID_FILE"
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