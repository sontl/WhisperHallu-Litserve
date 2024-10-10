import litserve as ls
import os
import torchaudio
from demucs import pretrained
from demucs.apply import apply_model
import tempfile
from fastapi import Response, HTTPException
from pydub import AudioSegment
import torch

# Define your LitServe API
class DemucsAPI(ls.LitAPI):
    def setup(self, device):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        self.model = pretrained.get_model(name="htdemucs").to(self.device)

    def decode_request(self, request):
        # Get the uploaded audio file from the request (FormData)
        audio_file = request["content"].file
        if audio_file is None:
            raise HTTPException(status_code=400, detail="No audio file found in the request.")

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
            return wav_file.name
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing audio file: {str(e)}")

    def predict(self, file_path):
        # Load audio with torchaudio
        try:
            wav, sr = torchaudio.load(file_path)
            wav = wav.to(self.device)

            # Check if the audio is mono (1 channel) and convert to stereo if necessary
            if wav.shape[0] == 1:
                wav = torch.cat([wav, wav], dim=0)

            # Ensure the shape is (batch, channels, samples)
            if wav.dim() == 2:
                wav = wav.unsqueeze(0)

            sources = apply_model(self.model, wav, device=self.device)
            
            # Extract only the vocals (index 3 in the sources tensor)
            vocals = sources[:, 3]
            
            output_path = f'{file_path}_vocals.wav'
            torchaudio.save(output_path, vocals[0].cpu(), sr)  # Save only the vocals
            return output_path
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")

    def encode_response(self, output_path):
        try:
            # Read the content of the file
            with open(output_path, "rb") as f:
                content = f.read()
            # Remove the temporary file
            os.remove(output_path)
            # Return the response with the correct media type
            return Response(content=content, media_type="audio/wav")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error encoding response: {str(e)}")

# Run the LitServe server
if __name__ == "__main__":
    server = ls.LitServer(DemucsAPI(), accelerator="cuda")
    server.run(port=8888)