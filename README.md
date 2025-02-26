# FasterWhisperHallu with LitServe

## What is this project?

This project is an API server that uses **FasterWhisper**, a faster implementation of OpenAI's **Whisper** model for speech recognition and transcription. It leverages **LitServe** to provide a lightweight, scalable web interface where users can upload audio files and receive transcriptions in return.

## Why use this project?

- **Efficiency**: FasterWhisper offers a more optimized performance compared to the original Whisper model, making it ideal for real-time transcription tasks.
- **Scalability**: LitServe extends FastAPI with GPU autoscaling and other features, making this server capable of handling large workloads efficiently.
- **Simplicity**: The project provides an easy-to-deploy API that can be used in both research and production environments.

## How to set it up?

### 1. Clone the repository

First, clone the repository or download the project files.

```bash
git clone <your-repo-url>
cd <your-repo-directory>
```

### 2. Install Dependencies

#### Make sure you have Python 3.8+ installed. Install the necessary dependencies using the provided `requirements.txt` file.

```bash
pip install -r requirements.txt
```

#### You also need to have *FFmpeg* installed on your system. You can install it via your package manager:

```bash
sudo apt install ffmpeg
```

#### Set up environment variables

You can set up the environment variables in the .env file. Set the permissions so only the owner can read/write the file:

```bash
chmod 600 .env
```

### 3. Set up systemd services

Create systemd service files for the various servers:

```bash
sudo nano /etc/systemd/system/whisperhallu-server.service
sudo nano /etc/systemd/system/demucs-server.service
sudo nano /etc/systemd/system/video-composer-server.service
```

Add the appropriate content to each file (refer to the service file content provided earlier).

### 4. Start the services

After creating the service files, reload the systemd manager and start the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable whisperhallu-server.service demucs-server.service video-composer-server.service
sudo systemctl start whisperhallu-server.service demucs-server.service video-composer-server.service
```

### 5. Managing the services

Run with nohup

```bash
nohup python whisperhallu_server.py &
nohup python demucs_server.py &
nohup python video_scene_composer_server.py &
```

Or use the start scripts:

```bash
chmod +x start_whisperhallu.sh
chmod +x start_video_composer.sh
```

```bash
./start_whisperhallu.sh start
./start_video_composer.sh start
```

To check the status of the services:

```bash
sudo systemctl status whisperhallu-server.service
sudo systemctl status demucs-server.service
sudo systemctl status video-composer-server.service
```

To stop the services:

```bash
sudo systemctl stop whisperhallu-server.service demucs-server.service video-composer-server.service
```

Or use the start scripts:

```bash
./start_whisperhallu.sh stop
./start_video_composer.sh stop
```

To restart the services:

```bash
sudo systemctl restart whisperhallu-server.service demucs-server.service video-composer-server.service
```

Or use the start scripts:

```bash
./start_whisperhallu.sh restart
./start_video_composer.sh restart
```

The services are set to start automatically on system boot.

### 6. Test the servers

You can test the servers using a tool like curl or Postman.

#### Test WhisperHallu:
```bash
curl -X POST http://127.0.0.1:8000/predict -F "audio_file=@path_to_audio_file.wav"
```

#### Test Video Scene Composer:
```bash
curl -X POST http://localhost:8890/predict \
  -H "Content-Type: application/json" \
  -d '{"project": {...your project data...}}' \
  --output composed_video.mp4
```

### 7. Run Unit Tests

To run the unit tests for the project, use the following commands:

```bash
python -m unittest test_json_util.py
python -m unittest test_video_audio_merge_server.py
```

### 8. Check logs

You can check the logs in the logs directory.

```bash
cat logs/whisperhallu_YYYYMMDD.log
cat logs/video_scene_composer_YYYYMMDD.log
```

```bash
cat logs/nohup.YYYYMMDD.out
```

These commands will run the unit tests for the JSON utility functions and the video-audio merge server, respectively. Make sure you're in the project's root directory when running these commands.

## How does it work?

### WhisperHallu Service
- **LitServe API**: The API is powered by LitServe, which handles the requests and sets up the server.
- **FasterWhisperHallu**: This model is loaded during server initialization. When an audio file is uploaded, FasterWhisperHallu processes it, splitting it into segments, and transcribes the audio.
- **Response**: The server returns the transcription in a readable format, with start and end times for each segment.

### Video Scene Composer Service
- **Purpose**: This service composes video scenes from multiple media items (images or videos) and adds an audio track.
- **Input**: JSON data containing scene information, media URLs, timing details, and audio URL.
- **Process**: 
  - Downloads each media item (video or image)
  - Creates clips with the appropriate timing (startTime to endTime)
  - Composes all clips into a single video
  - Downloads and adds the audio track
- **Output**: Returns a complete MP4 video with all scenes and audio

## WebM to MP4 Conversion Service

### What is it?
The WebM to MP4 conversion service is a lightweight API server that converts WebM video files to MP4 format using FFmpeg. It's built with LitServe and provides a simple HTTP endpoint for video conversion.

### Setting up the WebM Conversion Service

1. **Prerequisites**
   Make sure FFmpeg is installed on your system:
   ```bash
   sudo apt install ffmpeg
   ```

2. **Start the Service**
   You can start the WebM conversion service using the provided control script:
   ```bash
   chmod +x start_webmconvert.sh
   ./start_webmconvert.sh start
   ```

3. **Managing the Service**
   - To stop the service:
     ```bash
     ./start_webmconvert.sh stop
     ```
   - To restart the service:
     ```bash
     ./start_webmconvert.sh restart
     ```

4. **Check the Logs**
   You can monitor the conversion service logs:
   ```bash
   cat logs/nohup.YYYYMMDD.out
   ```

5. **Test the Service**
   You can test the conversion service using curl:
   ```bash
   curl -X POST http://localhost:8882/predict \
     -F "video=@path_to_your_video.webm" \
     -o output.mp4
   ```

The service runs on port 8882 by default and accepts WebM video files through HTTP POST requests. The converted MP4 file is returned in the response.

## Future Enhancements
- Add streaming capabilities to handle larger audio files in chunks.
- Integrate batching to handle multiple audio files in one request.
- Expand to support other models beyond FasterWhisper.
- Add more video composition features like transitions and effects.
- Support for captions and text overlays in the video composer.

## Crontab

You can add the following crontab to clean the logs every day at 00:00:

```bash
0 0 * * * /usr/bin/find /path/to/logs -type f -mtime +7 -delete
```

## Contributing
Contributions are welcome! Please fork the repository and submit pull requests.
