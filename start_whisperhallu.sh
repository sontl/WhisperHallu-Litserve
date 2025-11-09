#!/bin/bash

# Configuration
APP_NAME="whisperhallu_server.py"
PID_FILE="/tmp/whisperhallu.pid"
LOG_DIR="./logs"
PYTHON_ENV="prodenv/bin/python"

# Function to log messages with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/whisperhallu_service.log"
}

# Create log directory if it doesn't exist
mkdir -p $LOG_DIR

# Load configuration from external file
CONFIG_FILE=".env"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
    log "Configuration loaded from $CONFIG_FILE"
else
    log "Error: Configuration file $CONFIG_FILE not found"
    exit 1
fi

# Function to check if service is running
check_service() {
    if [ -f $PID_FILE ]; then
        PID=$(cat $PID_FILE)
        if ps -p $PID > /dev/null 2>&1; then
            log "Service is running with PID $PID"
            return 0
        else
            log "PID file exists but service is not running"
            rm $PID_FILE
            return 1
        fi
    else
        log "Service is not running"
        return 1
    fi
}

# Function to start the service
start_service() {
    log "Starting WhisperHallu service..."
    
    # Check if service is already running
    if check_service; then
        log "Service is already running"
        return 1
    fi

    # Check for required environment variables
    if [ -z "$GLADIA_API_KEY" ]; then
        log "Error: GLADIA_API_KEY not set in $CONFIG_FILE"
        exit 1
    fi

    # Check if Python environment exists
    if [ ! -f "$PYTHON_ENV" ]; then
        log "Error: Python environment not found at $PYTHON_ENV"
        exit 1
    fi

    # Start the process with environment variable and save PID
    log "Starting service with Python environment: $PYTHON_ENV"
    GLADIA_API_KEY=$GLADIA_API_KEY nohup $PYTHON_ENV $APP_NAME >> "$LOG_DIR/nohup.$(date +%Y%m%d).out" 2>&1 & 
    echo $! > $PID_FILE
    log "Service started with PID $(cat $PID_FILE)"
}

# Function to stop the service
stop_service() {
    if [ -f $PID_FILE ]; then
        log "Stopping WhisperHallu service..."
        PID=$(cat $PID_FILE)
        if kill $PID 2>/dev/null; then
            log "Sent SIGTERM to process $PID"
        else
            log "Failed to stop process $PID"
        fi
        
        # Additional cleanup with pkill
        if pkill -f whisperhallu_server.py; then
            log "Cleaned up any remaining whisperhallu processes"
        fi
        
        rm -f $PID_FILE
        log "Service stopped and PID file removed"
    else
        log "PID file not found, service may not be running"
    fi
}

# Function to restart the service
restart_service() {
    log "Restarting WhisperHallu service..."
    stop_service
    sleep 2
    start_service
}

# Function to show service status
status_service() {
    check_service
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
    status)
        status_service
        ;;
    *)
        log "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

exit 0 