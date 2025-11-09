import modal
import tempfile
import os
import requests
import logging
import typer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Modal app
app = modal.App("audio-utils")

# Create the image with required dependencies
image = (
    modal.Image.debian_slim()
    .apt_install(["ffmpeg"])  # Install FFmpeg binaries
    .pip_install(["ffmpeg-python", "requests", "fastapi[standard]", "typer"])
)

@app.function(image=image, scaledown_window=2)
@modal.fastapi_endpoint(method="POST", docs=True)
def get_duration(url: str):
    """Get the duration of an MP3 file from a URL."""
    logger.info(f"Processing MP3 from URL: {url}")
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    logger.info(f"Created temporary file: {temp_file.name}")
    import ffmpeg
    
    try:
        # Download the MP3 file
        logger.info("Downloading MP3 file...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        logger.info(f"Successfully downloaded {len(response.content)} bytes")
        
        temp_file.write(response.content)
        temp_file.close()
        logger.info("Saved MP3 to temporary file")
        
        # Probe the audio file
        logger.info("Probing audio file...")
        probe = ffmpeg.probe(temp_file.name)
        duration = float(probe['format']['duration'])
        logger.info(f"Audio duration: {duration} seconds")
        
        return {"duration": duration}
        
    except requests.RequestException as e:
        logger.error(f"Failed to download MP3: {str(e)}")
        raise modal.Error(f"Failed to download MP3: {str(e)}")
    except ffmpeg.Error as e:
        logger.error(f"Invalid audio file: {str(e)}")
        raise modal.Error(f"Invalid audio file: {str(e)}")
    finally:
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
            logger.info(f"Cleaned up temporary file: {temp_file.name}")

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
