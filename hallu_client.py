import argparse
import requests
from datetime import datetime
import json

# Update this URL to your server's URL if hosted remotely
API_URL = "http://localhost:8889/predict"

def send_request(input_source, lng, lng_input, is_url=False):
    data = {
        "lng": lng,
        "lng_input": lng_input
    }

    if is_url:
        data["url"] = input_source
        files = None
    else:
        with open(input_source, 'rb') as input_file:
            input_data = input_file.read()
        files = {"content": ("audio.mp3", input_data)}

    response = requests.post(API_URL, files=files, data=data)
    
    if response.status_code == 200:
        # Generate a unique filename for the output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Parse the JSON response
        transcription_data = json.loads(response.text)
        
        # Save the full JSON response
        json_filename = f"transcription_{timestamp}.json"
        with open(json_filename, "w", encoding="utf-8") as json_file:
            json.dump(transcription_data, json_file, ensure_ascii=False, indent=2)
        print(f"Full transcription data saved to {json_filename}")
        
        # Save the SRT content
        srt_filename = f"transcription_{timestamp}.srt"
        with open(srt_filename, "w", encoding="utf-8") as srt_file:
            srt_file.write(transcription_data["srt"])
        print(f"SRT content saved to {srt_filename}")
        
        # Save the plain text transcription
        text_filename = f"transcription_{timestamp}.txt"
        with open(text_filename, "w", encoding="utf-8") as text_file:
            text_file.write(transcription_data["text"])
        print(f"Plain text transcription saved to {text_filename}")
        
    else:
        print(f"Error: Response with status code {response.status_code} - {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sends an audio file or URL to the Whisper Hallu server and saves the transcription")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--path", help="Path of the audio file to transcribe")
    group.add_argument("--url", help="URL of the audio file to transcribe")
    parser.add_argument("--lng", default="en", help="Language for transcription output (default: en)")
    parser.add_argument("--lng_input", default="en", help="Language of the input audio (default: en)")
    args = parser.parse_args()
    
    if args.url:
        send_request(args.url, args.lng, args.lng_input, is_url=True)
    else:
        send_request(args.path, args.lng, args.lng_input, is_url=False)