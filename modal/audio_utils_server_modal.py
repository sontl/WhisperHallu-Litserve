import modal
import tempfile
import os
import requests
import logging
import typer
from typing import Optional
from pydantic import BaseModel

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
    .apt_install(["ffmpeg", "libsm6", "libxext6", "libxrender-dev", "libglib2.0-0"])  # Install FFmpeg binaries and OpenCV dependencies
    .pip_install(["ffmpeg-python", "requests", "fastapi[standard]", "typer", "opencv-python-headless"])
)

# Request models
class DurationRequest(BaseModel):
    url: str

class ThumbnailRequest(BaseModel):
    url: str
    timestamp: float = 1.0

class TrimRequest(BaseModel):
    url: str
    start: Optional[float] = None
    end: Optional[float] = None

class LastFrameRequest(BaseModel):
    url: str

@app.function(image=image, scaledown_window=2)
@modal.fastapi_endpoint(method="POST", docs=True)
def get_duration(request: DurationRequest):
    """Get the duration of an MP3 file from a URL."""
    url = request.url
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

@app.function(image=image, scaledown_window=2)
@modal.fastapi_endpoint(method="POST", docs=True)
def extract_thumbnail(request: ThumbnailRequest):
    """Extract a thumbnail from a video URL at the specified timestamp (default: 1 second)."""
    url = request.url
    timestamp = request.timestamp
    logger.info(f"Extracting thumbnail from video URL: {url} at {timestamp}s")
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_thumb = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    logger.info(f"Created temporary files: video={temp_video.name}, thumbnail={temp_thumb.name}")
    import ffmpeg
    from fastapi.responses import FileResponse
    
    try:
        # Download the video file
        logger.info("Downloading video file...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully downloaded {len(response.content)} bytes")
        
        temp_video.write(response.content)
        temp_video.close()
        logger.info("Saved video to temporary file")
        
        # Extract thumbnail at specified timestamp
        logger.info(f"Extracting frame at {timestamp}s...")
        (
            ffmpeg
            .input(temp_video.name, ss=timestamp)
            .output(temp_thumb.name, vframes=1, format='image2', vcodec='mjpeg')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info("Successfully extracted thumbnail")
        
        # Read the thumbnail file
        with open(temp_thumb.name, 'rb') as f:
            thumbnail_data = f.read()
        
        logger.info(f"Thumbnail size: {len(thumbnail_data)} bytes")
        
        # Return as base64 encoded string
        import base64
        thumbnail_base64 = base64.b64encode(thumbnail_data).decode('utf-8')
        
        return {
            "thumbnail": thumbnail_base64,
            "format": "jpeg",
            "timestamp": timestamp
        }
        
    except requests.RequestException as e:
        logger.error(f"Failed to download video: {str(e)}")
        raise modal.Error(f"Failed to download video: {str(e)}")
    except ffmpeg.Error as e:
        logger.error(f"Failed to extract thumbnail: {str(e)}")
        raise modal.Error(f"Failed to extract thumbnail: {str(e)}")
    finally:
        if os.path.exists(temp_video.name):
            os.unlink(temp_video.name)
            logger.info(f"Cleaned up temporary video file: {temp_video.name}")
        if os.path.exists(temp_thumb.name):
            os.unlink(temp_thumb.name)
            logger.info(f"Cleaned up temporary thumbnail file: {temp_thumb.name}")

@app.function(image=image, scaledown_window=2)
@modal.fastapi_endpoint(method="POST", docs=True)
def trim_video(request: TrimRequest):
    """Trim a video from a URL. If start is None, starts from beginning. If end is None, goes to end of video."""
    url = request.url
    start = request.start
    end = request.end
    logger.info(f"Trimming video from URL: {url}, start={start}, end={end}")
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    logger.info(f"Created temporary files: input={temp_input.name}, output={temp_output.name}")
    import ffmpeg
    
    try:
        # Download the video file
        logger.info("Downloading video file...")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        logger.info(f"Successfully downloaded {len(response.content)} bytes")
        
        temp_input.write(response.content)
        temp_input.close()
        logger.info("Saved video to temporary file")
        
        # Build FFmpeg command
        input_kwargs = {}
        output_kwargs = {'c': 'copy'}  # Use stream copy for speed
        
        if start is not None:
            input_kwargs['ss'] = start
            logger.info(f"Setting start time: {start}s")
        
        if end is not None:
            if start is not None:
                output_kwargs['t'] = end - start
                logger.info(f"Setting duration: {end - start}s")
            else:
                output_kwargs['to'] = end
                logger.info(f"Setting end time: {end}s")
        
        # Trim the video
        logger.info("Trimming video...")
        (
            ffmpeg
            .input(temp_input.name, **input_kwargs)
            .output(temp_output.name, **output_kwargs)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info("Successfully trimmed video")
        
        # Read the trimmed video
        with open(temp_output.name, 'rb') as f:
            video_data = f.read()
        
        logger.info(f"Trimmed video size: {len(video_data)} bytes")
        
        # Return as base64 encoded string
        import base64
        video_base64 = base64.b64encode(video_data).decode('utf-8')
        
        return {
            "video": video_base64,
            "format": "mp4",
            "start": start if start is not None else 0,
            "end": end
        }
        
    except requests.RequestException as e:
        logger.error(f"Failed to download video: {str(e)}")
        raise modal.Error(f"Failed to download video: {str(e)}")
    except ffmpeg.Error as e:
        logger.error(f"Failed to trim video: {str(e)}")
        raise modal.Error(f"Failed to trim video: {str(e)}")
    finally:
        if os.path.exists(temp_input.name):
            os.unlink(temp_input.name)
            logger.info(f"Cleaned up temporary input file: {temp_input.name}")
        if os.path.exists(temp_output.name):
            os.unlink(temp_output.name)
            logger.info(f"Cleaned up temporary output file: {temp_output.name}")

@app.function(image=image, scaledown_window=2)
@modal.fastapi_endpoint(method="POST", docs=True)
def extract_last_frame(request: LastFrameRequest):
    """Extract the last frame from a video URL and return as an image."""
    url = request.url
    logger.info(f"Extracting last frame from video URL: {url}")
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    logger.info(f"Created temporary file: video={temp_video.name}")
    import cv2
    import base64
    import numpy as np

    try:
        # Download the video file
        logger.info("Downloading video file...")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        logger.info(f"Successfully downloaded {len(response.content)} bytes")

        temp_video.write(response.content)
        temp_video.close()
        logger.info("Saved video to temporary file")

        # Open the video file with OpenCV to get the exact last frame
        logger.info("Opening video with OpenCV to get last frame...")
        cap = cv2.VideoCapture(temp_video.name)

        # Get total number of frames
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(f"Total frames in video: {total_frames}")

        if total_frames <= 0:
            raise modal.Error("Video has no frames")

        # Set position to last frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)

        # Read the last frame
        ret, frame = cap.read()

        # Release the video capture object
        cap.release()

        if not ret or frame is None:
            raise modal.Error("Failed to read the last frame from video")

        logger.info("Successfully extracted last frame using OpenCV")

        # Encode frame as JPEG to get bytes
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]  # 90% quality
        result, frame_bytes = cv2.imencode('.jpg', frame, encode_param)

        if not result:
            raise modal.Error("Failed to encode the last frame as JPEG")

        frame_data = frame_bytes.tobytes()
        logger.info(f"Last frame size: {len(frame_data)} bytes")

        # Return as base64 encoded string
        frame_base64 = base64.b64encode(frame_data).decode('utf-8')

        return {
            "frame": frame_base64,
            "format": "jpeg",
            "frame_number": total_frames - 1,
            "total_frames": total_frames
        }

    except requests.RequestException as e:
        logger.error(f"Failed to download video: {str(e)}")
        raise modal.Error(f"Failed to download video: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to extract last frame: {str(e)}")
        raise modal.Error(f"Failed to extract last frame: {str(e)}")
    finally:
        if os.path.exists(temp_video.name):
            os.unlink(temp_video.name)
            logger.info(f"Cleaned up temporary video file: {temp_video.name}")

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
