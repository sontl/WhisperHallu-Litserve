import litserve as ls
import os
import tempfile
from fastapi import Response, HTTPException
import ffmpeg
from starlette.middleware.cors import CORSMiddleware
import logging
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebmToMP4API(ls.LitAPI):
    def setup(self, device):
        logger.info("Setting up WebmToMP4API")
        # No specific setup needed for this server
        pass

    def decode_request(self, request):
        logger.info("Decoding request")
        # Get the uploaded webm file from the request
        webm_file = request["video"].file
        # Get compression parameter, default to False
        compress = request.get("compress", False)
        logger.info(f"Compression requested: {compress}")
        
        if webm_file is None:
            logger.error("No WebM file found in request")
            raise HTTPException(status_code=400, detail="No WebM file found in the request.")

        # Create temporary file for the uploaded webm
        webm_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")
        logger.info(f"Created temporary file: {webm_temp.name}")

        try:
            # Save the uploaded webm to a temporary file
            content = webm_file.read()
            if len(content) == 0:
                logger.error("Uploaded file is empty")
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            
            webm_temp.write(content)
            webm_temp.close()
            logger.info(f"Saved {len(content)} bytes to temporary file")
            
            # Verify the input file is valid
            try:
                probe = ffmpeg.probe(webm_temp.name)
                logger.info(f"Input file info: {probe}")
                
                # Get video stream info
                video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                if video_info:
                    logger.info(f"Input video codec: {video_info.get('codec_name')}")
                    logger.info(f"Input video dimensions: {video_info.get('width')}x{video_info.get('height')}")
            except ffmpeg.Error as e:
                logger.error(f"Invalid input file: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Invalid input file: {str(e)}")
                
            logger.info(f"Successfully saved and verified WebM file: {webm_temp.name}")
            return {"webm_path": webm_temp.name, "compress": compress}
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            if os.path.exists(webm_temp.name):
                os.unlink(webm_temp.name)
                logger.info(f"Cleaned up temporary file: {webm_temp.name}")
            raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

    def predict(self, input_data):
        logger.info("Starting prediction")
        webm_path = input_data["webm_path"]
        compress = input_data["compress"]
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        logger.info(f"Output path: {output_path}")

        try:
            # First, try to get input file information
            probe = ffmpeg.probe(webm_path)
            video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            
            if not video_info:
                logger.error("No video stream found in input file")
                raise HTTPException(status_code=400, detail="No video stream found in input file")

            logger.info("Setting up encoding parameters")
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
                logger.info("Using compressed settings")
                # Compressed settings
                encoding_params.update({
                    'preset': 'slower',  # Better compression at cost of encoding time
                    'crf': '28',         # Higher CRF means more compression (range 0-51)
                    'video_bitrate': '800k',  # Lower bitrate for smaller file
                    'audio_bitrate': '96k',   # Lower audio bitrate
                    'g': '60',           # Longer GOP for better compression
                })
            else:
                logger.info("Using standard quality settings")
                # Standard quality settings (existing settings)
                encoding_params.update({
                    'preset': 'medium',
                    'video_bitrate': '2M',
                    'g': '30',
                    'force_key_frames': 'expr:gte(t,n_forced*2)'
                })

            # Convert WebM to MP4 using ffmpeg
            logger.info("Starting FFmpeg conversion")
            stream = ffmpeg.input(webm_path)
            stream = ffmpeg.output(stream, output_path, **encoding_params)

            # Get the ffmpeg command for debugging
            cmd = ffmpeg.compile(stream)
            logger.info(f"FFmpeg command: {' '.join(cmd)}")

            # Run the FFmpeg command
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            logger.info("FFmpeg conversion completed")

            # Verify the output file
            try:
                output_probe = ffmpeg.probe(output_path)
                logger.info(f"Output file info: {output_probe}")
            except ffmpeg.Error as e:
                logger.warning(f"Could not probe output file: {str(e)}")

            logger.info("FFmpeg conversion completed successfully")

            # Clean up temporary file
            os.unlink(webm_path)
            logger.info(f"Cleaned up temporary WebM file: {webm_path}")
            return output_path

        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
            if os.path.exists(output_path):
                os.unlink(output_path)
                logger.info(f"Cleaned up failed output file: {output_path}")
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        except Exception as e:
            logger.error(f"Error converting file: {str(e)}")
            if os.path.exists(output_path):
                os.unlink(output_path)
                logger.info(f"Cleaned up failed output file: {output_path}")
            raise HTTPException(status_code=500, detail=f"Error converting file: {str(e)}")

    def encode_response(self, output_path):
        try:
            logger.info(f"Encoding response with output path: {output_path}")
            # Read the content of the converted file
            with open(output_path, "rb") as f:
                content = f.read()
            logger.info(f"Read {len(content)} bytes from output file")
            
            # Remove the temporary converted file
            os.remove(output_path)
            logger.info(f"Removed temporary output file: {output_path}")
            
            # Return the response with the correct media type
            return Response(content=content, media_type="video/mp4")
        except Exception as e:
            logger.error(f"Error encoding response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error encoding response: {str(e)}")


# Run the LitServe server
if __name__ == "__main__":
    logger.info("Starting WebmToMP4 server")
    # Define the CORS settings
    cors_middleware = (
        CORSMiddleware, 
        {
            "allow_origins": [
                "https://singmesong.com",  # Add the exact domain
                "https://www.singmesong.com",
                "https://app.singmesong.com",
                "https://mp4.singmesong.com",
                "http://localhost:3000"
            ],
            "allow_methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["*"],
            "allow_credentials": True,
            "expose_headers": ["Content-Type", "Content-Disposition"]
        }
    )
    server = ls.LitServer(WebmToMP4API(), middlewares=[cors_middleware])
    logger.info("Server initialized, starting on port 8882")
    server.run(port=8882)