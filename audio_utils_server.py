import litserve as ls
import os
import tempfile
from fastapi import Response, HTTPException
import ffmpeg
from starlette.middleware.cors import CORSMiddleware
import requests  # Add new import at top

class MP3DurationAPI(ls.LitAPI):
    def setup(self, device):
        pass

    def decode_request(self, request):
        mp3_url = request.get("url")
        if not mp3_url:
            raise HTTPException(status_code=400, detail="No MP3 URL provided")
        return {"url": mp3_url}

    def predict(self, input_data):
        mp3_url = input_data["url"]
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        
        try:
            # Download the MP3 file
            response = requests.get(mp3_url, timeout=10)
            response.raise_for_status()
            
            temp_file.write(response.content)
            temp_file.close()
            
            # Probe the audio file
            probe = ffmpeg.probe(temp_file.name)
            duration = float(probe['format']['duration'])
            
            return {"duration": duration}
            
        except requests.RequestException as e:
            raise HTTPException(status_code=400, detail=f"Failed to download MP3: {str(e)}")
        except ffmpeg.Error as e:
            raise HTTPException(status_code=400, detail=f"Invalid audio file: {str(e)}")
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

    def encode_response(self, output):
        return {"duration": output["duration"]}

# Add new server instance for the MP3 API
if __name__ == "__main__":
    # Define the CORS settings
    cors_middleware = (
        CORSMiddleware, 
        {
            "allow_origins": ["https://*.singmesong.com", "http://localhost:3000"],
            "allow_methods": ["GET", "POST"],
            "allow_headers": ["*"],
        }
    )
    # Add this for the MP3 duration API (run on different port)
    mp3_server = ls.LitServer(MP3DurationAPI(), middlewares=[cors_middleware])
    mp3_server.run(port=8883)