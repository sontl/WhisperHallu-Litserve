#!/bin/bash

# Configuration
APP_NAME="video_scene_composer_server.py"
PID_FILE="/tmp/video_composer.pid"
LOG_DIR="./logs"
PYTHON_ENV="prodenv/bin/python"
APP_DIR="/home/son/Production/litserve"

# Create log directory if it doesn't exist
mkdir -p $LOG_DIR

# Function to install dependencies
install_dependencies() {
    echo "Installing required dependencies..."
    
    # Verify Python environment exists
    if [ ! -f "$PYTHON_ENV" ]; then
        echo "ERROR: Python environment not found at $PYTHON_ENV"
        echo "Please check your Python environment path"
        exit 1
    fi
    
    # Uninstall existing moviepy first
    echo "Uninstalling existing MoviePy..."
    $PYTHON_ENV -m pip uninstall -y moviepy
    
    # Install specific version of moviepy with pip
    echo "Installing MoviePy version 1.0.3..."
    $PYTHON_ENV -m pip install moviepy==1.0.3
    
    # Check if moviepy is installed by running a simple import test
    if $PYTHON_ENV -c "import moviepy.editor" 2>/dev/null; then
        echo "MoviePy 1.0.3 is installed successfully"
    else
        echo "WARNING: Failed to verify moviepy in virtual environment. Trying with system pip..."
        pip uninstall -y moviepy
        pip install moviepy==1.0.3
        
        if $PYTHON_ENV -c "import moviepy.editor" 2>/dev/null; then
            echo "MoviePy 1.0.3 is installed successfully via system pip"
        else
            echo "ERROR: Still unable to install moviepy. Please check your Python environment."
            exit 1
        fi
    fi
    
    echo "Dependencies installed successfully"
}

# Function to start the service
start_service() {
    echo "Starting Video Scene Composer service..."
    
    # Change to the application directory
    cd $APP_DIR
    
    # Start the process and save PID
    nohup $PYTHON_ENV $APP_NAME >> "$LOG_DIR/nohup.$(date +%Y%m%d).out" 2>&1 & 
    echo $! > $PID_FILE
    echo "Service started with PID $(cat $PID_FILE)"
    echo "Check logs at $LOG_DIR/nohup.$(date +%Y%m%d).out"
}

# Function to stop the service
stop_service() {
    if [ -f $PID_FILE ]; then
        echo "Stopping Video Scene Composer service..."
        kill $(cat $PID_FILE)
        pkill -f video_scene_composer_server.py
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
    install_dependencies
    start_service
}

# Handle command line arguments
case "$1" in
    start)
        install_dependencies
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    install)
        install_dependencies
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|install}"
        exit 1
        ;;
esac

exit 0 