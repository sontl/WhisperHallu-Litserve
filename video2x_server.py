import os
import subprocess
import tempfile
import urllib.parse
from fastapi import UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi import FastAPI
import litserve as ls

class VideoUpscalerAPI(ls.LitAPI):
    def setup(self, device):
        # Store temp directories to prevent cleanup
        self.temp_dirs = {}

    def decode_request(self, request: UploadFile):
        temp_dir = tempfile.TemporaryDirectory()
        input_path = os.path.join(temp_dir.name, "input.mp4")
        with open(input_path, "wb") as f:
            f.write(request.file.read())
        # Store temp_dir reference to prevent cleanup
        self.temp_dirs[input_path] = temp_dir
        return input_path

    def predict(self, input_path):
        temp_dir = self.temp_dirs[input_path]
        output_path = os.path.join(temp_dir.name, "output_upscaled.mp4")
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
            "-it", "--rm",
            "ghcr.io/k4yt3x/video2x:6.4.0",
            "-i", "/host/input.mp4",
            "-o", "/host/output_upscaled.mp4",
            "-p", "realcugan",
            "-s", "3",
            "--realcugan-model", "models-se"
        ]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"video2x processing failed: {e}")
        return output_path

    def encode_response(self, output_path):
        return {"file_path": output_path}  # Return as JSON with file path

if __name__ == "__main__":
    api = VideoUpscalerAPI()
    server = ls.LitServer(api)
    
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