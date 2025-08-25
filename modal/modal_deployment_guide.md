# Modal.com Audio Transcription API Deployment Guide

## Prerequisites

1. **Modal Account**: Sign up at [modal.com](https://modal.com)
2. **Modal CLI**: Install and authenticate
   ```bash
   pip install modal
   modal token new
   ```
3. **Gladia API Key**: Get your API key from [gladia.io](https://gladia.io)

## Setup

### 1. Create Modal Secret for Gladia API Key

```bash
modal secret create gladia-api-key GLADIA_API_KEY=your_gladia_api_key_here
```

### 2. Deploy the API

```bash
modal deploy modal_transcribe_api.py
```

This will deploy your API and provide you with a webhook URL.

## API Usage

### Endpoint
- **Method**: POST
- **URL**: `https://your-modal-app-url.modal.run/transcribe_endpoint`
- **Content-Type**: `application/json`

### Request Format
```json
{
    "url": "https://example.com/audio.mp3",
    "lng": "en",
    "lng_input": "auto"
}
```

### Parameters
- `url` (required): Direct URL to the audio file
- `lng` (required): Target language code (e.g., "en", "fr", "es")
- `lng_input` (optional): Source language code or "auto" for detection

### Response Format
```json
{
    "text": "Full transcription text",
    "srt": "SRT formatted subtitles",
    "json": [
        {
            "start": 0.0,
            "end": 2.5,
            "sentence": "Hello world",
            "words": [
                {
                    "start": 0.0,
                    "end": 0.8,
                    "text": "Hello"
                },
                {
                    "start": 0.9,
                    "end": 2.5,
                    "text": "world"
                }
            ]
        }
    ]
}
```

## Features

- **Vocal Extraction**: Uses Demucs to extract vocals from music/mixed audio
- **High-Quality Transcription**: Leverages Gladia API for accurate transcription
- **Multiple Languages**: Supports language detection and translation
- **Subtitle Generation**: Provides SRT format subtitles with timestamps
- **Word-Level Timestamps**: Detailed timing information for each word

## Error Handling

The API returns error responses in this format:
```json
{
    "error": "Error description"
}
```

Common errors:
- Missing `url` parameter
- Invalid audio URL
- Gladia API key not configured
- Audio processing timeout (10 minutes max)

## Performance Notes

- **GPU Acceleration**: Uses T4 GPU for Demucs processing
- **Timeout**: 10 minutes maximum processing time
- **File Size**: Recommended max 100MB audio files
- **Cold Start**: First request may take 30-60 seconds for model loading

## Monitoring

Check logs in Modal dashboard:
```bash
modal logs modal_transcribe_api.py
```
