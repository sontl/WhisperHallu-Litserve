import litserve as ls
import torch
from faster_whisper import WhisperModel
import tempfile

# Define the LitServe API
class FasterWhisperAPI(ls.LitAPI):
    def setup(self, device):
        # Load the pre-trained FasterWhisper model
        self.model = WhisperModel("medium", device="cuda" if torch.cuda.is_available() else "cpu")

    def decode_request(self, request):
        # Save the uploaded audio file to a temporary file
        audio_file = request["audio_file"]
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(audio_file.read())
        return temp_file.name

    def predict(self, file_path):
        # Run transcription with FasterWhisper
        segments, _ = self.model.transcribe(file_path)
        
        # Collect all segments into a single transcript
        transcript = ""
        for segment in segments:
            transcript += f"{segment.start:.2f} --> {segment.end:.2f}: {segment.text}\n"
        
        return transcript

    def encode_response(self, output):
        # Return the transcribed text
        return {"transcription": output}

# Run the LitServe server
if __name__ == "__main__":
    server = ls.LitServer(FasterWhisperAPI(), accelerator="auto")
    server.run(port=8000)
