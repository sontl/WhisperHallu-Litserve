import litserve as ls
import os
import tempfile
from fastapi import Response, HTTPException
from pydub import AudioSegment
import torch
from transcribeHallu import loadModel, transcribePrompt
import json
import requests

class WhisperHalluAPI(ls.LitAPI):
    def setup(self, device):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        self.model_size = "medium"
        loadModel("0", modelSize=self.model_size)

    def decode_request(self, request):
        # Get the URL from the request, if present
        url = request.get("url")

        # Get lng and lng_input from the request, with default values
        lng = request.get("lng", "en")
        lng_input = request.get("lng_input", "en")

        if url:
            # If URL is provided, download the file
            try:
                response = requests.get(url)
                response.raise_for_status()
                
                # Create a temporary file with a .mp3 extension
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                
                # Write the downloaded content to the temporary file
                with open(temp_file.name, "wb") as f:
                    f.write(response.content)
                
                # Convert MP3 to WAV
                audio = AudioSegment.from_mp3(temp_file.name)
                wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                audio.export(wav_file.name, format="wav")
                
                # Clean up the temporary MP3 file
                os.unlink(temp_file.name)
                
                return {"file_path": wav_file.name, "lng": lng, "lng_input": lng_input}
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error downloading or processing file from URL: {str(e)}")

        # If no URL, process the audio file as before
        audio_file = request["content"].file
        if audio_file is None:
            raise HTTPException(status_code=400, detail="No audio file or URL found in the request.")

        # Create a temporary file with a .mp3 extension
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        
        # Read the file content
        audio_data = audio_file.read()
        
        # Write the audio data to the temporary file
        with open(temp_file.name, "wb") as f:
            f.write(audio_data)
        
        # Convert MP3 to WAV
        try:
            audio = AudioSegment.from_mp3(temp_file.name)
            wav_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            audio.export(wav_file.name, format="wav")
            
            # Clean up the temporary MP3 file
            os.unlink(temp_file.name)
            print("wav_file.name: ", wav_file.name)
            return {"file_path": wav_file.name, "lng": lng, "lng_input": lng_input}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing audio file: {str(e)}")

    def predict(self, request_data):
        try:
            file_path = request_data["file_path"]
            lng = request_data.get("lng", "en")
            lng_input = request_data.get("lng_input", "en")

            # Set up transcription parameters
            isMusic = True
            prompt = "Whisper, Ok. A pertinent sentence for your purpose in your language. Ok, Whisper. Whisper, Ok. Ok, Whisper. Whisper, Ok. Please find here, an unlikely ordinary sentence. This is to avoid a repetition to be deleted. Ok, Whisper. "

            # Perform transcription
            result = transcribePrompt(path=file_path, addSRT=True, lng=lng, prompt=prompt, lngInput=lng_input, isMusic=isMusic)

            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")

    def encode_response(self, transcription):
        try:
            # Parse the JSON string returned by transcribePrompt
            transcription_data = json.loads(transcription)
            
            # Return the transcription as JSON
            return Response(content=json.dumps(transcription_data), media_type="application/json")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error encoding response: {str(e)}")

# Run the LitServe server
if __name__ == "__main__":
    server = ls.LitServer(WhisperHalluAPI(), accelerator="cuda", timeout=120)  # Increased timeout to 120 seconds
    server.run(port=8889)
