import modal
import os
import typer
import subprocess

from fastapi import HTTPException, UploadFile, Response
from starlette.middleware.cors import CORSMiddleware

# Create Modal app
app = modal.App("webm-to-mp4")

# Create the image with required dependencies
image = (
    modal.Image.debian_slim()
    .apt_install(["ffmpeg"])
    .pip_install(["ffmpeg-python", "fastapi[standard]", "typer"])
)

@app.function(
    image=image,
    timeout=2000,
    gpu="T4"
)
@modal.fastapi_endpoint(method="POST", docs=True)
async def convert_webm_to_mp4(video: UploadFile, compress: bool = False):
    import logging
    import tempfile
    import ffmpeg
    """Convert a WebM file to MP4 format with optional compression."""
    # Configure logging for the Modal function
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Check NVIDIA driver status
    try:
        nvidia_smi = subprocess.check_output(['nvidia-smi'], stderr=subprocess.STDOUT).decode()
        logger.info(f"NVIDIA driver info:\n{nvidia_smi}")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Could not get NVIDIA driver info: {e.output.decode()}")
    except FileNotFoundError:
        logger.warning("nvidia-smi not found, GPU acceleration may not be available")
    
    logger.info("Starting WebM to MP4 conversion")
    
    # Create temporary files for input and output
    webm_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    
    try:
        # Save the uploaded webm to a temporary file
        content = await video.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        
        webm_temp.write(content)
        webm_temp.close()
        logger.info(f"Saved {len(content)} bytes to temporary file")
        
        # Verify the input file
        try:
            probe = ffmpeg.probe(webm_temp.name)
            video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if not video_info:
                raise HTTPException(status_code=400, detail="No video stream found in input file")
            logger.info(f"Input video codec: {video_info.get('codec_name')}")
        except ffmpeg.Error as e:
            raise HTTPException(status_code=400, detail=f"Invalid input file: {str(e)}")

        # Set encoding parameters
        encoding_params = {
            'vcodec': 'h264_nvenc',
            'acodec': 'aac',
            'pix_fmt': 'yuv420p',
            'preset': 'medium',    # Use standard preset
            'rc': 'vbr',          # Simple variable bitrate mode
            'b:v': '2M',          # Video bitrate
            'maxrate': '4M',
            'bufsize': '8M',
            'ac': 2,              # Audio channels
            'ar': '48000',        # Audio sample rate
            'movflags': '+faststart'
        }

        if compress:
            logger.info("Using compressed settings")
            encoding_params.update({
                'b:v': '800k',    # Lower video bitrate for compression
                'maxrate': '1M',
                'bufsize': '2M',
                'b:a': '96k',     # Lower audio bitrate
            })
        else:
            logger.info("Using standard quality settings")
            encoding_params.update({
                'b:v': '2M',      # Higher video bitrate for quality
                'maxrate': '4M',
                'bufsize': '8M'
            })

        # Convert WebM to MP4
        logger.info("Starting FFmpeg conversion")
        stream = ffmpeg.input(webm_temp.name)
        stream = ffmpeg.output(stream, output_path, **encoding_params)
        
        try:
            # First try with GPU encoding
            logger.info("Attempting GPU encoding with NVENC...")
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            logger.warning(f"GPU encoding failed with error: {e.stderr.decode()}")
            logger.info("Falling back to CPU encoding...")
            
            # Fallback to CPU encoding with compatible parameters
            cpu_params = encoding_params.copy()
            cpu_params['vcodec'] = 'libx264'
            # Remove NVENC-specific parameters
            for key in ['rc', 'spatial-aq', 'temporal-aq']:
                cpu_params.pop(key, None)
            
            if not compress:
                cpu_params.update({
                    'preset': 'veryfast',
                    'crf': '23'
                })
            else:
                cpu_params.update({
                    'preset': 'medium',
                    'crf': '28'
                })
            
            # Try CPU encoding
            stream = ffmpeg.input(webm_temp.name)
            stream = ffmpeg.output(stream, output_path, **cpu_params)
            try:
                ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
                logger.info("CPU encoding completed successfully")
            except ffmpeg.Error as e:
                error_message = f"Both GPU and CPU encoding failed. FFmpeg error: {e.stderr.decode()}"
                logger.error(error_message)
                raise HTTPException(status_code=500, detail=error_message)
        
        # Read the converted file
        with open(output_path, "rb") as f:
            content = f.read()
        
        return Response(
            content=content,
            media_type="video/mp4",
            headers={
                "Content-Disposition": "attachment; filename=converted.mp4"
            }
        )

    except Exception as e:
        logger.error(f"Error during conversion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Clean up temporary files
        if os.path.exists(webm_temp.name):
            os.unlink(webm_temp.name)
        if os.path.exists(output_path):
            os.unlink(output_path)

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