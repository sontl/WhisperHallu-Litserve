#!/bin/bash

# Image Upscale Server Management Script
# Usage: ./start_image_upscale_server.sh {start|stop|restart|status}

SERVICE_NAME="image_upscale_server"
SCRIPT_PATH="image_upscale_server.py"
PID_FILE="/tmp/${SERVICE_NAME}.pid"
LOG_DIR="./logs"
NOHUP_LOG="${LOG_DIR}/nohup.$(date +%Y%m%d).out"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to get process status
get_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "running"
            return 0
        else
            echo "stopped"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo "stopped"
        return 1
    fi
}

# Function to start the service
start_service() {
    STATUS=$(get_status)
    if [ "$STATUS" = "running" ]; then
        PID=$(cat "$PID_FILE")
        echo "Image Upscale Server is already running (PID: $PID)"
        return 0
    fi

    echo "Starting Image Upscale Server..."
    
    # Check if Python script exists
    if [ ! -f "$SCRIPT_PATH" ]; then
        echo "Error: $SCRIPT_PATH not found"
        return 1
    fi

    # Start the service with nohup
    nohup python "$SCRIPT_PATH" >> "$NOHUP_LOG" 2>&1 &
    PID=$!
    
    # Save PID to file
    echo "$PID" > "$PID_FILE"
    
    # Wait a moment and check if process is still running
    sleep 2
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Image Upscale Server started successfully (PID: $PID)"
        echo "Logs: $NOHUP_LOG"
        return 0
    else
        echo "Failed to start Image Upscale Server"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to stop the service
stop_service() {
    STATUS=$(get_status)
    if [ "$STATUS" = "stopped" ]; then
        echo "Image Upscale Server is not running"
        return 0
    fi

    PID=$(cat "$PID_FILE")
    echo "Stopping Image Upscale Server (PID: $PID)..."
    
    # Send TERM signal
    kill "$PID" 2>/dev/null
    
    # Wait for graceful shutdown
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "Image Upscale Server stopped successfully"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done
    
    # Force kill if still running
    echo "Force killing Image Upscale Server..."
    kill -9 "$PID" 2>/dev/null
    rm -f "$PID_FILE"
    echo "Image Upscale Server force stopped"
    return 0
}

# Function to restart the service
restart_service() {
    echo "Restarting Image Upscale Server..."
    stop_service
    sleep 2
    start_service
}

# Function to show status
show_status() {
    STATUS=$(get_status)
    if [ "$STATUS" = "running" ]; then
        PID=$(cat "$PID_FILE")
        echo "Image Upscale Server is running (PID: $PID)"
        
        # Show port information
        echo "Service should be available at: http://localhost:8867"
        
        # Show recent log entries
        if [ -f "$NOHUP_LOG" ]; then
            echo "Recent log entries:"
            tail -5 "$NOHUP_LOG"
        fi
    else
        echo "Image Upscale Server is stopped"
    fi
}

# Main script logic
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
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the Image Upscale Server"
        echo "  stop    - Stop the Image Upscale Server"
        echo "  restart - Restart the Image Upscale Server"
        echo "  status  - Show service status"
        echo ""
        echo "Service runs on port 8867"
        echo "Logs are written to: $NOHUP_LOG"
        exit 1
        ;;
esac

exit $?