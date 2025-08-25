import modal
import os
import json
import time
import requests
import tempfile
import logging
from pathlib import Path

# Create Modal app
app = modal.App("whisper-hallu-transcribe")

# Define images for different resource requirements
# GPU image for Demucs processing
gpu_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install([
        "torch",
        "torchaudio", 
        "demucs",
        "requests",
        "ffmpeg-python"
    ])
    .apt_install(["ffmpeg"])
)

# CPU image for API calls and orchestration
cpu_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install([
        "requests",
        "fastapi"
    ])
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.function(
    image=gpu_image,
    gpu="T4",
    scaledown_window=2,
    timeout=300  # Reduced timeout for GPU processing only
)
def extract_vocals_gpu(audio_url: str) -> str:
    """
    GPU function to extract vocals from audio URL using Demucs.
    Returns the vocals audio data as bytes.
    """
    import requests
    import tempfile
    
    try:
        logger.info(f"GPU: Processing audio URL: {audio_url}")
        
        # Step 1: Download audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
            logger.info("GPU: Downloading audio file...")
            response = requests.get(audio_url, stream=True)
            response.raise_for_status()
            
            for chunk in response.iter_content(chunk_size=8192):
                temp_audio.write(chunk)
            
            temp_audio_path = temp_audio.name
        
        logger.info(f"GPU: Audio downloaded to: {temp_audio_path}")
        
        # Step 2: Convert to WAV format
        wav_path = temp_audio_path + ".wav"
        convert_to_wav(temp_audio_path, wav_path)
        
        # Step 3: Extract vocals using Demucs
        vocals_path = extract_vocals_with_demucs(wav_path)
        
        # Step 4: Read vocals file and return as base64
        import base64
        with open(vocals_path, 'rb') as f:
            vocals_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Cleanup temporary files
        cleanup_files([temp_audio_path, wav_path, vocals_path])
        
        logger.info("GPU: Vocal extraction completed")
        return vocals_data
        
    except Exception as e:
        logger.error(f"GPU: Error in vocal extraction: {str(e)}")
        raise e

def convert_to_wav(input_path: str, output_path: str):
    """Convert audio file to WAV format using ffmpeg"""
    import subprocess
    
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:a", "pcm_s16le", "-ar", "16000",
        output_path
    ]
    
    logger.info(f"Converting to WAV: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"FFmpeg conversion failed: {result.stderr}")

def extract_vocals_with_demucs(audio_path: str) -> str:
    """Extract vocals from audio using Demucs"""
    import torch
    import torchaudio
    from demucs.pretrained import get_model_from_args
    from demucs.apply import apply_model
    from demucs.separate import load_track
    
    logger.info("Loading Demucs model...")
    model = get_model_from_args(type('args', (object,), dict(name='htdemucs', repo=None))).cpu().eval()
    
    logger.info(f"Processing audio with Demucs: {audio_path}")
    audio = load_track(audio_path, model.audio_channels, model.samplerate)
    
    # Ensure proper audio dimensions
    audio_dims = audio.dim()
    if audio_dims == 1:
        audio = audio[None, None].repeat_interleave(2, -2)
    else:
        if audio.shape[-2] == 1:
            audio = audio.repeat_interleave(2, -2)
        if audio_dims < 3:
            audio = audio[None]
    
    # Use GPU if available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Demucs using device: {device}")
    
    result = apply_model(model, audio, device=device, split=True, overlap=.25)
    
    if device != 'cpu':
        torch.cuda.empty_cache()
    
    # Extract vocals
    vocals_path = audio_path + ".vocals.wav"
    vocals_idx = model.sources.index('vocals')
    vocals = result[0, vocals_idx].mean(0)
    torchaudio.save(vocals_path, vocals[None], model.samplerate)
    
    logger.info(f"Vocals extracted to: {vocals_path}")
    return vocals_path

def transcribe_with_gladia(audio_path: str, source_lang: str, target_lang: str) -> dict:
    """Transcribe audio using Gladia API"""
    logger.info(f"Starting Gladia transcription - File: {audio_path}")
    logger.info(f"Source language: {source_lang}, Target language: {target_lang}")
    
    upload_url = "https://api.gladia.io/v2/upload"
    transcribe_url = "https://api.gladia.io/v2/pre-recorded"
    
    # Get API key from Modal secret
    api_key = os.getenv('GLADIA_API_KEY')
    if not api_key:
        logger.error("GLADIA_API_KEY environment variable not set")
        return {"text": "", "srt": "", "json": []}

    headers = {"x-gladia-key": api_key}

    try:
        # Step 1: Upload the file
        with open(audio_path, "rb") as audio_file:
            logger.info(f"Uploading file to Gladia: {audio_path}")
            files = {"audio": (os.path.basename(audio_path), audio_file, "audio/wav")}
            upload_response = requests.post(upload_url, files=files, headers=headers)
        
        if upload_response.status_code != 200:
            logger.error(f"Upload failed - Status code: {upload_response.status_code}")
            return {"text": "", "srt": "", "json": []}

        upload_result = upload_response.json()
        audio_url = upload_result["audio_url"]
        logger.info(f"File uploaded successfully - URL: {audio_url}")

        # Step 2: Request transcription
        transcribe_headers = {
            "x-gladia-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "audio_url": audio_url,
            "detect_language": source_lang == "auto",
            "language": source_lang if source_lang != "auto" else None,
            "translation": target_lang != source_lang and target_lang != "auto",
            "translation_config": {
                "target_languages": [target_lang],
                "model": "base",
                "match_original_utterances": True
            } if target_lang != source_lang and target_lang != "auto" else None,
            "diarization": False,
            "subtitles": True,
            "subtitles_config": {
                "formats": ["srt"],
            },
        }

        logger.info("Requesting transcription from Gladia")
        transcribe_response = requests.post(transcribe_url, json=payload, headers=transcribe_headers)
        
        if transcribe_response.status_code not in [200, 201]:
            logger.error(f"Transcription request failed - Status code: {transcribe_response.status_code}")
            return {"text": "", "srt": "", "json": []}

        transcribe_result = transcribe_response.json()
        result_url = transcribe_result["result_url"]
        logger.info(f"Transcription request successful - Result URL: {result_url}")
        
        # Step 3: Poll for results
        max_wait_time = 300
        total_wait_time = 0
        
        while total_wait_time < max_wait_time:
            result_response = requests.get(result_url, headers=headers)
            
            if result_response.status_code in [200, 201]:
                gladia_result = result_response.json()
                
                if gladia_result.get("status") == "done":
                    logger.info("Transcription completed successfully")
                    formatted_result = convert_gladia_to_internal_format(gladia_result)
                    return formatted_result
                else:
                    wait_time = 3
                    total_wait_time += wait_time
                    logger.info(f"Waiting for result - Status: {gladia_result.get('status')} - Waited: {total_wait_time}s")
                    time.sleep(wait_time)
            else:
                logger.error(f"Failed to fetch result - Status code: {result_response.status_code}")
                return {"text": "", "srt": "", "json": []}

        logger.warning(f"Timeout waiting for result - Max wait time ({max_wait_time}s) reached")
        return {"text": "", "srt": "", "json": []}
        
    except requests.exceptions.RequestException as e:
        logger.error("Failed to connect to Gladia API", exc_info=True)
        return {"text": "", "srt": "", "json": []}

def convert_gladia_to_internal_format(gladia_response):
    """Convert Gladia API response to internal format"""
    result = {
        "text": "",
        "srt": "",
        "json": []
    }

    gladia_response = gladia_response.get("result", {})
    
    # Get utterances from transcription
    transcription = gladia_response.get("transcription", {})
    utterances = transcription.get("utterances", [])
    
    # Convert utterances to internal JSON format
    for utterance in utterances:
        json_segment = {
            "start": utterance.get("start", 0),
            "end": utterance.get("end", 0),
            "sentence": utterance.get("text", "").strip(),
            "words": []
        }
        
        for word in utterance.get("words", []):
            json_segment["words"].append({
                "start": word.get("start", 0),
                "end": word.get("end", 0),
                "text": word.get("word", "").strip()
            })
        
        result["json"].append(json_segment)
    
    # Get text and SRT
    result["text"] = transcription.get("full_transcript", "")
    subtitles = transcription.get("subtitles", [])
    if subtitles:
        result["srt"] = subtitles[0].get("subtitles", "")
    
    return result

def cleanup_files(file_paths: list):
    """Clean up temporary files"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.info(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")

@app.function(
    image=cpu_image,
    timeout=600,
    scaledown_window=2,
    secrets=[modal.Secret.from_name("gladia-api-key")]
)
def transcribe_with_gladia_cpu(vocals_data: str, source_lang: str, target_lang: str) -> dict:
    """
    CPU function to transcribe vocals using Gladia API.
    Takes base64 encoded vocals data.
    """
    import base64
    import tempfile
    
    try:
        logger.info("CPU: Starting Gladia transcription")
        
        # Decode vocals data and save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_vocals:
            vocals_bytes = base64.b64decode(vocals_data)
            temp_vocals.write(vocals_bytes)
            vocals_path = temp_vocals.name
        
        # Call Gladia API
        result = transcribe_with_gladia(vocals_path, source_lang, target_lang)
        
        # Cleanup
        cleanup_files([vocals_path])
        
        logger.info("CPU: Gladia transcription completed")
        return result
        
    except Exception as e:
        logger.error(f"CPU: Error in Gladia transcription: {str(e)}")
        return {"error": str(e)}

# Main orchestration endpoint
@app.function(image=cpu_image, scaledown_window=2)
@modal.fastapi_endpoint(method="POST")
def transcribe_endpoint(request_data: dict):
    """
    Main endpoint that orchestrates GPU vocal extraction and CPU Gladia transcription.
    
    Expected JSON input:
    {
        "url": "https://example.com/audio.mp3",
        "lng": "en", 
        "lng_input": "auto"
    }
    """
    try:
        # Extract parameters from request
        audio_url = request_data.get("url")
        output_lang = request_data.get("lng", "en")
        input_lang = request_data.get("lng_input", "auto")
        
        if not audio_url:
            return {"error": "Missing 'url' parameter"}
        
        logger.info(f"Main: Processing request - URL: {audio_url}, Input: {input_lang}, Output: {output_lang}")
        
        # Step 1: Extract vocals using GPU function
        logger.info("Main: Starting GPU vocal extraction...")
        vocals_data = extract_vocals_gpu.remote(audio_url)
        
        # Step 2: Transcribe using CPU function (no GPU cost during waiting)
        logger.info("Main: Starting CPU Gladia transcription...")
        result = transcribe_with_gladia_cpu.remote(vocals_data, input_lang, output_lang)
        
        logger.info("Main: Transcription pipeline completed")
        return result
        
    except Exception as e:
        logger.error(f"Main: Error in transcription pipeline: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # For local testing
    test_request = {
        "url": "https://example.com/test-audio.mp3",
        "lng": "en",
        "lng_input": "auto"
    }
    
    with app.run():
        result = transcribe_audio_endpoint.remote(test_request)
        print(json.dumps(result, indent=2))
