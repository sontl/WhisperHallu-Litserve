#!/usr/bin/env python3
"""
Test script for video2x server with R2 upload functionality
"""

import requests
import os

def test_video2x_with_r2():
    """Test video upscaling with R2 upload"""
    
    # Server URL
    server_url = "http://localhost:8866"
    
    # Test file path (adjust as needed)
    test_video = "input/caption.mp4"  # Use one of your existing test files
    
    if not os.path.exists(test_video):
        print(f"Test video {test_video} not found. Please adjust the path.")
        return
    
    # Test 1: Regular upscaling (file output)
    print("Testing regular upscaling (file output)...")
    with open(test_video, 'rb') as f:
        files = {'file': f}
        data = {
            'scale': 2,
            'isAnime': False,
            'urlOutput': False
        }
        
        response = requests.post(f"{server_url}/upscale", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    
    print("\n" + "="*50 + "\n")
    
    # Test 2: Upscaling with R2 upload
    print("Testing upscaling with R2 upload (URL output)...")
    with open(test_video, 'rb') as f:
        files = {'file': f}
        data = {
            'scale': 2,
            'isAnime': False,
            'urlOutput': True  # This will trigger R2 upload
        }
        
        response = requests.post(f"{server_url}/upscale", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result}")
            if result.get('type') == 'url':
                print(f"Video uploaded to R2: {result['url']}")
            else:
                print("R2 upload failed, returned local file path")
        else:
            print(f"Error: {response.status_code} - {response.text}")

def test_video2x_with_url():
    """Test video upscaling from URL with R2 upload"""
    
    server_url = "http://localhost:8866"
    
    # Example video URL (replace with actual URL)
    video_url = "https://example.com/sample_video.mp4"
    
    print("Testing upscaling from URL with R2 upload...")
    
    data = {
        'url': video_url,
        'scale': 2,
        'isAnime': False,
        'urlOutput': True
    }
    
    response = requests.post(f"{server_url}/upscale", data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Success: {result}")
        if result.get('type') == 'url':
            print(f"Video uploaded to R2: {result['url']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    print("Video2X R2 Upload Test")
    print("="*30)
    
    # Make sure to configure your .env file with R2 credentials before running
    print("Make sure your .env file is configured with R2 credentials:")
    print("- R2_ACCESS_KEY_ID")
    print("- R2_SECRET_ACCESS_KEY") 
    print("- R2_BUCKET_NAME")
    print("- R2_ENDPOINT_URL")
    print("- R2_PUBLIC_URL (optional)")
    print()
    
    test_video2x_with_r2()
    
    # Uncomment to test URL input
    # test_video2x_with_url()