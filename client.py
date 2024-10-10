import argparse
import requests
from datetime import datetime

# Update this URL to your server's URL if hosted remotely
API_URL = "https://demucs.singmesong.com/predict"

def send_request(path):

    inputFile = open(path, 'rb')
    inputData = inputFile.read()
    inputFile.close()

    response = requests.post(API_URL, files={"prompt": (None, ""), "content": inputData})
    if response.status_code == 200:
        filename = "output.wav"
        
        with open(filename, "wb") as audio_file:
            audio_file.write(response.content)
        
        print(f"Audio saved to {filename}")
    else:
        print(f"Error: Response with status code {response.status_code} - {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sends a file to the deep filter net server and receives the enhanced audio")
    parser.add_argument("--path", required=True, help="Path of the audio file to convert")
    args = parser.parse_args()
    
    send_request(args.path)