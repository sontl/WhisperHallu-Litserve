import logging
import os
import tempfile
import time
import urllib.parse
import requests
import boto3
import uuid
import shutil
import subprocess
import shlex
from datetime import datetime
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
from PIL import Image

# Load environment variables
load_dotenv()

# Logging setup
LOG_DIR = os.getenv("IMAGE_UPSCALE_LOG_DIR", "./logs")
os.makedirs(LOG_DIR, exist_ok=True)


def _setup_logger():
    logger = logging.getLogger("image_upscale_server")
    if logger.handlers:
        return logger

    log_level = os.getenv("IMAGE_UPSCALE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    logger.setLevel(level)

    max_bytes = int(os.getenv("IMAGE_UPSCALE_LOG_MAX_BYTES", 10 * 1024 * 1024))
    backup_count = int(os.getenv("IMAGE_UPSCALE_LOG_BACKUP_COUNT", 5))
    log_path = os.path.join(LOG_DIR, "image_upscale_server.log")
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if os.getenv("IMAGE_UPSCALE_LOG_STDOUT", "1") == "1":
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.propagate = False
    return logger


logger = _setup_logger()

# Initialize FastAPI app
app = FastAPI(title="Image Upscaler API", version="1.0.0")

# Global R2 client
r2_client = None
r2_bucket_name = os.getenv('R2_BUCKET_NAME')
r2_public_url = os.getenv('R2_PUBLIC_URL')
REALESRGAN_TIMEOUT_SECONDS = int(os.getenv("REALESRGAN_TIMEOUT_SECONDS", "300")) or None


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

def check_realesrgan_installation():
    """Check if Real-ESRGAN CLI is available"""
    try:
        result = subprocess.run(['realesrgan-ncnn-vulkan', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("Real-ESRGAN NCNN Vulkan found")
            return 'ncnn'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    try:
        result = subprocess.run(['python', '-c', 'import realesrgan; print("OK")'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and 'OK' in result.stdout:
            logger.info("Real-ESRGAN Python package found")
            return 'python'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    try:
        # Try our simple implementation
        from simple_realesrgan import create_simple_realesrgan
        import torch
        model = create_simple_realesrgan()
        model.load_model()
        logger.info("Simple Real-ESRGAN implementation loaded")
        return 'simple'
    except Exception as e:
        logger.warning("Simple Real-ESRGAN failed to load: %s", e)
    
    logger.warning("No Real-ESRGAN implementation found, will use basic PIL upscaling")
    return 'fallback'

# Initialize R2 on startup
initialize_r2()
realesrgan_backend = check_realesrgan_installation()

# Pydantic model for JSON request
class UpscaleRequest(BaseModel):
    url: Optional[str] = None
    scale: int = 4
    model: str = "RealESRGAN_x4"  # Default model
    urlOutput: bool = False

# Supported image formats
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}

def validate_image_format(file_path: str) -> bool:
    """Validate if the file is a supported image format"""
    _, ext = os.path.splitext(file_path.lower())
    return ext in SUPPORTED_FORMATS

def prepare_input(file: UploadFile = None, url: str = None, scale: int = 4, model: str = "RealESRGAN_x4", url_output: bool = False):
    """Prepare input file for processing"""
    if file is None and url is None:
        raise ValueError("Either file or URL must be provided")

    if file is not None and url is not None:
        raise ValueError("Please provide either file or URL, not both")

    temp_dir_path = tempfile.mkdtemp(prefix="image_upscale_")
    job_id = uuid.uuid4().hex[:8]
    prefix = _job_prefix(job_id)

    logger.info(
        "%s Preparing input (temp_dir=%s, scale=%s, model=%s, url_output=%s)",
        prefix,
        temp_dir_path,
        scale,
        model,
        url_output,
    )

    if url is not None:
        try:
            logger.info("%s Downloading input from URL %s", prefix, url)
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            # Determine file extension from content-type or URL
            content_type = response.headers.get('content-type', '')
            if 'image/jpeg' in content_type:
                ext = '.jpg'
            elif 'image/png' in content_type:
                ext = '.png'
            elif 'image/webp' in content_type:
                ext = '.webp'
            else:
                # Try to get extension from URL
                parsed_url = urllib.parse.urlparse(url)
                _, ext = os.path.splitext(parsed_url.path)
                if not ext or ext.lower() not in SUPPORTED_FORMATS:
                    ext = '.jpg'  # Default fallback
            
            input_path = os.path.join(temp_dir_path, f"input{ext}")
            
            with open(input_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.info("%s Download complete -> %s", prefix, input_path)
        except requests.exceptions.RequestException as e:
            shutil.rmtree(temp_dir_path, ignore_errors=True)
            logger.error("%s Failed to download input: %s", prefix, e)
            raise ValueError(f"Failed to download image from URL: {str(e)}")
    else:
        # Get file extension from uploaded file
        filename = file.filename or "input.jpg"
        _, ext = os.path.splitext(filename.lower())
        if not ext or ext not in SUPPORTED_FORMATS:
            ext = '.jpg'  # Default fallback
            
        input_path = os.path.join(temp_dir_path, f"input{ext}")
        
        with open(input_path, "wb") as f:
            content = file.file.read()
            f.write(content)
        try:
            file_size = os.path.getsize(input_path)
        except OSError:
            file_size = "unknown"
        logger.info("%s Uploaded file saved -> %s (size=%s)", prefix, input_path, file_size)

    # Validate the image
    if not validate_image_format(input_path):
        shutil.rmtree(temp_dir_path, ignore_errors=True)
        raise ValueError(f"Unsupported image format. Supported formats: {', '.join(SUPPORTED_FORMATS)}")

    return {
        'input_path': input_path,
        'temp_dir_path': temp_dir_path,
        'scale': scale,
        'model': model,
        'url_output': url_output,
        'job_id': job_id,
    }
def process_image_fallback(input_path, output_path, scale, prefix):
    """Fallback image processing using PIL"""
    logger.info("%s Using PIL fallback for upscaling", prefix)
    
    # Load image
    image = Image.open(input_path)
    original_size = image.size
    
    # Calculate new size
    new_size = (original_size[0] * scale, original_size[1] * scale)
    
    # Upscale using Lanczos resampling (high quality)
    upscaled = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Save result
    upscaled.save(output_path, quality=95)
    
    return original_size, new_size

def process_image_ncnn(input_path, output_path, scale, model_name, prefix):
    """Process image using Real-ESRGAN NCNN Vulkan"""
    logger.info("%s Using Real-ESRGAN NCNN Vulkan", prefix)
    
    # Map model names to NCNN models
    model_mapping = {
        "RealESRGAN_x4": "realesrgan-x4plus",
        "RealESRGAN_x2": "realesrgan-x4plus",  # Will scale down result
        "RealESRGAN_anime": "realesrgan-x4plus-anime"
    }
    
    ncnn_model = model_mapping.get(model_name, "realesrgan-x4plus")
    
    # Build command
    command = [
        "realesrgan-ncnn-vulkan",
        "-i", input_path,
        "-o", output_path,
        "-n", ncnn_model,
        "-s", str(scale),
        "-f", "jpg"  # Output format
    ]
    
    # Execute command
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=REALESRGAN_TIMEOUT_SECONDS
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Real-ESRGAN NCNN failed: {result.stderr}")
    
    return result

def process_image_python_cli(input_path, output_path, scale, model_name, prefix):
    """Process image using Real-ESRGAN Python CLI"""
    logger.info("%s Using Real-ESRGAN Python CLI", prefix)
    
    # Build command
    command = [
        "python", "-m", "realesrgan.inference_realesrgan",
        "-i", input_path,
        "-o", output_path,
        "-s", str(scale),
        "--model_name", "RealESRGAN_x4plus"
    ]
    
    # Execute command
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=REALESRGAN_TIMEOUT_SECONDS
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Real-ESRGAN Python CLI failed: {result.stderr}")
    
    return result

def process_image_simple(input_path, output_path, scale, model_name, prefix):
    """Process image using Simple Real-ESRGAN implementation"""
    logger.info("%s Using Simple Real-ESRGAN implementation", prefix)
    
    try:
        from simple_realesrgan import create_simple_realesrgan
        import cv2
        
        # Map model names
        esrgan_model = 'RealESRGAN_x4plus'
        if 'x2' in model_name.lower():
            esrgan_model = 'RealESRGAN_x2plus'
        elif 'anime' in model_name.lower():
            esrgan_model = 'RealESRGAN_x4plus_anime_6B'
        
        # Create model
        model = create_simple_realesrgan(scale=scale, model_name=esrgan_model)
        model.load_model()
        
        if model.using_real_model:
            logger.info("%s Real-ESRGAN model loaded successfully", prefix)
        else:
            logger.warning("%s Using bicubic fallback (Real-ESRGAN weights not available)", prefix)
        
        # Load image
        img = cv2.imread(input_path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Could not load image from {input_path}")
        
        # Process image
        output, _ = model.enhance(img, outscale=scale)
        
        # Save result
        cv2.imwrite(output_path, output)
        
        return True
        
    except Exception as e:
        raise RuntimeError(f"Simple Real-ESRGAN failed: {str(e)}")

def process_image(request_data):
    """Process image with available Real-ESRGAN backend"""
    input_path = request_data['input_path']
    temp_dir_path = request_data['temp_dir_path']
    scale = request_data['scale']
    model_name = request_data['model']
    url_output = request_data['url_output']
    job_id = request_data.get('job_id', uuid.uuid4().hex[:8])
    prefix = _job_prefix(job_id)
    
    # Get input file extension to maintain format
    _, input_ext = os.path.splitext(input_path)
    output_path = os.path.join(temp_dir_path, f"output_upscaled{input_ext}")
    
    try:
        logger.info("%s Starting image processing (backend=%s, model=%s, scale=%s)", 
                   prefix, realesrgan_backend, model_name, scale)
        start_time = time.time()
        
        # Get original image size for logging
        with Image.open(input_path) as img:
            original_size = img.size
        logger.info("%s Original image size: %sx%s", prefix, original_size[0], original_size[1])
        
        # Process based on available backend
        if realesrgan_backend == 'ncnn':
            try:
                process_image_ncnn(input_path, output_path, scale, model_name, prefix)
            except Exception as e:
                logger.warning("%s NCNN backend failed, falling back to PIL: %s", prefix, e)
                original_size, new_size = process_image_fallback(input_path, output_path, scale, prefix)
        elif realesrgan_backend == 'python':
            try:
                process_image_python_cli(input_path, output_path, scale, model_name, prefix)
            except Exception as e:
                logger.warning("%s Python CLI backend failed, falling back to PIL: %s", prefix, e)
                original_size, new_size = process_image_fallback(input_path, output_path, scale, prefix)
        elif realesrgan_backend == 'simple':
            try:
                process_image_simple(input_path, output_path, scale, model_name, prefix)
            except Exception as e:
                logger.warning("%s Simple Real-ESRGAN failed, falling back to PIL: %s", prefix, e)
                original_size, new_size = process_image_fallback(input_path, output_path, scale, prefix)
        else:
            # Fallback to PIL
            original_size, new_size = process_image_fallback(input_path, output_path, scale, prefix)
        
        # Get final image size
        if os.path.exists(output_path):
            with Image.open(output_path) as img:
                final_size = img.size
        else:
            raise RuntimeError("Output file was not created")
        
        duration = time.time() - start_time
        logger.info(
            "%s Processing complete in %.2fs (size: %sx%s -> %sx%s)",
            prefix,
            duration,
            original_size[0],
            original_size[1],
            final_size[0],
            final_size[1]
        )
        
    except Exception as e:
        logger.exception("%s Image processing failed", prefix)
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

def create_response(result):
    """Create consistent API response with download URL"""
    if result['type'] == 'url':
        return {
            "success": True,
            "type": "url",
            "url": result['url'],
            "message": "Image processed and uploaded to R2 successfully",
            "job_id": result.get('job_id'),
        }
    else:
        # Generate download URL for the file
        encoded_path = urllib.parse.quote(result['local_path'])
        download_url = f"/download?file_path={encoded_path}"
        
        return {
            "success": True,
            "type": "file",
            "file_path": result['local_path'],
            "download_url": download_url,
            "temp_dir_path": result.get('temp_dir_path'),
            "message": "Image processed successfully",
            "job_id": result.get('job_id'),
        }

def upload_to_r2(file_path):
    """Upload file to R2 bucket and return public URL"""
    if not r2_client:
        raise Exception("R2 client not initialized")
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    _, ext = os.path.splitext(file_path)
    filename = f"upscaled_images/{timestamp}_{unique_id}{ext}"
    
    # Determine content type based on file extension
    content_type_mapping = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg', 
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff'
    }
    content_type = content_type_mapping.get(ext.lower(), 'image/jpeg')
    
    # Upload file
    with open(file_path, 'rb') as file_data:
        r2_client.upload_fileobj(
            file_data,
            r2_bucket_name,
            filename,
            ExtraArgs={
                'ContentType': content_type,
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
        result = process_image(request_data)
        return create_response(result)
    except Exception as e:
        job_id = request_data.get('job_id') if 'request_data' in locals() else 'unknown'
        logger.exception("%s /predict failed", _job_prefix(str(job_id)))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upscale")
async def upscale_image(
    file: UploadFile = File(None),
    url: str = Form(None),
    scale: int = Form(2),
    model: str = Form("RealESRGAN_x2plus"),
    urlOutput: bool = Form(False)
):
    """Custom endpoint that handles form parameters"""
    try:
        request_data = prepare_input(file=file, url=url, scale=scale, model=model, url_output=urlOutput)
        logger.info("%s Received /upscale request", _job_prefix(request_data['job_id']))
        result = process_image(request_data)
        return create_response(result)
    except Exception as e:
        job_id = request_data.get('job_id') if 'request_data' in locals() else 'unknown'
        logger.exception("%s /upscale failed", _job_prefix(str(job_id)))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upscale-json")
async def upscale_image_json(
    request: UpscaleRequest,
):
    """Endpoint that handles JSON payload"""
    try:
        request_data = prepare_input(
            url=request.url, 
            scale=request.scale, 
            model=request.model,
            url_output=request.urlOutput
        )
        logger.info("%s Received /upscale-json request", _job_prefix(request_data['job_id']))
        result = process_image(request_data)
        return create_response(result)
    except Exception as e:
        job_id = request_data.get('job_id') if 'request_data' in locals() else 'unknown'
        logger.exception("%s /upscale-json failed", _job_prefix(str(job_id)))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download")
async def download_image(file_path: str):
    """Download processed image file"""
    decoded_path = urllib.parse.unquote(file_path)
    if not os.path.exists(decoded_path):
        raise HTTPException(status_code=404, detail=f"File not found: {decoded_path}")
    
    # Determine media type based on file extension
    _, ext = os.path.splitext(decoded_path.lower())
    media_type_mapping = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff'
    }
    media_type = media_type_mapping.get(ext, 'image/jpeg')
    
    try:
        return FileResponse(
            decoded_path,
            media_type=media_type,
            filename=f"upscaled_image{ext}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")

@app.get("/models")
async def list_models():
    """List available Real-ESRGAN models"""
    models = {
        "RealESRGAN_x4": {
            "description": "General purpose 4x upscaling model (default)",
            "scale": 4,
            "type": "general",
            "backend": realesrgan_backend
        },
        "RealESRGAN_x2": {
            "description": "General purpose 2x upscaling model",
            "scale": 2,
            "type": "general", 
            "backend": realesrgan_backend
        },
        "RealESRGAN_anime": {
            "description": "Anime-specific upscaling model",
            "scale": 4,
            "type": "anime",
            "backend": realesrgan_backend
        }
    }
    return {
        "models": models,
        "backend": realesrgan_backend,
        "note": "Using PIL fallback if Real-ESRGAN not available" if realesrgan_backend == 'fallback' else "Real-ESRGAN available"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "image-upscaler"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8867)