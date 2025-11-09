import litserve as ls
import os
import tempfile
from fastapi import Response, HTTPException
from pydub import AudioSegment
import torch
from transcribeHallu import loadModel, transcribePrompt
import json
import requests
import logging
from datetime import datetime

# Set up logging with more detailed format
log_dir = "./logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"whisperhallu_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WhisperHalluAPI(ls.LitAPI):
    def setup(self, device):
        logger.info("Starting WhisperHalluAPI setup...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        self.model_size = "medium"
        try:
            loadModel("0", modelSize=self.model_size)
            logger.info(f"Model loaded successfully: {self.model_size}")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}", exc_info=True)
            raise

    def decode_request(self, request):
        try:
            logger.info("Starting request decoding...")
            # Get the URL from the request, if present
            url = request.get("url")
            lng = request.get("lng", "en")
            lng_input = request.get("lng_input", "en")

            logger.info(f"Request parameters - URL: {url if url else 'None'}, Language: {lng}, Input Language: {lng_input}")

            if url:
                logger.info(f"Processing URL: {url}")
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    logger.info(f"Successfully downloaded content from URL, status code: {response.status_code}")
                    
                    # Create a temporary file with the same extension as the URL
                    file_ext = os.path.splitext(url)[1].lower()
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
                    logger.info(f"Created temporary file: {temp_file.name}")
                    
                    with open(temp_file.name, "wb") as f:
                        f.write(response.content)
                    
                    # Handle both MP3 and WAV files
                    if file_ext == '.mp3':
                        logger.info("Converting MP3 to audio segment")
                        audio = AudioSegment.from_mp3(temp_file.name)
                    elif file_ext == '.wav':
                        logger.info("Loading WAV audio segment")
                        audio = AudioSegment.from_wav(temp_file.name)
                    else:
                        logger.error(f"Unsupported file format: {file_ext}")
                        raise HTTPException(status_code=400, detail="Unsupported file format. Only .mp3 and .wav are supported.")
                    
                    wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                    logger.info(f"Exporting to WAV file: {wav_file.name}")
                    audio.export(wav_file.name, format="wav")
                    
                    os.unlink(temp_file.name)
                    logger.info("Successfully processed URL audio")
                    return {"file_path": wav_file.name, "lng": lng, "lng_input": lng_input}
                except Exception as e:
                    logger.error(f"Error processing URL: {str(e)}", exc_info=True)
                    raise HTTPException(status_code=400, detail=f"Error downloading or processing file from URL: {str(e)}")

            # If no URL, process the uploaded file
            logger.info("Processing uploaded file...")
            audio_file = request["content"].file
            if audio_file is None:
                logger.error("No audio file or URL found in request")
                raise HTTPException(status_code=400, detail="No audio file or URL found in the request.")

            # Get the file extension from the filename
            original_filename = request["content"].filename
            file_ext = os.path.splitext(original_filename)[1].lower()
            logger.info(f"Processing uploaded file: {original_filename} with extension {file_ext}")
            
            # Create a temporary file with the original extension
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
            logger.info(f"Created temporary file: {temp_file.name}")
            
            audio_data = audio_file.read()
            with open(temp_file.name, "wb") as f:
                f.write(audio_data)
            
            try:
                # Handle both MP3 and WAV files
                if file_ext == '.mp3':
                    logger.info("Converting MP3 to audio segment")
                    audio = AudioSegment.from_mp3(temp_file.name)
                elif file_ext == '.wav':
                    logger.info("Loading WAV audio segment")
                    audio = AudioSegment.from_wav(temp_file.name)
                else:
                    logger.error(f"Unsupported file format: {file_ext}")
                    raise HTTPException(status_code=400, detail="Unsupported file format. Only .mp3 and .wav are supported.")
                
                wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                logger.info(f"Exporting to WAV file: {wav_file.name}")
                audio.export(wav_file.name, format="wav")
                
                os.unlink(temp_file.name)
                logger.info("Successfully processed uploaded audio")
                return {"file_path": wav_file.name, "lng": lng, "lng_input": lng_input}
            except Exception as e:
                logger.error(f"Error processing audio file: {str(e)}", exc_info=True)
                raise HTTPException(status_code=400, detail=f"Error processing audio file: {str(e)}")
        except Exception as e:
            logger.error(f"Error in decode_request: {str(e)}", exc_info=True)
            raise

    def predict(self, request_data):
        try:
            file_path = request_data["file_path"]
            lng_input = request_data.get("lng_input", "en")
            lng = lng_input  # fixed this because we use AI to translate later after transcription

            logger.info(f"Starting transcription - File: {file_path}, Input Language: {lng_input}, Target Language: {lng}")
            
            # Set up transcription parameters
            isMusic = True
            prompt = "Whisper, Ok. A pertinent sentence for your purpose in your language. Ok, Whisper. Whisper, Ok. Ok, Whisper. Whisper, Ok. Please find here, an unlikely ordinary sentence. This is to avoid a repetition to be deleted. Ok, Whisper. "
            logger.info(f"Transcription parameters - Music: {isMusic}, Prompt length: {len(prompt)}")

            # Perform transcription
            result = transcribePrompt(path=file_path, addSRT=True, lng=lng, prompt=prompt, lngInput=lng_input, isMusic=isMusic)
            logger.info("Transcription completed successfully")
            
            return result
        except Exception as e:
            logger.error(f"Error in predict: {str(e)}", exc_info=True)
            raise

    def encode_response(self, transcription):
        try:
            logger.info("Starting response encoding...")
            # Parse the JSON string returned by transcribePrompt
            transcription_data = json.loads(transcription)
            logger.info(f"Transcription data parsed successfully, text length: {len(transcription_data.get('text', ''))}")
            
            # Return the transcription as JSON
            return Response(content=json.dumps(transcription_data), media_type="application/json")
        except Exception as e:
            logger.error(f"Error in encode_response: {str(e)}", exc_info=True)
            raise

# Run the LitServe server
if __name__ == "__main__":
    try:
        logger.info("Starting WhisperHallu Server")
        server = ls.LitServer(WhisperHalluAPI(), accelerator="cuda", timeout=120)
        logger.info("Server initialized successfully")
        logger.info("Starting server on port 8889")
        server.run(port=8889)
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}", exc_info=True)
        raise
