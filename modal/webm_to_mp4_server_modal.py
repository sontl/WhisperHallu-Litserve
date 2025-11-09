import modal
import os
import typer
import subprocess

from fastapi import HTTPException, UploadFile, Response, Request
from starlette.middleware.cors import CORSMiddleware

# Create Modal app
app = modal.App("webm-to-mp4")

# Create the image with FFmpeg that includes NVENC (BtbN FFmpeg-Builds)
image = (
    modal.Image.debian_slim()
    .apt_install([
        "wget", "xz-utils"
    ])
    .run_commands([
        # Install FFmpeg with NVENC (yt-dlp FFmpeg-Builds known-good URL)
        "set -e",
        "wget -q -O ffmpeg.tar.xz https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-n7.1-latest-linux64-gpl-7.1.tar.xz",
        "tar -xf ffmpeg.tar.xz",
        "mv ffmpeg-*/bin/ffmpeg /usr/local/bin/",
        "mv ffmpeg-*/bin/ffprobe /usr/local/bin/",
        "chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe",
        "rm -rf ffmpeg*"
    ])
    .pip_install(["ffmpeg-python", "fastapi[standard]", "typer"])
)

# CPU-only image for fallback encoding (cost optimization)
cpu_image = (
    modal.Image.debian_slim()
    .apt_install([
        "wget", "xz-utils"
    ])
    .run_commands([
        # Install newer FFmpeg for CPU encoding
        "wget -O ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
        "tar -xf ffmpeg.tar.xz",
        "mv ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/",
        "mv ffmpeg-*-amd64-static/ffprobe /usr/local/bin/",
        "chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe",
        "rm -rf ffmpeg*"
    ])
    .pip_install(["ffmpeg-python", "typer", "fastapi[standard]"])
)

# GPU-only function for NVENC encoding
@app.function(
    image=image,
    timeout=2000,
    gpu="T4",
    scaledown_window=2
)
def gpu_convert(webm_content: bytes, compress: bool = False):
    import logging
    import tempfile
    import ffmpeg
    import os
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting GPU NVENC conversion")
    
    # Create temporary files
    webm_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    
    try:
        # Save content to temp file
        webm_temp.write(webm_content)
        webm_temp.close()
        
        # T4 GPU optimized encoding parameters (fast + high quality)
        gpu_params = {
            'vcodec': 'h264_nvenc',
            'acodec': 'aac',
            'tune': 'hq',
            'preset': 'p7',           # faster than p4, good quality
            'profile:v': 'high',
            'refs': '4',
            'g': '240',
            'spatial-aq': '1',
            'temporal-aq': '1',
            'bf': '3',                # better compression/quality
            'rc': 'vbr_hq',              # rate control
            'rc-lookahead': '32',     # lookahead for b-frames/rc
            'aq-strength': '8',
            'b:v': '6M',     
            'b:a': '192k',         # raise bitrate to preserve quality
            'maxrate': '10M',
            'bufsize': '20M',
            'ac': 2,                  # Audio channels
            'ar': '48000',            # Audio sample rate
            'movflags': '+faststart',
        }
        
        if compress:
            gpu_params.update({
                'b:v': '800k',
                'maxrate': '1M',
                'bufsize': '2M',
                'b:a': '96k'
            })
        
        # Convert with GPU: enable NVDEC and keep frames on GPU path
        stream = ffmpeg.input(
            webm_temp.name,
            hwaccel='cuda',
            hwaccel_output_format='cuda'
        )
        stream = ffmpeg.output(
            stream,
            output_path,
            vf='scale_cuda=format=nv12',
            **gpu_params
        )
        
        try:
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            error_details = f"FFmpeg stderr: {e.stderr.decode() if e.stderr else 'No stderr'}"
            logger.error(f"GPU encoding failed: {error_details}")
            raise Exception(f"GPU encoding failed: {error_details}")
        
        # Read result
        with open(output_path, "rb") as f:
            result_content = f.read()
        
        logger.info(f"GPU conversion completed, output size: {len(result_content)} bytes")
        return result_content
        
    finally:
        # Cleanup
        try:
            if os.path.exists(webm_temp.name):
                os.unlink(webm_temp.name)
            if os.path.exists(output_path):
                os.unlink(output_path)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup error: {cleanup_error}")

# CPU fallback function for when GPU fails
@app.function(
    image=cpu_image,
    timeout=2000,
    cpu=2.0,
    scaledown_window=2
)
def cpu_fallback_convert(webm_content: bytes, compress: bool = False):
    import logging
    import tempfile
    import ffmpeg
    import os
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting CPU fallback conversion")
    
    # Create temporary files
    webm_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    
    try:
        # Save content to temp file
        webm_temp.write(webm_content)
        webm_temp.close()
        
        # CPU encoding parameters
        cpu_params = {
            'vcodec': 'libx264',
            'acodec': 'aac',
            'pix_fmt': 'yuv420p',
            'ac': 2,
            'ar': '48000',
            'movflags': '+faststart'
        }
        
        if compress:
            cpu_params.update({
                'preset': 'medium',
                'crf': '28',
                'b:a': '96k'
            })
        else:
            cpu_params.update({
                'preset': 'veryfast',
                'crf': '23'
            })
        
        # Convert with CPU
        stream = ffmpeg.input(webm_temp.name)
        stream = ffmpeg.output(stream, output_path, **cpu_params)
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        # Read result
        with open(output_path, "rb") as f:
            result_content = f.read()
        
        logger.info(f"CPU conversion completed, output size: {len(result_content)} bytes")
        return result_content
        
    finally:
        # Cleanup
        try:
            if os.path.exists(webm_temp.name):
                os.unlink(webm_temp.name)
            if os.path.exists(output_path):
                os.unlink(output_path)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup error: {cleanup_error}")

@app.function(
    image=cpu_image,
    timeout=2000,
    cpu=1.0,
    scaledown_window=2
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI
    
    web_app = FastAPI()
    
    # Add CORS middleware
    web_app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https://.*\.singmesong\.com|https://singmesong\.com|http://localhost:3000|https://localhost:3000",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @web_app.post("/convert")
    async def convert_webm_to_mp4_endpoint(video: UploadFile, compress: bool = False, request: Request = None):
        return await convert_webm_to_mp4(video, compress, request)
    
    return web_app

async def convert_webm_to_mp4(video: UploadFile, compress: bool = False, request: Request | None = None):
    import logging
    """Convert a WebM file to MP4 format with GPU-first, CPU fallback architecture."""
    # Configure logging for the Modal function
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting WebM to MP4 conversion orchestration")
    
    try:
        # Read the uploaded webm content
        webm_content = await video.read()
        if len(webm_content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        logger.info(f"Received {len(webm_content)} bytes for conversion")
        
        # First try GPU conversion
        try:
            logger.info("Attempting GPU conversion with T4 NVENC...")
            content = gpu_convert.remote(webm_content, compress)
            logger.info("GPU conversion completed successfully")
            
        except Exception as gpu_error:
            logger.warning(f"GPU conversion failed: {str(gpu_error)}")
            logger.info("Falling back to CPU-only container...")
            
            # Fallback to CPU conversion
            try:
                content = cpu_fallback_convert.remote(webm_content, compress)
                logger.info("CPU fallback conversion completed successfully")
            except Exception as cpu_error:
                error_message = f"Both GPU and CPU conversion failed. GPU: {str(gpu_error)}, CPU: {str(cpu_error)}"
                logger.error(error_message)
                raise HTTPException(status_code=500, detail=error_message)
        
        logger.info(f"Conversion completed, output size: {len(content)} bytes")

        total = len(content)
        headers = {
            "Content-Disposition": "attachment; filename=converted.mp4",
            "Accept-Ranges": "bytes",
        }

        # Handle HTTP Range header for partial content
        range_header = None
        if request is not None:
            range_header = request.headers.get("range") or request.headers.get("Range")

        if range_header:
            try:
                # Expected formats:
                # bytes=start-end
                # bytes=start-
                # bytes=-suffix_length
                units, _, ranges = range_header.partition("=")
                if units.strip().lower() != "bytes" or not ranges:
                    raise ValueError("Invalid Range units")

                # Only support a single range
                range_spec = ranges.split(",")[0].strip()

                if range_spec.startswith("-"):
                    # suffix range
                    suffix_len = int(range_spec[1:])
                    if suffix_len <= 0:
                        raise ValueError("Invalid suffix length")
                    start = max(total - suffix_len, 0)
                    end = total - 1
                else:
                    start_str, _, end_str = range_spec.partition("-")
                    if not start_str.isdigit():
                        raise ValueError("Invalid start")
                    start = int(start_str)
                    end = total - 1 if end_str == "" else int(end_str)

                if start < 0 or end < start or start >= total:
                    # Unsatisfiable range
                    return Response(
                        status_code=416,
                        media_type="video/mp4",
                        headers={
                            **headers,
                            "Content-Range": f"bytes */{total}",
                            "Content-Length": "0",
                        },
                        content=b"",
                    )

                end = min(end, total - 1)
                body = content[start:end + 1]
                headers.update({
                    "Content-Range": f"bytes {start}-{end}/{total}",
                    "Content-Length": str(len(body)),
                })

                return Response(
                    content=body,
                    media_type="video/mp4",
                    status_code=206,
                    headers=headers,
                )
            except Exception as _:
                # Malformed Range header -> ignore and send full content
                pass

        # No (valid) range: return full content
        headers["Content-Length"] = str(total)
        return Response(
            content=content,
            media_type="video/mp4",
            headers=headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during conversion orchestration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# CLI interface
cli = typer.Typer()

@cli.command()
def deploy():
    """Deploy the FastAPI app as a service."""
    modal.deploy(app)

@cli.command()
def serve():
    """Serve the FastAPI app locally."""
    modal.serve(app)

if __name__ == "__main__":
    cli() 