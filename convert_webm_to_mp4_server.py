import litserve as ls
import os
import tempfile
from fastapi import Response, HTTPException
import ffmpeg
from starlette.middleware.cors import CORSMiddleware

class WebmToMP4API(ls.LitAPI):
    def setup(self, device):
        # No specific setup needed for this server
        pass

    def decode_request(self, request):
        # Get the uploaded webm file from the request
        webm_file = request["video"].file
        # Get compression parameter, default to False
        compress = request.get("compress", False)
        if webm_file is None:
            raise HTTPException(status_code=400, detail="No WebM file found in the request.")

        # Create temporary file for the uploaded webm
        webm_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")

        try:
            # Save the uploaded webm to a temporary file
            content = webm_file.read()
            if len(content) == 0:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            
            webm_temp.write(content)
            webm_temp.close()
            
            # Verify the input file is valid
            try:
                probe = ffmpeg.probe(webm_temp.name)
                print(f"Input file info: {probe}")
                
                # Get video stream info
                video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                if video_info:
                    print(f"Input video codec: {video_info.get('codec_name')}")
                    print(f"Input video dimensions: {video_info.get('width')}x{video_info.get('height')}")
            except ffmpeg.Error as e:
                raise HTTPException(status_code=400, detail=f"Invalid input file: {str(e)}")
                
            print(f"Saved WebM to {webm_temp.name}")
            return {"webm_path": webm_temp.name, "compress": compress}
        except Exception as e:
            if os.path.exists(webm_temp.name):
                os.unlink(webm_temp.name)
            raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

    def predict(self, input_data):
        webm_path = input_data["webm_path"]
        compress = input_data["compress"]
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

        try:
            # First, try to get input file information
            probe = ffmpeg.probe(webm_path)
            video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            
            if not video_info:
                raise HTTPException(status_code=400, detail="No video stream found in input file")

            # Set encoding parameters based on compression flag
            encoding_params = {
                'vcodec': 'libx264',
                'acodec': 'aac',
                'pix_fmt': 'yuv420p',
                'profile': 'high',
                'level': '4.0',
                'movflags': '+faststart+rtphint',
                'strict': 'strict',
                'brand': 'mp42',
                'ac': 2,
                'ar': '48000',
                'max_muxing_queue_size': '1024'
            }

            if compress:
                # Compressed settings
                encoding_params.update({
                    'preset': 'slower',  # Better compression at cost of encoding time
                    'crf': '28',         # Higher CRF means more compression (range 0-51)
                    'video_bitrate': '800k',  # Lower bitrate for smaller file
                    'audio_bitrate': '96k',   # Lower audio bitrate
                    'g': '60',           # Longer GOP for better compression
                })
            else:
                # Standard quality settings (existing settings)
                encoding_params.update({
                    'preset': 'medium',
                    'video_bitrate': '2M',
                    'g': '30',
                    'force_key_frames': 'expr:gte(t,n_forced*2)'
                })

            # Convert WebM to MP4 using ffmpeg
            stream = ffmpeg.input(webm_path)
            stream = ffmpeg.output(stream, output_path, **encoding_params)

            # Get the ffmpeg command for debugging
            cmd = ffmpeg.compile(stream)
            print(f"FFmpeg command: {' '.join(cmd)}")

            # Run the FFmpeg command
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)

            # Verify the output file
            try:
                output_probe = ffmpeg.probe(output_path)
                print(f"Output file info: {output_probe}")
            except ffmpeg.Error as e:
                print(f"Warning: Could not probe output file: {str(e)}")

            print("FFmpeg conversion completed successfully")

            # Clean up temporary file
            os.unlink(webm_path)
            print(f"Unlinked temporary WebM file")
            return output_path

        except ffmpeg.Error as e:
            if os.path.exists(output_path):
                os.unlink(output_path)
            print(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        except Exception as e:
            if os.path.exists(output_path):
                os.unlink(output_path)
            print(f"Error converting file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error converting file: {str(e)}")

    def encode_response(self, output_path):
        try:
            print(f"Encoding response with output path: {output_path}")
            # Read the content of the converted file
            with open(output_path, "rb") as f:
                content = f.read()
            # Remove the temporary converted file
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
            "allow_origins": ["https://*.singmesong.com", "http://localhost:3000"],
            "allow_methods": ["GET", "POST"],
            "allow_headers": ["*"],
        }
    )
    server = ls.LitServer(WebmToMP4API(), middlewares=[cors_middleware])
    
    server.run(port=8882) 