import modal
import tempfile
from fastapi import Response, HTTPException
import ffmpeg
from starlette.middleware.cors import CORSMiddleware
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = modal.App("audio-utils")
image = modal.Image.debian_slim().pip_install(["ffmpeg-python", "requests"])

@app.cls(image=image)
class MP3DurationAPI:
    def setup(self, device):
        logger.info("Setting up MP3DurationAPI")
        pass

    def decode_request(self, request):
        logger.info("Decoding request")
        mp3_url = request.get("url")
        if not mp3_url:
            logger.error("No MP3 URL provided in request")
            raise HTTPException(status_code=400, detail="No MP3 URL provided")
        logger.info(f"Received request for URL: {mp3_url}")
        return {"url": mp3_url}

    def predict(self, input_data):
        mp3_url = input_data["url"]
        logger.info(f"Processing MP3 from URL: {mp3_url}")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        logger.info(f"Created temporary file: {temp_file.name}")
        
        try:
            # Download the MP3 file
            logger.info("Downloading MP3 file...")
            response = requests.get(mp3_url, timeout=10)
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
            raise HTTPException(status_code=400, detail=f"Failed to download MP3: {str(e)}")
        except ffmpeg.Error as e:
            logger.error(f"Invalid audio file: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid audio file: {str(e)}")
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
                logger.info(f"Cleaned up temporary file: {temp_file.name}")

    def encode_response(self, output):
        logger.info(f"Encoding response with duration: {output['duration']}")
        return {"duration": output["duration"]}

@app.function()
@modal.web_endpoint(method="POST")
def predict(url: str):
    return MP3DurationAPI().predict({"url": url})
