# Image Upscale Server

AI-powered image upscaling service using Real-ESRGAN with intelligent fallback to high-quality PIL processing.

## Overview

The Image Upscale Server provides HTTP APIs for upscaling images using state-of-the-art AI models. It automatically detects available Real-ESRGAN implementations and falls back to high-quality PIL Lanczos resampling when needed, ensuring reliable operation in any environment.

## Features

- **Smart Backend Detection**: Automatically uses the best available upscaling method
- **Multiple Input Methods**: File upload, URL processing, or JSON payloads
- **Format Support**: JPG, PNG, WebP, BMP, TIFF
- **R2 Cloud Storage**: Optional upload to Cloudflare R2 with public URLs
- **Download URLs**: Direct download links for processed images
- **Production Ready**: Comprehensive logging, error handling, and monitoring

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make management script executable
chmod +x start_image_upscale_server.sh
```

### 2. Start the Service

```bash
./start_image_upscale_server.sh start
```

The service will be available at `http://localhost:8867`

### 3. Test the Service

```bash
# Health check
curl http://localhost:8867/health

# List available models
curl http://localhost:8867/models

# Test with a sample image
curl -X POST http://localhost:8867/upscale \
  -F "file=@your_image.jpg" \
  -F "scale=4" \
  -F "model=RealESRGAN_x4"
```

## API Endpoints

### POST /predict
LitServe-compatible endpoint for file uploads.

**Parameters:**
- `file` (required): Image file to upscale

**Example:**
```bash
curl -X POST http://localhost:8867/predict \
  -F "file=@image.jpg"
```

### POST /upscale
Main endpoint supporting both file uploads and URL processing.

**Parameters:**
- `file` (optional): Image file to upload
- `url` (optional): URL of image to process
- `scale` (optional): Upscaling factor (default: 4)
- `model` (optional): Model to use (default: RealESRGAN_x4)
- `urlOutput` (optional): Upload result to R2 (default: false)

**Examples:**
```bash
# Upload file
curl -X POST http://localhost:8867/upscale \
  -F "file=@image.jpg" \
  -F "scale=4" \
  -F "model=RealESRGAN_x4"

# Process from URL
curl -X POST http://localhost:8867/upscale \
  -F "url=https://example.com/image.jpg" \
  -F "scale=2" \
  -F "model=RealESRGAN_x2"
```

### POST /upscale-json
JSON endpoint for programmatic access.

**Request Body:**
```json
{
  "url": "https://example.com/image.jpg",
  "scale": 4,
  "model": "RealESRGAN_x4",
  "urlOutput": false
}
```

**Example:**
```bash
curl -X POST http://localhost:8867/upscale-json \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/image.jpg",
    "scale": 4,
    "model": "RealESRGAN_x4"
  }'
```

### GET /download
Download processed images using the download URL from responses.

**Parameters:**
- `file_path` (required): Encoded file path from API response

**Example:**
```bash
curl "http://localhost:8867/download?file_path=/tmp/image_upscale_abc123/output.jpg" \
  -o upscaled_image.jpg
```

### GET /models
List available upscaling models and backend information.

**Example:**
```bash
curl http://localhost:8867/models
```

**Response:**
```json
{
  "models": {
    "RealESRGAN_x4": {
      "description": "General purpose 4x upscaling model (default)",
      "scale": 4,
      "type": "general",
      "backend": "fallback"
    },
    "RealESRGAN_x2": {
      "description": "General purpose 2x upscaling model",
      "scale": 2,
      "type": "general",
      "backend": "fallback"
    },
    "RealESRGAN_anime": {
      "description": "Anime-specific upscaling model",
      "scale": 4,
      "type": "anime",
      "backend": "fallback"
    }
  },
  "backend": "fallback",
  "note": "Using PIL fallback if Real-ESRGAN not available"
}
```

### GET /health
Health check endpoint.

**Example:**
```bash
curl http://localhost:8867/health
```

## Response Format

All processing endpoints return a consistent response format:

### Successful Response (File)
```json
{
  "success": true,
  "type": "file",
  "file_path": "/tmp/image_upscale_abc123/output_upscaled.jpg",
  "download_url": "/download?file_path=/tmp/image_upscale_abc123/output_upscaled.jpg",
  "temp_dir_path": "/tmp/image_upscale_abc123",
  "message": "Image processed successfully",
  "job_id": "abc12345"
}
```

### Successful Response (R2 Upload)
```json
{
  "success": true,
  "type": "url",
  "url": "https://your-r2-domain.com/upscaled_images/20231219_123456_abc123.jpg",
  "message": "Image processed and uploaded to R2 successfully",
  "job_id": "abc12345"
}
```

### Error Response
```json
{
  "detail": "Error message describing what went wrong"
}
```

## Available Models

| Model | Scale | Type | Description |
|-------|-------|------|-------------|
| `RealESRGAN_x4` | 4x | General | Default general-purpose upscaling |
| `RealESRGAN_x2` | 2x | General | Lighter 2x upscaling |
| `RealESRGAN_anime` | 4x | Anime | Optimized for anime/cartoon images |

## Backend Detection

The service automatically detects and uses the best available backend:

1. **Real-ESRGAN NCNN Vulkan**: GPU-accelerated, fastest performance
2. **Real-ESRGAN Python**: CPU/GPU processing via Python package  
3. **Simple Real-ESRGAN**: PyTorch-based implementation with neural network upscaling
4. **PIL Fallback**: High-quality Lanczos resampling (always available)

## Service Management

### Start/Stop/Restart
```bash
# Start the service
./start_image_upscale_server.sh start

# Stop the service
./start_image_upscale_server.sh stop

# Restart the service
./start_image_upscale_server.sh restart

# Check status
./start_image_upscale_server.sh status
```

### Logs
```bash
# View recent logs
tail -f logs/nohup.$(date +%Y%m%d).out

# View service-specific logs
tail -f logs/image_upscale_server.log
```

## Configuration

### Environment Variables

Create a `.env` file with the following optional configurations:

```bash
# Logging
IMAGE_UPSCALE_LOG_LEVEL=INFO
IMAGE_UPSCALE_LOG_STDOUT=1
IMAGE_UPSCALE_LOG_MAX_BYTES=10485760
IMAGE_UPSCALE_LOG_BACKUP_COUNT=5

# Processing
REALESRGAN_TIMEOUT_SECONDS=300

# R2 Storage (optional)
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_ENDPOINT_URL=https://your_account_id.r2.cloudflarestorage.com
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_URL=https://your_custom_domain.com
```

### Real-ESRGAN Installation (Optional)

For better performance, install Real-ESRGAN:

```bash
# Option 1: Install via pip (may have compatibility issues)
pip install realesrgan basicsr facexlib gfpgan

# Option 2: Install NCNN Vulkan binary (recommended for production)
# Download from: https://github.com/xinntao/Real-ESRGAN/releases
# Extract and add to PATH
```

## Testing

Run the comprehensive test suite:

```bash
python test_image_upscale.py
```

This will test:
- Health check endpoint
- Models listing
- File upload processing
- URL processing
- JSON endpoint
- Download functionality

## Integration Examples

### Python Client
```python
import requests

# Upload and process image
with open('image.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8867/upscale',
        files={'file': f},
        data={'scale': 4, 'model': 'RealESRGAN_x4'}
    )

result = response.json()
if result['success']:
    # Download the processed image
    download_response = requests.get(
        f"http://localhost:8867{result['download_url']}"
    )
    with open('upscaled_image.jpg', 'wb') as f:
        f.write(download_response.content)
```

### JavaScript/Node.js
```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function upscaleImage(imagePath) {
    const form = new FormData();
    form.append('file', fs.createReadStream(imagePath));
    form.append('scale', '4');
    form.append('model', 'RealESRGAN_x4');

    const response = await axios.post(
        'http://localhost:8867/upscale',
        form,
        { headers: form.getHeaders() }
    );

    if (response.data.success) {
        // Download the result
        const downloadResponse = await axios.get(
            `http://localhost:8867${response.data.download_url}`,
            { responseType: 'stream' }
        );
        
        downloadResponse.data.pipe(fs.createWriteStream('upscaled.jpg'));
    }
}
```

## Performance Notes

- **Simple Real-ESRGAN**: Neural network-based upscaling, good quality, GPU-accelerated when available
- **PIL Fallback**: Always available, good quality, moderate speed
- **Real-ESRGAN NCNN/Python**: Superior quality, requires additional installation
- **File Size**: Larger images take longer to process
- **Memory Usage**: 4x upscaling requires significant RAM for large images
- **GPU Acceleration**: Simple Real-ESRGAN and full Real-ESRGAN can utilize CUDA when available

## Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   # Check if port is in use
   lsof -i :8867
   
   # Check logs
   tail logs/nohup.$(date +%Y%m%d).out
   ```

2. **Real-ESRGAN not working**
   - Service automatically falls back to PIL
   - Check logs for backend detection results
   - Verify Real-ESRGAN installation

3. **Out of memory errors**
   - Reduce image size before processing
   - Use lower scale factors (2x instead of 4x)
   - Monitor system memory usage

4. **Slow processing**
   - PIL fallback is slower than Real-ESRGAN
   - Consider installing Real-ESRGAN NCNN for better performance
   - Use appropriate scale factors

### Log Analysis
```bash
# Check backend detection
grep "backend" logs/image_upscale_server.log

# Monitor processing times
grep "Processing complete" logs/image_upscale_server.log

# Check for errors
grep "ERROR\|EXCEPTION" logs/image_upscale_server.log
```

## Production Deployment

### Systemd Service
Create `/etc/systemd/system/image-upscale.service`:

```ini
[Unit]
Description=Image Upscale Server
After=network.target

[Service]
Type=forking
User=your_user
WorkingDirectory=/path/to/your/project
ExecStart=/path/to/your/project/start_image_upscale_server.sh start
ExecStop=/path/to/your/project/start_image_upscale_server.sh stop
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable image-upscale
sudo systemctl start image-upscale
sudo systemctl status image-upscale
```

### Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8867;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeouts for large image processing
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # Increase max body size for image uploads
        client_max_body_size 50M;
    }
}
```

## License

This service is part of the AI Media Processing Platform. See the main project README for license information.