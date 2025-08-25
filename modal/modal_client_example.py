#!/usr/bin/env python3
"""
Example client for Modal.com Audio Transcription API
"""

import requests
import json
import sys

def transcribe_audio(api_url: str, audio_url: str, target_lang: str = "en", source_lang: str = "auto"):
    """
    Send transcription request to Modal API
    
    Args:
        api_url: Modal API endpoint URL
        audio_url: Direct URL to audio file
        target_lang: Target language code (e.g., "en", "fr", "es")
        source_lang: Source language code or "auto" for detection
    
    Returns:
        dict: Transcription result or error
    """
    
    payload = {
        "url": audio_url,
        "lng": target_lang,
        "lng_input": source_lang
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print(f"Sending request to: {api_url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=600)
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            return {
                "error": f"HTTP {response.status_code}: {response.text}"
            }
            
    except requests.exceptions.Timeout:
        return {"error": "Request timeout (10 minutes)"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def main():
    # Example usage
    API_URL = "https://your-modal-app-url.modal.run/transcribe_endpoint"
    
    # Example audio URLs (replace with your own)
    test_cases = [
        {
            "url": "https://example.com/song.mp3",
            "lng": "en",
            "lng_input": "auto",
            "description": "English song transcription"
        },
        {
            "url": "https://example.com/french_audio.mp3", 
            "lng": "fr",
            "lng_input": "fr",
            "description": "French audio transcription"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*50}")
        print(f"Test Case {i}: {test_case['description']}")
        print(f"{'='*50}")
        
        result = transcribe_audio(
            API_URL,
            test_case["url"],
            test_case["lng"],
            test_case["lng_input"]
        )
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Success!")
            print(f"📝 Text: {result.get('text', '')[:200]}...")
            print(f"📊 Segments: {len(result.get('json', []))}")
            print(f"🎬 SRT Length: {len(result.get('srt', ''))} characters")
            
            # Save detailed results
            filename = f"transcription_result_{i}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"💾 Full result saved to: {filename}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Command line usage
        if len(sys.argv) < 3:
            print("Usage: python modal_client_example.py <api_url> <audio_url> [target_lang] [source_lang]")
            sys.exit(1)
            
        api_url = sys.argv[1]
        audio_url = sys.argv[2]
        target_lang = sys.argv[3] if len(sys.argv) > 3 else "en"
        source_lang = sys.argv[4] if len(sys.argv) > 4 else "auto"
        
        result = transcribe_audio(api_url, audio_url, target_lang, source_lang)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Interactive example
        main()
