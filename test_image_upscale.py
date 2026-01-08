#!/usr/bin/env python
"""
Test script for Image Upscale Server
Tests various endpoints and functionality
"""

import requests
import os
import sys
from pathlib import Path

BASE_URL = "http://localhost:8867"

def test_health():
    """Test health check endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        print(f"✓ Health check passed: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False

def test_list_models():
    """Test models listing endpoint"""
    print("\nTesting models endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/models")
        response.raise_for_status()
        models = response.json()
        print(f"✓ Available models: {len(models['models'])}")
        for model_name, model_info in models['models'].items():
            print(f"  - {model_name}: {model_info['description']}")
        return True
    except Exception as e:
        print(f"✗ Models listing failed: {e}")
        return False

def test_upscale_file(image_path: str):
    """Test image upscaling with file upload"""
    print(f"\nTesting upscale with file: {image_path}")
    
    if not os.path.exists(image_path):
        print(f"✗ Test image not found: {image_path}")
        return False
    
    try:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = {
                'scale': 4,
                'model': 'RealESRGAN_x4',
                'urlOutput': False
            }
            
            print("  Uploading and processing image...")
            response = requests.post(f"{BASE_URL}/upscale", files=files, data=data)
            response.raise_for_status()
            
            result = response.json()
            print(f"✓ Upscale successful!")
            print(f"  Job ID: {result.get('job_id')}")
            print(f"  Type: {result.get('type')}")
            
            if result.get('type') == 'file':
                print(f"  Output: {result.get('file_path')}")
            elif result.get('type') == 'url':
                print(f"  URL: {result.get('url')}")
            
            return True
    except Exception as e:
        print(f"✗ Upscale failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}")
        return False

def test_upscale_url(image_url: str):
    """Test image upscaling with URL"""
    print(f"\nTesting upscale with URL: {image_url}")
    
    try:
        data = {
            'url': image_url,
            'scale': 2,
            'model': 'RealESRGAN_x2plus',
            'urlOutput': False
        }
        
        print("  Downloading and processing image...")
        response = requests.post(f"{BASE_URL}/upscale", data=data)
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ Upscale successful!")
        print(f"  Job ID: {result.get('job_id')}")
        print(f"  Type: {result.get('type')}")
        
        if result.get('type') == 'file':
            print(f"  Output: {result.get('file_path')}")
        elif result.get('type') == 'url':
            print(f"  URL: {result.get('url')}")
        
        return True
    except Exception as e:
        print(f"✗ Upscale failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}")
        return False

def test_upscale_json(image_url: str):
    """Test image upscaling with JSON payload"""
    print(f"\nTesting upscale-json endpoint with URL: {image_url}")
    
    try:
        payload = {
            'url': image_url,
            'scale': 2,
            'model': 'RealESRGAN_x2plus',
            'urlOutput': False
        }
        
        print("  Sending JSON request...")
        response = requests.post(
            f"{BASE_URL}/upscale-json",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ Upscale successful!")
        print(f"  Job ID: {result.get('job_id')}")
        print(f"  Type: {result.get('type')}")
        
        if result.get('type') == 'file':
            print(f"  Output: {result.get('file_path')}")
        elif result.get('type') == 'url':
            print(f"  URL: {result.get('url')}")
        
        return True
    except Exception as e:
        print(f"✗ Upscale failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Response: {e.response.text}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Image Upscale Server Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test health
    results.append(("Health Check", test_health()))
    
    # Test models listing
    results.append(("List Models", test_list_models()))
    
    # Test with local file if available
    test_images = [
        "input/test.jpg",
        "input/test.png",
        "test.jpg",
        "test.png"
    ]
    
    local_file_found = False
    for test_image in test_images:
        if os.path.exists(test_image):
            results.append(("Upscale File", test_upscale_file(test_image)))
            local_file_found = True
            break
    
    if not local_file_found:
        print("\n⚠ No local test image found, skipping file upload test")
        print("  Create a test image at: input/test.jpg or test.jpg")
    
    # Test with URL (sample image)
    sample_url = "https://raw.githubusercontent.com/xinntao/Real-ESRGAN/master/inputs/0014.jpg"
    results.append(("Upscale URL", test_upscale_url(sample_url)))
    
    # Test JSON endpoint
    results.append(("Upscale JSON", test_upscale_json(sample_url)))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())