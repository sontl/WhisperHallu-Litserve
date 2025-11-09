import logging
import os
import shlex
import subprocess
import tempfile
import time
import urllib.parse
import requests
import boto3
import uuid
import shutil
from datetime import datetime
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional

# Load environment variables
load_dotenv()

# Logging setup
LOG_DIR = os.getenv("VIDEO2X_LOG_DIR", "./logs")
os.makedirs(LOG_DIR, exist_ok=True)


def _setup_logger():
    logger = logging.getLogger("video2x_server")
    if logger.handlers:
        return logger

    log_level = os.getenv("VIDEO2X_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(level)

    max_bytes = int(os.getenv("VIDEO2X_LOG_MAX_BYTES", 10 * 1024 * 1024))
    backup_count = int(os.getenv("VIDEO2X_LOG_BACKUP_COUNT", 5))
    log_path = os.path.join(LOG_DIR, "video2x_server.log")
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if os.getenv("VIDEO2X_LOG_STDOUT", "1") == "1":
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.propagate = False
    return logger


logger = _setup_logger()

# Initialize FastAPI app
app = FastAPI(title="Video2X Upscaler API", version="1.0.0")

# Global R2 client
r2_client = None
r2_bucket_name = os.getenv('R2_BUCKET_NAME')
r2_public_url = os.getenv('R2_PUBLIC_URL')
VIDEO2X_TIMEOUT_SECONDS = int(os.getenv("VIDEO2X_TIMEOUT_SECONDS", "0")) or None


def _job_prefix(job_id: str) -> str:
    return f"[job={job_id}]"

def initialize_r2():
    """Initialize R2 client"""
    global r2_client
    
    if all([os.getenv('R2_ACCESS_KEY_ID'), os.getenv('R2_SECRET_ACCESS_KEY'), 
            os.getenv('R2_ENDPOINT_URL'), r2_bucket_name]):
        try:
            r2_client = boto3.client(
                's3',
                endpoint_url=os.getenv('R2_ENDPOINT_URL'),
                aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
                region_name='auto'  # R2 uses 'auto' as region
            )
            logger.info("R2 client initialized successfully")
        except Exception as e:
            logger.exception("Failed to initialize R2 client: %s", e)
            r2_client = None
    else:
        logger.warning("R2 configuration incomplete - upload to R2 will be disabled")

# Initialize R2 on startup
initialize_r2()

# Pydantic model for JSON request
class UpscaleRequest(BaseModel):
    url: Optional[str] = None
    scale: int = 3
    isAnime: bool = False
    urlOutput: bool = False

def prepare_input(file: UploadFile = None, url: str = None, scale: int = 3, is_anime: bool = False, url_output: bool = False):
    """Prepare input file for processing"""
    if file is None and url is None:
        raise ValueError("Either file or URL must be provided")

    if file is not None and url is not None:
        raise ValueError("Please provide either file or URL, not both")

    temp_dir_path = tempfile.mkdtemp(prefix="video2x_")
    input_path = os.path.join(temp_dir_path, "input.mp4")
    job_id = uuid.uuid4().hex[:8]
    prefix = _job_prefix(job_id)

    logger.info(
        "%s Preparing input (temp_dir=%s, scale=%s, is_anime=%s, url_output=%s)",
        prefix,
        temp_dir_path,
        scale,
        is_anime,
        url_output,
    )

    if url is not None:
        try:
            logger.info("%s Downloading input from URL %s", prefix, url)
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            with open(input_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info("%s Download complete -> %s", prefix, input_path)
        except requests.exceptions.RequestException as e:
            shutil.rmtree(temp_dir_path, ignore_errors=True)
            logger.error("%s Failed to download input: %s", prefix, e)
            raise ValueError(f"Failed to download video from URL: {str(e)}")
    else:
        with open(input_path, "wb") as f:
            content = file.file.read()
            f.write(content)
        try:
            file_size = os.path.getsize(input_path)
        except OSError:
            file_size = "unknown"
        logger.info("%s Uploaded file saved -> %s (size=%s)", prefix, input_path, file_size)

    return {
        'input_path': input_path,
        'temp_dir_path': temp_dir_path,
        'scale': scale,
        'is_anime': is_anime,
        'url_output': url_output,
        'job_id': job_id,
    }

def process_video(request_data):
    """Process video with Video2X"""
    input_path = request_data['input_path']
    temp_dir_path = request_data['temp_dir_path']
    scale = request_data['scale']
    is_anime = request_data['is_anime']
    url_output = request_data['url_output']
    job_id = request_data.get('job_id', uuid.uuid4().hex[:8])
    prefix = _job_prefix(job_id)
    
    output_path = os.path.join(temp_dir_path, "output_upscaled.mp4")
    
    # Build command based on parameters
    command = [
        "docker", "run", "--gpus", "all",
        "-e", "NVIDIA_VISIBLE_DEVICES=all",
        "-e", "NVIDIA_DRIVER_CAPABILITIES=all",
        "-e", "VIDEO2X_VULKAN_DEVICE=0",
        "-v", f"{temp_dir_path}:/host",
        "--device", "/dev/dri",
        "--device", "/dev/nvidia0",
        "--device", "/dev/nvidiactl",
        "--device", "/dev/nvidia-modeset",
        "--device", "/dev/nvidia-uvm",
        "--device", "/dev/nvidia-uvm-tools",
        "--rm",  # Removed -it flag to avoid TTY issues
        "ghcr.io/k4yt3x/video2x:6.4.0",
        "-i", "/host/input.mp4",
        "-o", "/host/output_upscaled.mp4",
        "-s", str(scale)
    ]
    
    if is_anime:
        command.extend(["-p", "realesrgan", "--realesrgan-model", "realesr-animevideov3"])
    else:
        command.extend(["-p", "realcugan", "--realcugan-model", "models-se"])
    
    process = None
    try:
        command_str = shlex.join(command)
        logger.info("%s Starting docker command: %s", prefix, command_str)
        start_time = time.time()
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        try:
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if not line:
                        break
                    logger.info("%s [video2x] %s", prefix, line.rstrip())
            return_code = (
                process.wait(timeout=VIDEO2X_TIMEOUT_SECONDS)
                if VIDEO2X_TIMEOUT_SECONDS
                else process.wait()
            )
        finally:
            if process.stdout and not process.stdout.closed:
                process.stdout.close()

        duration = time.time() - start_time
        logger.info("%s Docker command finished in %.2fs with exit code %s", prefix, duration, return_code)

        if return_code != 0:
            raise RuntimeError(f"video2x processing failed with exit code {return_code}")
    except subprocess.TimeoutExpired:
        if process is not None:
            process.kill()
            with suppress(Exception):
                process.wait()
        logger.error(
            "%s Docker command exceeded timeout (%ss), process terminated",
            prefix,
            VIDEO2X_TIMEOUT_SECONDS,
        )
        raise RuntimeError(f"video2x processing exceeded timeout of {VIDEO2X_TIMEOUT_SECONDS} seconds")
    except Exception as e:
        if process is not None and process.poll() is None:
            process.kill()
            with suppress(Exception):
                process.wait()
        logger.exception("%s video2x processing failed", prefix)
        raise
    
    # If url_output is requested, upload to R2 and return URL
    if url_output and r2_client:
        try:
            r2_url = upload_to_r2(output_path)
            # Clean up temp directory after successful upload
            shutil.rmtree(temp_dir_path, ignore_errors=True)
            logger.info("%s Upload to R2 succeeded: %s", prefix, r2_url)
            return {'type': 'url', 'url': r2_url, 'local_path': output_path, 'job_id': job_id}
        except Exception as e:
            logger.exception("%s Failed to upload to R2: %s", prefix, e)
            # Fall back to local file path
            return {'type': 'file', 'local_path': output_path, 'temp_dir_path': temp_dir_path, 'job_id': job_id}

    logger.info("%s Processing complete -> %s", prefix, output_path)
    return {'type': 'file', 'local_path': output_path, 'temp_dir_path': temp_dir_path, 'job_id': job_id}

def upload_to_r2(file_path):
    """Upload file to R2 bucket and return public URL"""
    if not r2_client:
        raise Exception("R2 client not initialized")
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"upscaled_videos/{timestamp}_{unique_id}.mp4"
    
    # Upload file
    with open(file_path, 'rb') as file_data:
        r2_client.upload_fileobj(
            file_data,
            r2_bucket_name,
            filename,
            ExtraArgs={
                'ContentType': 'video/mp4',
                'ACL': 'public-read'  # Make file publicly accessible
            }
        )
    
    # Return public URL
    if r2_public_url:
        # Use custom domain if configured
        return f"{r2_public_url.rstrip('/')}/{filename}"
    else:
        # Use default R2 public URL format
        endpoint_url = os.getenv('R2_ENDPOINT_URL')
        account_id = endpoint_url.split('//')[1].split('.')[0]
        return f"https://pub-{account_id}.r2.dev/{filename}"

# FastAPI endpoints
@app.post("/predict")
async def predict_endpoint(file: UploadFile = File(...)):
    """LitServe-compatible predict endpoint"""
    try:
        request_data = prepare_input(file=file)
        logger.info("%s Received /predict request", _job_prefix(request_data['job_id']))
        result = process_video(request_data)
        
        if result['type'] == 'url':
            return {
                "success": True,
                "type": "url",
                "url": result['url'],
                "message": "Video processed and uploaded to R2 successfully",
                "job_id": result.get('job_id'),
            }
        else:
            return {
                "success": True,
                "type": "file",
                "file_path": result['local_path'],
                "temp_dir_path": result.get('temp_dir_path'),
                "message": "Video processed successfully",
                "job_id": result.get('job_id'),
            }
    except Exception as e:
        job_id = request_data.get('job_id') if 'request_data' in locals() else 'unknown'
        logger.exception("%s /predict failed", _job_prefix(str(job_id)))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upscale")
async def upscale_video(
    file: UploadFile = File(None),
    url: str = Form(None),
    scale: int = Form(3),
    isAnime: bool = Form(False),
    urlOutput: bool = Form(False)
):
    """Custom endpoint that handles form parameters"""
    try:
        request_data = prepare_input(file=file, url=url, scale=scale, is_anime=isAnime, url_output=urlOutput)
        logger.info("%s Received /upscale request", _job_prefix(request_data['job_id']))
        result = process_video(request_data)
        
        if result['type'] == 'url':
            return {
                "success": True,
                "type": "url",
                "url": result['url'],
                "message": "Video processed and uploaded to R2 successfully",
                "job_id": result.get('job_id'),
            }
        else:
            return {
                "success": True,
                "type": "file",
                "file_path": result['local_path'],
                "temp_dir_path": result.get('temp_dir_path'),
                "message": "Video processed successfully",
                "job_id": result.get('job_id'),
            }
    except Exception as e:
        job_id = request_data.get('job_id') if 'request_data' in locals() else 'unknown'
        logger.exception("%s /upscale failed", _job_prefix(str(job_id)))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upscale-json")
async def upscale_video_json(
    request: UpscaleRequest,
):
    """Endpoint that handles JSON payload"""
    try:
        request_data = prepare_input(
            url=request.url, 
            scale=request.scale, 
            is_anime=request.isAnime, 
            url_output=request.urlOutput
        )
        logger.info("%s Received /upscale-json request", _job_prefix(request_data['job_id']))
        result = process_video(request_data)
        
        if result['type'] == 'url':
            return {
                "success": True,
                "type": "url",
                "url": result['url'],
                "message": "Video processed and uploaded to R2 successfully",
                "job_id": result.get('job_id'),
            }
        else:
            return {
                "success": True,
                "type": "file",
                "file_path": result['local_path'],
                "temp_dir_path": result.get('temp_dir_path'),
                "message": "Video processed successfully",
                "job_id": result.get('job_id'),
            }
    except Exception as e:
        job_id = request_data.get('job_id') if 'request_data' in locals() else 'unknown'
        logger.exception("%s /upscale-json failed", _job_prefix(str(job_id)))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download")
async def download_video(file_path: str):
    """Download processed video file"""
    decoded_path = urllib.parse.unquote(file_path)
    if not os.path.exists(decoded_path):
        raise HTTPException(status_code=404, detail=f"File not found: {decoded_path}")
    try:
        return FileResponse(
            decoded_path,
            media_type="video/mp4",
            filename="upscaled_video.mp4"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "video2x-upscaler"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8866)