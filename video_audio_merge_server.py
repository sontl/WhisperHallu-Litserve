import litserve as ls
import os
import tempfile
from fastapi import Response, HTTPException
import urllib.request
import subprocess

class VideoAudioMergeAPI(ls.LitAPI):
    def setup(self):
        # No specific setup needed for this server
        pass

    def decode_request(self, request):
        # Get the uploaded video file from the request
        video_file = request["video"].file
        if video_file is None:
            raise HTTPException(status_code=400, detail="No video file found in the request.")

        # Get the audio URL from the request
        audio_url = request["audio_url"]
        if not audio_url:
            raise HTTPException(status_code=400, detail="No audio URL provided in the request.")

        # Create temporary files for video and audio
        video_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")

        try:
            # Save the uploaded video to a temporary file
            video_temp.write(video_file.read())
            video_temp.close()

            # Download the audio file
            urllib.request.urlretrieve(audio_url, audio_temp.name)
            audio_temp.close()

            return video_temp.name, audio_temp.name
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing files: {str(e)}")

    def predict(self, file_paths):
        video_path, audio_path = file_paths
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

        try:
            # Use FFmpeg to merge video and audio
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)

            # Clean up temporary files
            os.unlink(video_path)
            os.unlink(audio_path)

            return output_path
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {e.stderr.decode()}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error merging files: {str(e)}")

    def encode_response(self, output_path):
        try:
            # Read the content of the merged file
            with open(output_path, "rb") as f:
                content = f.read()
            # Remove the temporary merged file
            os.remove(output_path)
            # Return the response with the correct media type
            return Response(content=content, media_type="video/mp4")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error encoding response: {str(e)}")

# Run the LitServe server
if __name__ == "__main__":
    server = ls.LitServer(VideoAudioMergeAPI())
    server.run(port=8887)
