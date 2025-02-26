import litserve as ls
import os
import tempfile
import json
import requests
from fastapi import Response, HTTPException
import ffmpeg
from starlette.middleware.cors import CORSMiddleware
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, concatenate_videoclips
import logging
from datetime import datetime
import concurrent.futures
import subprocess

# Set up logging
log_dir = "./logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"video_scene_composer_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VideoSceneComposerAPI(ls.LitAPI):
    def setup(self, device):
        # No specific setup needed for this server
        pass

    def decode_request(self, request):
        try:
            # Get the JSON data from the request
            # Check if scenes are directly in the request
            if "scenes" in request:
                project_data = request
            else:
                # Fallback to check for project key for backward compatibility
                project_data = request.get("project", {})
                if isinstance(project_data, str):
                    project_data = json.loads(project_data)
            
            if not project_data.get("scenes"):
                raise HTTPException(status_code=400, detail="No scenes found in the request.")
                
            logger.info(f"Received project with {len(project_data.get('scenes', []))} scenes")
            return project_data
        except Exception as e:
            logger.error(f"Error decoding request: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error processing request: {str(e)}")

    def predict(self, project_data):
        try:
            scenes = project_data.get("scenes", [])
            song = project_data.get("song")
            config = project_data.get("config", {})
            
            if not scenes:
                raise HTTPException(status_code=400, detail="No scenes found in the project data.")
            
            if not song or not song.get("audioUrl"):
                raise HTTPException(status_code=400, detail="No song or audio URL found in the project data.")
            
            # Get configuration parameters
            width = config.get("width", 1920)
            height = config.get("height", 1080)
            fps = config.get("fps", 30)
            
            # Create a temporary directory for downloaded files
            temp_dir = tempfile.mkdtemp()
            logger.info(f"Created temporary directory: {temp_dir}")
            
            # Sort scenes by start time to ensure proper ordering
            scenes = sorted(scenes, key=lambda x: x.get("startTime", 0))
            
            # Download the audio file first
            audio_url = song.get("audioUrl")
            audio_path = os.path.join(temp_dir, "audio.mp3")
            logger.info(f"Downloading audio from {audio_url}")
            
            response = requests.get(audio_url, stream=True)
            response.raise_for_status()
            
            with open(audio_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Process each scene and create a list of input files for ffmpeg
            scene_files = []
            concat_file_content = []
            
            def process_scene(scene_data):
                i, scene = scene_data
                try:
                    media_item = scene.get("mediaItem")
                    if not media_item or not media_item.get("url"):
                        logger.warning(f"Scene {i} has no media item or URL, skipping")
                        return None
                    
                    media_url = media_item.get("url")
                    media_type = media_item.get("type", "").lower()
                    start_time = scene.get("startTime", 0)
                    end_time = scene.get("endTime", 0)
                    
                    if end_time <= start_time:
                        logger.warning(f"Scene {i} has invalid timing (start: {start_time}, end: {end_time}), skipping")
                        return None
                    
                    # Download the media file
                    media_ext = os.path.splitext(media_url)[1].lower() or ".mp4"
                    if not media_ext.startswith("."):
                        media_ext = "." + media_ext
                    
                    media_path = os.path.join(temp_dir, f"scene_{i}_original{media_ext}")
                    processed_path = os.path.join(temp_dir, f"scene_{i}_processed.mp4")
                    
                    logger.info(f"Downloading media for scene {i} from {media_url}")
                    
                    response = requests.get(media_url, stream=True)
                    response.raise_for_status()
                    
                    with open(media_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Process based on media type
                    clip_duration = end_time - start_time
                    
                    if media_type == "image":
                        # For images, use ffmpeg to create a video from the image
                        logger.info(f"Creating video from image for scene {i} with duration {clip_duration}s")
                        
                        ffmpeg.input(media_path, loop=1, t=clip_duration).filter(
                            'scale', width, height
                        ).output(
                            processed_path, 
                            vcodec='libx264', 
                            pix_fmt='yuv420p', 
                            r=fps,
                            preset='ultrafast'
                        ).run(overwrite_output=True, quiet=True)
                        
                    else:
                        # For videos, extract the portion between start and end times
                        logger.info(f"Processing video for scene {i} with duration {clip_duration}s")
                        
                        # Get video info
                        probe = ffmpeg.probe(media_path)
                        video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
                        
                        if video_info:
                            video_duration = float(video_info.get('duration', 0))
                            
                            if video_duration < clip_duration:
                                # If video is shorter than needed, we need to loop it
                                logger.info(f"Video is shorter than needed duration. Looping video.")
                                
                                # Create a temporary file with the video repeated multiple times
                                temp_concat_file = os.path.join(temp_dir, f"concat_{i}.txt")
                                repeats = int(clip_duration / video_duration) + 1
                                
                                with open(temp_concat_file, 'w') as f:
                                    for _ in range(repeats):
                                        f.write(f"file '{media_path}'\n")
                                
                                # Concatenate the repeated videos and then cut to exact duration
                                ffmpeg.input(temp_concat_file, format='concat', safe=0).output(
                                    processed_path,
                                    t=clip_duration,
                                    vcodec='libx264',
                                    preset='ultrafast',
                                    r=fps,
                                    s=f"{width}x{height}"
                                ).run(overwrite_output=True, quiet=True)
                                
                            else:
                                # Just cut the video to the needed duration
                                ffmpeg.input(media_path).output(
                                    processed_path,
                                    t=clip_duration,
                                    vcodec='libx264',
                                    preset='ultrafast',
                                    r=fps,
                                    s=f"{width}x{height}"
                                ).run(overwrite_output=True, quiet=True)
                        else:
                            logger.warning(f"Could not get video info for scene {i}")
                            return None
                    
                    return {
                        "index": i,
                        "path": processed_path,
                        "duration": clip_duration
                    }
                    
                except Exception as e:
                    logger.error(f"Error processing scene {i}: {str(e)}")
                    return None
            
            # Process scenes in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(scenes))) as executor:
                results = list(executor.map(process_scene, enumerate(scenes)))
            
            # Filter out None results and sort by original index
            processed_scenes = [r for r in results if r is not None]
            processed_scenes.sort(key=lambda x: x["index"])
            
            if not processed_scenes:
                raise HTTPException(status_code=400, detail="No valid scenes could be processed.")
            
            # Create a concat file for ffmpeg
            concat_file = os.path.join(temp_dir, "concat.txt")
            with open(concat_file, 'w') as f:
                for scene in processed_scenes:
                    f.write(f"file '{scene['path']}'\n")
            
            # Concatenate all videos and add audio
            logger.info(f"Concatenating {len(processed_scenes)} clips and adding audio")
            
            # First concatenate the videos
            temp_video_path = os.path.join(temp_dir, "temp_video_no_audio.mp4")
            ffmpeg.input(concat_file, format='concat', safe=0).output(
                temp_video_path,
                c='copy'
            ).run(overwrite_output=True, quiet=True)
            
            # Then add the audio - using a different approach with direct command construction
            output_path = os.path.join(temp_dir, "final_video.mp4")
            
            # Create the ffmpeg command as a list of arguments
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', temp_video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                output_path,
                '-y'  # Overwrite output file if it exists
            ]
            
            # Run the command
            logger.info(f"Running ffmpeg command: {' '.join(ffmpeg_cmd)}")
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            logger.info("Video composition completed successfully")
            return output_path
            
        except Exception as e:
            logger.error(f"Error in predict: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating video: {str(e)}")

    def encode_response(self, output_path):
        try:
            logger.info(f"Encoding response with output path: {output_path}")
            # Read the content of the merged file
            with open(output_path, "rb") as f:
                content = f.read()
            
            # Clean up temporary files
            temp_dir = os.path.dirname(output_path)
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {str(e)}")
            
            try:
                os.rmdir(temp_dir)
            except Exception as e:
                logger.error(f"Error removing temporary directory {temp_dir}: {str(e)}")
            
            # Return the response with the correct media type
            return Response(content=content, media_type="video/mp4")
        except Exception as e:
            logger.error(f"Error in encode_response: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error encoding response: {str(e)}")

# Run the LitServe server
if __name__ == "__main__":
    try:
        logger.info("Starting Video Scene Composer Server")
        # Define the CORS settings
        cors_middleware = (
            CORSMiddleware, 
            {
                "allow_origins": ["https://*.singmesong.com", "http://localhost:3000"],
                "allow_methods": ["GET", "POST"],
                "allow_headers": ["*"],
            }
        )
        server = ls.LitServer(VideoSceneComposerAPI(), middlewares=[cors_middleware], timeout=300)
        logger.info("Server initialized, starting on port 8890")
        server.run(port=8890)
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}")
        raise 