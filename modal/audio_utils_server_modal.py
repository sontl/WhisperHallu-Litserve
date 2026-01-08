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
    .apt_install(["ffmpeg", "libsm6", "libxext6", "libxrender-dev", "libglib2.0-0"])
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

class TrimAudioRequest(BaseModel):
    url: str
    start: Optional[float] = None
    end: Optional[float] = None

@app.cls(
    image=image,
    min_containers=0,
    enable_memory_snapshot=True,
    scaledown_window=10,
    timeout=300,
)
class AudioUtilsService:
    @modal.enter(snap=True)
    def initialize(self):
        """Initialize and warm up dependencies"""
        import ffmpeg
        import cv2
        logger.info("Initializing AudioUtilsService with memory snapshot...")
        logger.info("FFmpeg and OpenCV loaded and ready for snapshot")
    
    @modal.method()
    def get_audio_duration(self, url: str):
        """Get the duration of an MP3 file from a URL."""
        import ffmpeg
        
        logger.info(f"Processing MP3 from URL: {url}")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        logger.info(f"Created temporary file: {temp_file.name}")
        
        try:
            logger.info("Downloading MP3 file...")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            logger.info(f"Successfully downloaded {len(response.content)} bytes")
            
            temp_file.write(response.content)
            temp_file.close()
            logger.info("Saved MP3 to temporary file")
            
            logger.info("Probing audio file...")
            probe = ffmpeg.probe(temp_file.name)
            duration = float(probe['format']['duration'])
            logger.info(f"Audio duration: {duration} seconds")
            
            return {"duration": duration}
            
        except requests.RequestException as e:
            logger.error(f"Failed to download MP3: {str(e)}")
            raise RuntimeError(f"Failed to download MP3: {str(e)}")
        except Exception as e:
            logger.error(f"Invalid audio file: {str(e)}")
            raise RuntimeError(f"Invalid audio file: {str(e)}")
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
                logger.info(f"Cleaned up temporary file: {temp_file.name}")
    
    @modal.method()
    def extract_video_thumbnail(self, url: str, timestamp: float = 1.0):
        """Extract a thumbnail from a video URL at the specified timestamp."""
        import ffmpeg
        import base64
        import time
        
        logger.info(f"Extracting thumbnail from video URL: {url} at {timestamp}s")
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_thumb = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        logger.info(f"Created temporary files: video={temp_video.name}, thumbnail={temp_thumb.name}")
        
        try:
            # Retry logic for video download
            max_retries = 3
            retry_delay = 2  # seconds between retries
            download_timeout = 60  # increased timeout
            last_error = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"Downloading video file... (attempt {attempt}/{max_retries})")
                    response = requests.get(url, timeout=download_timeout)
                    response.raise_for_status()
                    logger.info(f"Successfully downloaded {len(response.content)} bytes")
                    break  # Success, exit retry loop
                except requests.RequestException as e:
                    last_error = e
                    logger.warning(f"Download attempt {attempt}/{max_retries} failed: {str(e)}")
                    if attempt < max_retries:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"All {max_retries} download attempts failed")
                        raise RuntimeError(f"Failed to download video after {max_retries} attempts: {str(last_error)}")
            
            temp_video.write(response.content)
            temp_video.close()
            logger.info("Saved video to temporary file")
            
            logger.info(f"Extracting frame at {timestamp}s...")
            (
                ffmpeg
                .input(temp_video.name, ss=timestamp)
                .output(temp_thumb.name, vframes=1, format='image2', vcodec='mjpeg')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            logger.info("Successfully extracted thumbnail")
            
            with open(temp_thumb.name, 'rb') as f:
                thumbnail_data = f.read()
            
            logger.info(f"Thumbnail size: {len(thumbnail_data)} bytes")
            
            thumbnail_base64 = base64.b64encode(thumbnail_data).decode('utf-8')
            
            return {
                "thumbnail": thumbnail_base64,
                "format": "jpeg",
                "timestamp": timestamp
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to download video: {str(e)}")
            raise RuntimeError(f"Failed to download video: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to extract thumbnail: {str(e)}")
            raise RuntimeError(f"Failed to extract thumbnail: {str(e)}")
        finally:
            if os.path.exists(temp_video.name):
                os.unlink(temp_video.name)
                logger.info(f"Cleaned up temporary video file: {temp_video.name}")
            if os.path.exists(temp_thumb.name):
                os.unlink(temp_thumb.name)
                logger.info(f"Cleaned up temporary thumbnail file: {temp_thumb.name}")
    
    @modal.method()
    def trim_video_file(self, url: str, start: Optional[float] = None, end: Optional[float] = None):
        """Trim a video from a URL."""
        import ffmpeg
        import base64
        
        logger.info(f"Trimming video from URL: {url}, start={start}, end={end}")
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        logger.info(f"Created temporary files: input={temp_input.name}, output={temp_output.name}")
        
        try:
            logger.info("Downloading video file...")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            logger.info(f"Successfully downloaded {len(response.content)} bytes")
            
            temp_input.write(response.content)
            temp_input.close()
            logger.info("Saved video to temporary file")
            
            input_kwargs = {}
            output_kwargs = {'c': 'copy'}
            
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
            
            logger.info("Trimming video...")
            (
                ffmpeg
                .input(temp_input.name, **input_kwargs)
                .output(temp_output.name, **output_kwargs)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            logger.info("Successfully trimmed video")
            
            with open(temp_output.name, 'rb') as f:
                video_data = f.read()
            
            logger.info(f"Trimmed video size: {len(video_data)} bytes")
            
            video_base64 = base64.b64encode(video_data).decode('utf-8')
            
            return {
                "video": video_base64,
                "format": "mp4",
                "start": start if start is not None else 0,
                "end": end
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to download video: {str(e)}")
            raise RuntimeError(f"Failed to download video: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to trim video: {str(e)}")
            raise RuntimeError(f"Failed to trim video: {str(e)}")
        finally:
            if os.path.exists(temp_input.name):
                os.unlink(temp_input.name)
                logger.info(f"Cleaned up temporary input file: {temp_input.name}")
            if os.path.exists(temp_output.name):
                os.unlink(temp_output.name)
                logger.info(f"Cleaned up temporary output file: {temp_output.name}")
    
    @modal.method()
    def trim_audio_file(self, url: str, start: Optional[float] = None, end: Optional[float] = None):
        """Trim an audio file from a URL."""
        import ffmpeg
        import base64
        
        logger.info(f"Trimming audio from URL: {url}, start={start}, end={end}")
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        logger.info(f"Created temporary files: input={temp_input.name}, output={temp_output.name}")
        
        try:
            logger.info("Downloading audio file...")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            logger.info(f"Successfully downloaded {len(response.content)} bytes")
            
            temp_input.write(response.content)
            temp_input.close()
            logger.info("Saved audio to temporary file")
            
            # Probe input file to get format info
            try:
                probe = ffmpeg.probe(temp_input.name)
                input_format = probe.get('format', {}).get('format_name', 'unknown')
                logger.info(f"Input audio format: {input_format}")
            except Exception as probe_err:
                logger.warning(f"Could not probe input file: {probe_err}")
            
            input_kwargs = {}
            # Re-encode instead of stream copy for better compatibility
            output_kwargs = {'acodec': 'libmp3lame', 'audio_bitrate': '192k'}
            
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
            
            logger.info("Trimming audio...")
            try:
                (
                    ffmpeg
                    .input(temp_input.name, **input_kwargs)
                    .output(temp_output.name, **output_kwargs)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except ffmpeg.Error as ffmpeg_err:
                stderr_output = ffmpeg_err.stderr.decode('utf-8') if ffmpeg_err.stderr else 'No stderr'
                logger.error(f"FFmpeg stderr: {stderr_output}")
                raise RuntimeError(f"FFmpeg error: {stderr_output}")
            
            logger.info("Successfully trimmed audio")
            
            with open(temp_output.name, 'rb') as f:
                audio_data = f.read()
            
            logger.info(f"Trimmed audio size: {len(audio_data)} bytes")
            
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            return {
                "audio": audio_base64,
                "format": "mp3",
                "start": start if start is not None else 0,
                "end": end
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to download audio: {str(e)}")
            raise RuntimeError(f"Failed to download audio: {str(e)}")
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Failed to trim audio: {str(e)}")
            raise RuntimeError(f"Failed to trim audio: {str(e)}")
        finally:
            if os.path.exists(temp_input.name):
                os.unlink(temp_input.name)
                logger.info(f"Cleaned up temporary input file: {temp_input.name}")
            if os.path.exists(temp_output.name):
                os.unlink(temp_output.name)
                logger.info(f"Cleaned up temporary output file: {temp_output.name}")
    
    @modal.method()
    def extract_video_last_frame(self, url: str):
        """Extract the last frame from a video URL."""
        import cv2
        import base64
        
        logger.info(f"Extracting last frame from video URL: {url}")
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        logger.info(f"Created temporary file: video={temp_video.name}")
        
        try:
            logger.info("Downloading video file...")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            logger.info(f"Successfully downloaded {len(response.content)} bytes")
            
            temp_video.write(response.content)
            temp_video.close()
            logger.info("Saved video to temporary file")
            
            logger.info("Opening video with OpenCV to get last frame...")
            cap = cv2.VideoCapture(temp_video.name)
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            logger.info(f"Total frames in video: {total_frames}")
            
            if total_frames <= 0:
                raise RuntimeError("Video has no frames")
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                raise RuntimeError("Failed to read the last frame from video")
            
            logger.info("Successfully extracted last frame using OpenCV")
            
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
            result, frame_bytes = cv2.imencode('.jpg', frame, encode_param)
            
            if not result:
                raise RuntimeError("Failed to encode the last frame as JPEG")
            
            frame_data = frame_bytes.tobytes()
            logger.info(f"Last frame size: {len(frame_data)} bytes")
            
            frame_base64 = base64.b64encode(frame_data).decode('utf-8')
            
            return {
                "frame": frame_base64,
                "format": "jpeg",
                "frame_number": total_frames - 1,
                "total_frames": total_frames
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to download video: {str(e)}")
            raise RuntimeError(f"Failed to download video: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to extract last frame: {str(e)}")
            raise RuntimeError(f"Failed to extract last frame: {str(e)}")
        finally:
            if os.path.exists(temp_video.name):
                os.unlink(temp_video.name)
                logger.info(f"Cleaned up temporary video file: {temp_video.name}")

# FastAPI endpoints
@app.function(image=image, timeout=300)
@modal.fastapi_endpoint(method="POST", docs=True)
async def get_duration(request: DurationRequest):
    """Get the duration of an MP3 file from a URL."""
    try:
        service = AudioUtilsService()
        result = await service.get_audio_duration.remote.aio(request.url)
        return result
    except Exception as e:
        raise modal.Error(str(e))

@app.function(image=image, timeout=300)
@modal.fastapi_endpoint(method="POST", docs=True)
async def extract_thumbnail(request: ThumbnailRequest):
    """Extract a thumbnail from a video URL at the specified timestamp."""
    try:
        service = AudioUtilsService()
        result = await service.extract_video_thumbnail.remote.aio(request.url, request.timestamp)
        return result
    except Exception as e:
        raise modal.Error(str(e))

@app.function(image=image, timeout=300)
@modal.fastapi_endpoint(method="POST", docs=True)
async def trim_video(request: TrimRequest):
    """Trim a video from a URL."""
    try:
        service = AudioUtilsService()
        result = await service.trim_video_file.remote.aio(request.url, request.start, request.end)
        return result
    except Exception as e:
        raise modal.Error(str(e))

@app.function(image=image, timeout=300)
@modal.fastapi_endpoint(method="POST", docs=True)
async def trim_audio(request: TrimAudioRequest):
    """Trim an audio file from a URL."""
    try:
        service = AudioUtilsService()
        result = await service.trim_audio_file.remote.aio(request.url, request.start, request.end)
        return result
    except Exception as e:
        raise modal.Error(str(e))

@app.function(image=image, timeout=300)
@modal.fastapi_endpoint(method="POST", docs=True)
async def extract_last_frame(request: LastFrameRequest):
    """Extract the last frame from a video URL."""
    try:
        service = AudioUtilsService()
        result = await service.extract_video_last_frame.remote.aio(request.url)
        return result
    except Exception as e:
        raise modal.Error(str(e))

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
