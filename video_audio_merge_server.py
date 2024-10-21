import litserve as ls
import os
import tempfile
from fastapi import Response, HTTPException
import urllib.request
import ffmpeg
from starlette.middleware.cors import CORSMiddleware
class VideoAudioMergeAPI(ls.LitAPI):
    def setup(self, device):
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
            print(f"Saved video to {video_temp.name}")
            # Download the audio file
            urllib.request.urlretrieve(audio_url, audio_temp.name)
            audio_temp.close()
            print(f"Saved audio to {audio_temp.name}")
            return video_temp.name, audio_temp.name
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error processing files: {str(e)}")

    def predict(self, file_paths):
        video_path, audio_path = file_paths
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

        try:
            # Input video and audio streams
            input_video = ffmpeg.input(video_path)
            input_audio = ffmpeg.input(audio_path)

            # Merge video and audio
            output = ffmpeg.output(
                input_video,
                input_audio,
                output_path,
                vcodec='copy',  # Copy video codec
                acodec='aac',   # Use AAC for audio
                shortest=None   # End the output when the shortest input stream ends
            )

            # Run the FFmpeg command
            ffmpeg.run(output, overwrite_output=True, capture_stdout=True, capture_stderr=True)

            print("FFmpeg process completed successfully")

            # Clean up temporary files
            os.unlink(video_path)
            os.unlink(audio_path)
            print(f"Unlinked temporary files")
            print(f"Returning output path: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            # FFmpeg error occurred
            print(f"FFmpeg error: {e.stderr.decode()}")
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {e.stderr.decode()}")

        except Exception as e:
            # Other exceptions
            print(f"Error merging files: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error merging files: {str(e)}")

    def encode_response(self, output_path):
        try:
            print(f"Encoding response with output path: {output_path}")
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
    # Define the CORS settings
    cors_middleware = (
        CORSMiddleware, 
        {
            "allow_origins": ["https://*.singmesong.com", "http://localhost:3000"],  # Allows all origins
            "allow_methods": ["GET", "POST"],  # Allows GET and POST methods
            "allow_headers": ["*"],  # Allows all headers
        }
    )
    server = ls.LitServer(VideoAudioMergeAPI(), middlewares=[cors_middleware])
    
    server.run(port=8887)
