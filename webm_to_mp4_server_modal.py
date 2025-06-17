import modal
import os
import typer

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

@app.function(image=image)
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
            'vcodec': 'libx264',
            'acodec': 'aac',
            'pix_fmt': 'yuv420p',
            'profile': 'high',
            'level': '4.0',
            'movflags': '+faststart+rtphint',
            'strict': 'strict',
            'brand': 'mp42',
            'ac': 2,
            'ar': '48000',
            'max_muxing_queue_size': '1024'
        }

        if compress:
            logger.info("Using compressed settings")
            encoding_params.update({
                'preset': 'slower',
                'crf': '28',
                'video_bitrate': '800k',
                'audio_bitrate': '96k',
                'g': '60',
            })
        else:
            logger.info("Using standard quality settings")
            encoding_params.update({
                'preset': 'medium',
                'video_bitrate': '2M',
                'g': '30',
                'force_key_frames': 'expr:gte(t,n_forced*2)'
            })

        # Convert WebM to MP4
        logger.info("Starting FFmpeg conversion")
        stream = ffmpeg.input(webm_temp.name)
        stream = ffmpeg.output(stream, output_path, **encoding_params)
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
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