# Audio Utils Server - Modal Deployment

A serverless audio and video processing API deployed on Modal.com, providing utilities for media analysis and manipulation.

## Features

- **Get Audio Duration**: Extract duration from MP3 files
- **Extract Video Thumbnail**: Generate JPEG thumbnails from videos at any timestamp
- **Trim Video**: Cut video segments with precise start/end timestamps

## Prerequisites

- Python 3.8+
- Modal account ([sign up at modal.com](https://modal.com))
- Modal CLI installed and authenticated

## Setup

### 1. Install Modal

```bash
pip install modal
```

### 2. Authenticate with Modal

```bash
modal token new
```

Follow the prompts to authenticate with your Modal account.

### 3. Deploy the Service

```bash
# Deploy to production
python audio_utils_server_modal.py deploy

# Or run locally for testing
python audio_utils_server_modal.py serve
```

After deployment, Modal will provide you with endpoint URLs for each function.

## API Endpoints

### 1. Get Audio Duration

Extract the duration of an MP3 file from a URL.

**Endpoint**: `/get_duration`

**Method**: POST

**Parameters**:
- `url` (string, required): URL of the MP3 file

**Example**:
```bash
curl -X POST "https://your-app--get-duration.modal.run" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/audio.mp3"}'
```

**Response**:
```json
{
  "duration": 123.45
}
```

### 2. Extract Video Thumbnail

Generate a thumbnail image from a video at a specific timestamp.

**Endpoint**: `/extract_thumbnail`

**Method**: POST

**Parameters**:
- `url` (string, required): URL of the video file
- `timestamp` (float, optional): Time in seconds to extract frame (default: 1.0)

**Example**:
```bash
curl -X POST "https://your-app--extract-thumbnail.modal.run" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.mp4", "timestamp": 5.0}'
```

**Response**:
```json
{
  "thumbnail": "base64_encoded_jpeg_data...",
  "format": "jpeg",
  "timestamp": 5.0
}
```

### 3. Trim Video

Cut a video segment between start and end timestamps.

**Endpoint**: `/trim_video`

**Method**: POST

**Parameters**:
- `url` (string, required): URL of the video file
- `start` (float, optional): Start time in seconds (null = beginning)
- `end` (float, optional): End time in seconds (null = end of video)

**Examples**:

```bash
# Trim from 5s to 15s
curl -X POST "https://your-app--trim-video.modal.run" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.mp4", "start": 5.0, "end": 15.0}'

# Trim from beginning to 10s
curl -X POST "https://your-app--trim-video.modal.run" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.mp4", "end": 10.0}'

# Trim from 30s to end
curl -X POST "https://your-app--trim-video.modal.run" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/video.mp4", "start": 30.0}'
```

**Response**:
```json
{
  "video": "base64_encoded_mp4_data...",
  "format": "mp4",
  "start": 5.0,
  "end": 15.0
}
```

## Usage in Python

```python
import requests
import base64

# Get audio duration
response = requests.post(
    "https://your-app--get-duration.modal.run",
    json={"url": "https://example.com/audio.mp3"}
)
duration = response.json()["duration"]
print(f"Duration: {duration} seconds")

# Extract thumbnail
response = requests.post(
    "https://your-app--extract-thumbnail.modal.run",
    json={"url": "https://example.com/video.mp4", "timestamp": 2.5}
)
thumbnail_base64 = response.json()["thumbnail"]
thumbnail_data = base64.b64decode(thumbnail_base64)
with open("thumbnail.jpg", "wb") as f:
    f.write(thumbnail_data)

# Trim video
response = requests.post(
    "https://your-app--trim-video.modal.run",
    json={"url": "https://example.com/video.mp4", "start": 10.0, "end": 20.0}
)
video_base64 = response.json()["video"]
video_data = base64.b64decode(video_base64)
with open("trimmed.mp4", "wb") as f:
    f.write(video_data)
```

## Performance Notes

- **Thumbnail Extraction**: Uses FFmpeg seeking for fast frame extraction
- **Video Trimming**: Uses stream copy (`-c copy`) to avoid re-encoding, making it very fast
- **Auto-scaling**: Modal automatically scales based on demand with a 2-second scaledown window

## Monitoring

View logs and monitor your deployment:

```bash
modal app logs audio-utils
```

Or visit the Modal dashboard at [modal.com/apps](https://modal.com/apps)

## Development

### Local Testing

```bash
# Serve locally with hot reload
python audio_utils_server_modal.py serve
```

### View API Documentation

After deployment or local serving, visit the `/docs` endpoint to see interactive API documentation (Swagger UI).

## Troubleshooting

**Issue**: "Failed to download video/audio"
- Ensure the URL is publicly accessible
- Check if the URL requires authentication
- Verify the file format is supported

**Issue**: "Invalid audio/video file"
- Confirm the file is not corrupted
- Check if FFmpeg supports the codec/format

**Issue**: Modal authentication errors
- Run `modal token new` to re-authenticate
- Verify your Modal account is active

## License

Part of the AI Media Processing Platform.
