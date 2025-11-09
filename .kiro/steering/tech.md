# Technology Stack

## Core Framework
- **LitServe**: Primary API framework for all services (extends FastAPI with GPU autoscaling)
- **FastAPI**: Underlying web framework for HTTP endpoints
- **Python 3.8+**: Runtime environment

## AI/ML Libraries
- **FasterWhisper 0.2.0**: Optimized Whisper implementation for speech recognition
- **PyTorch 1.13.1+**: Deep learning framework
- **TorchAudio 0.13.1+**: Audio processing

## Media Processing
- **FFmpeg**: Video/audio processing (system dependency)
- **MoviePy 1.0.3**: Python video editing
- **OpenCV 4.8.0+**: Computer vision and image processing
- **Pydub**: Audio manipulation
- **Video2X**: AI video upscaling (Docker-based)

## Infrastructure
- **Docker**: Containerization for Video2X service with GPU support
- **NVIDIA Container Toolkit**: GPU acceleration in containers
- **systemd**: Service management in production
- **nohup**: Process management for development

## Development Tools
- **unittest**: Testing framework
- **requests**: HTTP client library
- **python-multipart**: File upload handling

## Common Commands

### Service Management
```bash
# Start services
./start_whisperhallu.sh start
./start_video_composer.sh start  
./start_video2x_server.sh start
./start_webmconvert.sh start

# Stop services
./start_whisperhallu.sh stop
./start_video_composer.sh stop
./start_video2x_server.sh stop
./start_webmconvert.sh stop

# Restart services
./start_whisperhallu.sh restart
./start_video_composer.sh restart
./start_video2x_server.sh restart
./start_webmconvert.sh restart

# Check status
./start_whisperhallu.sh status
```

### Testing
```bash
# Run unit tests
python -m unittest json_util_test.py
python -m unittest test_video_audio_merge_server.py

# Test API endpoints
curl -X POST http://127.0.0.1:8000/predict -F "audio_file=@audio.wav"
curl -X POST http://localhost:8890/predict -H "Content-Type: application/json" -d '{...}'
curl -X POST http://localhost:8882/predict -F "video=@video.webm" -o output.mp4
```

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Install system dependencies
sudo apt install ffmpeg

# Set up environment
chmod 600 .env
source .env

# Set up Python virtual environment
python -m venv prodenv
source prodenv/bin/activate
```

### Log Management
```bash
# View logs
cat logs/whisperhallu_YYYYMMDD.log
cat logs/video_scene_composer_YYYYMMDD.log
cat logs/nohup.YYYYMMDD.out

# Clean old logs (crontab)
0 0 * * * /usr/bin/find /path/to/logs -type f -mtime +7 -delete
```