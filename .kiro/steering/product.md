# Product Overview

This is a multi-service AI media processing platform that provides HTTP APIs for audio transcription, video processing, and media conversion. The core services include:

- **WhisperHallu**: Speech-to-text transcription using FasterWhisper with hallucination detection
- **Video Scene Composer**: Creates composite videos from multiple media sources with audio tracks
- **Video2X Upscaler**: AI-powered video upscaling with GPU acceleration using Docker containers
- **WebM Converter**: Converts WebM video files to MP4 format
- **Demucs**: Audio source separation service
- **Audio Utils**: General audio processing utilities

The platform is designed for production deployment with systemd services, comprehensive logging, and process management scripts. Each service runs independently on different ports and can be managed via shell scripts or systemd.

## Key Features
- Real-time audio transcription with language detection
- Video composition from multiple sources
- AI-powered video upscaling (general and anime-specific models)
- Audio source separation
- Format conversion utilities
- Production-ready deployment with monitoring and logging