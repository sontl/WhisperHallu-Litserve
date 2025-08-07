import os
import subprocess
import tempfile
import urllib.parse
import requests
from fastapi import UploadFile, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi import FastAPI
from typing import Optional
import litserve as ls

class VideoUpscalerAPI(ls.LitAPI):
    def setup(self, device):
        # Store temp directories to prevent cleanup
        self.temp_dirs = {}

    def decode_request(self, request):
        # Handle both UploadFile (from LitServe /predict) and dict (from custom /upscale)
        if isinstance(request, UploadFile):
            # Direct UploadFile from LitServe /predict endpoint
            file = request
            url = None
            scale = 3  # default
            is_anime = False  # default
        else:
            # Form data with parameters from custom /upscale endpoint
            file = request.get('file')
            url = request.get('url')
            scale = int(request.get('scale', 3))
            is_anime = request.get('isAnime', 'false').lower() == 'true'
        
        if file is None and url is None:
            raise ValueError("Either file or URL must be provided in request")
        
        if file is not None and url is not None:
            raise ValueError("Please provide either file or URL, not both")
            
        temp_dir = tempfile.TemporaryDirectory()
        input_path = os.path.join(temp_dir.name, "input.mp4")
        
        if url is not None:
            # Download video from URL
            try:
                response = requests.get(url, stream=True, timeout=300)
                response.raise_for_status()
                
                with open(input_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            except requests.exceptions.RequestException as e:
                temp_dir.cleanup()
                raise ValueError(f"Failed to download video from URL: {str(e)}")
        else:
            # Handle uploaded file
            with open(input_path, "wb") as f:
                # Read file content properly
                if isinstance(file, UploadFile):
                    # For UploadFile, read directly
                    content = file.file.read()
                else:
                    # For dict-based request, file should also be UploadFile
                    content = file.file.read()
                f.write(content)
        
        # Store temp_dir reference to prevent cleanup
        self.temp_dirs[input_path] = temp_dir
        return {
            'input_path': input_path,
            'scale': scale,
            'is_anime': is_anime
        }

    def predict(self, request_data):
        input_path = request_data['input_path']
        scale = request_data['scale']
        is_anime = request_data['is_anime']
        
        temp_dir = self.temp_dirs[input_path]
        output_path = os.path.join(temp_dir.name, "output_upscaled.mp4")
        
        # Build command based on parameters
        command = [
            "docker", "run", "--gpus", "all",
            "-e", "NVIDIA_VISIBLE_DEVICES=all",
            "-e", "NVIDIA_DRIVER_CAPABILITIES=all",
            "-e", "VIDEO2X_VULKAN_DEVICE=0",
            "-v", f"{temp_dir.name}:/host",
            "--device", "/dev/dri",
            "--device", "/dev/nvidia0",
            "--device", "/dev/nvidiactl",
            "--device", "/dev/nvidia-modeset",
            "--device", "/dev/nvidia-uvm",
            "--device", "/dev/nvidia-uvm-tools",
            "--rm",  # Removed -it flag to avoid TTY issues
            "ghcr.io/k4yt3x/video2x:6.4.0",
            "-i", "/host/input.mp4",
            "-o", "/host/output_upscaled.mp4",
            "-s", str(scale)
        ]
        
        if is_anime:
            command.extend(["-p", "realesrgan", "--realesrgan-model", "realesr-animevideov3"])
        else:
            command.extend(["-p", "realcugan", "--realcugan-model", "models-se"])
        
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            error_msg = f"video2x processing failed: {e}"
            if e.stdout:
                error_msg += f"\nStdout: {e.stdout}"
            if e.stderr:
                error_msg += f"\nStderr: {e.stderr}"
            raise RuntimeError(error_msg)
        return output_path

    def encode_response(self, output_path):
        return {"file_path": output_path}  # Return as JSON with file path

if __name__ == "__main__":
    api = VideoUpscalerAPI()
    server = ls.LitServer(api)
    
    # Add custom endpoint for video upscaling with parameters
    @server.app.post("/upscale")
    async def upscale_video(
        file: Optional[UploadFile] = None,
        url: Optional[str] = Form(None),
        scale: Optional[int] = Form(3),
        isAnime: Optional[bool] = Form(False)
    ):
        try:
            # Create request data structure
            request_data = {
                'file': file,
                'url': url,
                'scale': scale,
                'isAnime': isAnime
            }
            
            # Process through the API
            decoded_request = api.decode_request(request_data)
            output_path = api.predict(decoded_request)
            response = api.encode_response(output_path)
            
            return response
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    
    # Add the download endpoint to LitServer's FastAPI app
    @server.app.get("/download")
    async def download_video(file_path: str):
        decoded_path = urllib.parse.unquote(file_path)
        if not os.path.exists(decoded_path):
            raise HTTPException(status_code=404, detail=f"File not found: {decoded_path}")
        try:
            return FileResponse(
                decoded_path,
                media_type="video/mp4",
                filename="upscaled_video.mp4"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")
    
    server.run(port=8866)