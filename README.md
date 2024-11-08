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

You can set up the environment variables in the .env file.  Set the permissions so only the owner can read/write the file:

```bash
chmod 600 .env
```

### 4. Set up systemd services

Create systemd service files for both the WhisperHallu and Demucs servers:

```bash
sudo nano /etc/systemd/system/whisperhallu-server.service
sudo nano /etc/systemd/system/demucs-server.service
```

Add the appropriate content to each file (refer to the service file content provided earlier).

### 4. Start the services

After creating the service files, reload the systemd manager and start the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable whisperhallu-server.service demucs-server.service
sudo systemctl start whisperhallu-server.service demucs-server.service
```

### 5. Managing the services

Run with nohup

```bash
nohup python whisperhallu_server.py &
nohup python demucs_server.py &
```

Or use the start_whisperhallu.sh script:

```bash
chmod +x start_whisperhallu.sh
```bash
./start_whisperhallu.sh start
```


To check the status of the services:

```bash
sudo systemctl status whisperhallu-server.service
sudo systemctl status demucs-server.service
```

To stop the services:

```bash
sudo systemctl stop whisperhallu-server.service demucs-server.service
```

Or use the start_whisperhallu.sh script:

```bash
./start_whisperhallu.sh stop
```


To restart the services:

```bash
sudo systemctl restart whisperhallu-server.service demucs-server.service
```

Or use the start_whisperhallu.sh script:

```bash
./start_whisperhallu.sh restart
```

The services are set to start automatically on system boot.

### 6. Test the server

You can test the server using a tool like curl or Postman. Here's an example using curl:

```bash
curl -X POST http://127.0.0.1:8000/predict -F "audio_file=@path_to_audio_file.wav"
```

The response will be in JSON format and contain the transcribed text from the audio.

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
```

```bash
cat logs/nohup.YYYYMMDD.out
```



These commands will run the unit tests for the JSON utility functions and the video-audio merge server, respectively. Make sure you're in the project's root directory when running these commands.

## How does it work?
- **LitServe API**: The API is powered by LitServe, which handles the requests and sets up the server.
- **FasterWhisperHallu**: This model is loaded during server initialization. When an audio file is uploaded, FasterWhisperHallu processes it, splitting it into segments, and transcribes the audio.
- **Response**: The server returns the transcription in a readable format, with start and end times for each segment.

## Future Enhancements
Add streaming capabilities to handle larger audio files in chunks.
Integrate batching to handle multiple audio files in one request.
Expand to support other models beyond FasterWhisper.

## Crontab

You can add the following crontab to clean the logs every day at 00:00:

```bash
0 0 * * * /usr/bin/find /path/to/logs -type f -mtime +7 -delete
```



## Contributing
Contributions are welcome! Please fork the repository and submit pull requests.
