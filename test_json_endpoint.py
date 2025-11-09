import requests
import json

# Example of how to use the new JSON endpoint
def test_json_endpoint():
    # Example with URL input
    payload = {
        "url": "https://example.com/video.mp4",
        "scale": 2,
        "isAnime": True,
        "urlOutput": True
    }
    
    response = requests.post(
        "http://localhost:8866/upscale-json",
        json=payload
    )
    
    print("Status Code:", response.status_code)
    print("Response:", response.json())

if __name__ == "__main__":
    test_json_endpoint()