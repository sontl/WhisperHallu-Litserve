# Video2X R2 Upload Setup

This document explains how to configure and use the R2 bucket upload feature for the Video2X upscaling service.

## Configuration

### 1. Install Dependencies
Make sure boto3 is installed:
```bash
pip install -r requirements.txt
```

### 2. Configure R2 Credentials
Add the following environment variables to your `.env` file:

```env
# R2 Bucket Configuration
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET_NAME=your_bucket_name
R2_ENDPOINT_URL=https://your_account_id.r2.cloudflarestorage.com
R2_PUBLIC_URL=https://your_custom_domain.com  # Optional: custom domain for public URLs
```

### 3. R2 Bucket Setup
1. Create a Cloudflare R2 bucket
2. Generate API tokens with R2 permissions
3. Configure bucket for public access (if you want direct URL access)
4. Optionally set up a custom domain for cleaner URLs

## Usage

### API Endpoints

#### POST /upscale
Enhanced endpoint with R2 upload support:

**Parameters:**
- `file`: Video file to upload (multipart/form-data)
- `url`: Alternative to file - URL of video to process
- `scale`: Upscaling factor (default: 3)
- `isAnime`: Use anime-specific model (default: false)
- `urlOutput`: Upload result to R2 and return URL (default: false)

**Examples:**

1. **Regular upscaling (file output):**
```bash
curl -X POST http://localhost:8866/upscale \
  -F "file=@video.mp4" \
  -F "scale=2" \
  -F "isAnime=false" \
  -F "urlOutput=false"
```

2. **Upscaling with R2 upload:**
```bash
curl -X POST http://localhost:8866/upscale \
  -F "file=@video.mp4" \
  -F "scale=2" \
  -F "isAnime=false" \
  -F "urlOutput=true"
```

3. **Process video from URL and upload to R2:**
```bash
curl -X POST http://localhost:8866/upscale \
  -F "url=https://example.com/video.mp4" \
  -F "scale=2" \
  -F "urlOutput=true"
```

### Response Formats

**File Output Response:**
```json
{
  "success": true,
  "type": "file",
  "file_path": "/tmp/tmpXXXXXX/output_upscaled.mp4",
  "message": "Video processed successfully"
}
```

**URL Output Response (R2 Upload):**
```json
{
  "success": true,
  "type": "url",
  "url": "https://your-domain.com/upscaled_videos/20250107_143022_a1b2c3d4.mp4",
  "message": "Video processed and uploaded to R2 successfully"
}
```

## Testing

Run the test script to verify functionality:
```bash
python test_video2x_r2.py
```

## Troubleshooting

### Common Issues

1. **R2 client not initialized:**
   - Check that all R2 environment variables are set
   - Verify R2 credentials are correct

2. **Upload fails:**
   - Check bucket permissions
   - Verify bucket name and endpoint URL
   - Ensure bucket allows public uploads

3. **Public URL not accessible:**
   - Configure bucket for public read access
   - Set up custom domain if using R2_PUBLIC_URL

### Logs
Check server logs for detailed error messages:
```bash
# If running with start script
cat logs/video2x_server_$(date +%Y%m%d).log

# If running directly
# Check console output
```

## File Organization

Uploaded files are organized in the R2 bucket as:
```
upscaled_videos/
├── 20250107_143022_a1b2c3d4.mp4
├── 20250107_143155_e5f6g7h8.mp4
└── ...
```

Format: `YYYYMMDD_HHMMSS_[8-char-uuid].mp4`

## Security Notes

- R2 credentials should be kept secure
- Consider using IAM roles instead of access keys in production
- Regularly rotate access keys
- Monitor bucket usage and costs
- Set up bucket lifecycle policies to manage storage costs