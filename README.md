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

Make sure you have Python 3.8+ installed. Install the necessary dependencies using the provided `requirements.txt` file.

```bash
pip install -r requirements.txt
```

You also need to have *FFmpeg* installed on your system. You can install it via your package manager:

```bash
sudo apt install ffmpeg
```

### 3. Set up systemd services

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

To check the status of the services:

```bash
sudo systemctl status whisperhallu-server.service
sudo systemctl status demucs-server.service
```

To stop the services:

```bash
sudo systemctl stop whisperhallu-server.service demucs-server.service
```

To restart the services:

```bash
sudo systemctl restart whisperhallu-server.service demucs-server.service
```

The services are set to start automatically on system boot.

### 6. Test the server

You can test the server using a tool like curl or Postman. Here's an example using curl:

```bash
curl -X POST http://127.0.0.1:8000/predict -F "audio_file=@path_to_audio_file.wav"
```

The response will be in JSON format and contain the transcribed text from the audio.

## How does it work?
- **LitServe API**: The API is powered by LitServe, which handles the requests and sets up the server.
- **FasterWhisperHallu**: This model is loaded during server initialization. When an audio file is uploaded, FasterWhisperHallu processes it, splitting it into segments, and transcribes the audio.
- **Response**: The server returns the transcription in a readable format, with start and end times for each segment.

## Future Enhancements
Add streaming capabilities to handle larger audio files in chunks.
Integrate batching to handle multiple audio files in one request.
Expand to support other models beyond FasterWhisper.

## Contributing
Contributions are welcome! Please fork the repository and submit pull requests.