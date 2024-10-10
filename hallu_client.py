import argparse
import requests
from datetime import datetime

# Update this URL to your server's URL if hosted remotely
API_URL = "http://localhost:8889/predict"

def send_request(path):
    with open(path, 'rb') as input_file:
        input_data = input_file.read()

    response = requests.post(API_URL, files={"content": ("audio.mp3", input_data)})
    
    if response.status_code == 200:
        # Generate a unique filename for the output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"transcription_{timestamp}.txt"
        
        # Save the transcription to a text file
        with open(output_filename, "w", encoding="utf-8") as text_file:
            text_file.write(response.text)
        
        print(f"Transcription saved to {output_filename}")
    else:
        print(f"Error: Response with status code {response.status_code} - {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sends an audio file to the Whisper Hallu server and saves the transcription")
    parser.add_argument("--path", required=True, help="Path of the audio file to transcribe")
    args = parser.parse_args()
    
    send_request(args.path)