import requests
import os

url = "https://api.gladia.io/v2/upload"

# Specify the name of the audio file in the same folder
audio_file_name = "test.mp3"  # Replace with your actual file name

# Check if the file exists
if not os.path.exists(audio_file_name):
    print(f"Error: File '{audio_file_name}' not found in the current directory.")
    exit()

headers = {
    "x-gladia-key": "aac97688-7e14-4274-8e03-cbf2a8212828",
}

# Open the file and send it in the request
with open(audio_file_name, "rb") as audio_file:
    files = {"audio": (audio_file_name, audio_file, "audio/mpeg")}
    response = requests.post(url, headers=headers, files=files)

print(response.status_code)
print(response.text)