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
            
            # Download and process each scene's media
            scene_clips = []
            for i, scene in enumerate(scenes):
                try:
                    media_item = scene.get("mediaItem")
                    if not media_item or not media_item.get("url"):
                        logger.warning(f"Scene {i} has no media item or URL, skipping")
                        continue
                    
                    media_url = media_item.get("url")
                    media_type = media_item.get("type", "").lower()
                    start_time = scene.get("startTime", 0)
                    end_time = scene.get("endTime", 0)
                    
                    if end_time <= start_time:
                        logger.warning(f"Scene {i} has invalid timing (start: {start_time}, end: {end_time}), skipping")
                        continue
                    
                    # Download the media file
                    media_ext = os.path.splitext(media_url)[1].lower() or ".mp4"
                    if not media_ext.startswith("."):
                        media_ext = "." + media_ext
                    
                    media_path = os.path.join(temp_dir, f"scene_{i}{media_ext}")
                    logger.info(f"Downloading media for scene {i} from {media_url}")
                    
                    response = requests.get(media_url, stream=True)
                    response.raise_for_status()
                    
                    with open(media_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    # Create clip based on media type
                    if media_type == "image":
                        # For images, create a static clip with the specified duration
                        duration = end_time - start_time  # Already in seconds
                        logger.info(f"Creating image clip for scene {i} from {media_path} with duration {duration}s")
                        clip = ImageClip(media_path, duration=duration)
                        clip = clip.resize(width=width, height=height, resample='bicubic')
                    else:
                        # For videos, extract the portion between start and end times
                        logger.info(f"Creating video clip for scene {i} from {media_path}")
                        video_clip = VideoFileClip(media_path)
                        
                        # Calculate subclip times
                        clip_duration = end_time - start_time
                        # If the video is shorter than the requested duration, loop it
                        if video_clip.duration < clip_duration:
                            logger.info(f"Video clip is shorter than requested duration. Video: {video_clip.duration}s, Requested: {clip_duration}s")
                            # Use the entire video clip
                            clip = video_clip.resize(width=width, height=height)
                            # Set the duration to match the requested duration
                            clip = clip.set_duration(clip_duration)
                        else:
                            # Use the specified portion of the video
                            clip = video_clip.subclip(0, clip_duration)
                            clip = clip.resize(width=width, height=height)
                    
                    scene_clips.append(clip)
                    logger.info(f"Processed scene {i}: duration {clip.duration}s")
                    
                except Exception as e:
                    logger.error(f"Error processing scene {i}: {str(e)}")
                    # Continue with other scenes even if one fails
            
            if not scene_clips:
                raise HTTPException(status_code=400, detail="No valid scenes could be processed.")
            
            # Download the audio file
            audio_url = song.get("audioUrl")
            audio_path = os.path.join(temp_dir, "audio.mp3")
            logger.info(f"Downloading audio from {audio_url}")
            
            response = requests.get(audio_url, stream=True)
            response.raise_for_status()
            
            with open(audio_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Create the audio clip
            audio_clip = AudioFileClip(audio_path)
            
            # Concatenate all clips in sequence
            logger.info(f"Concatenating {len(scene_clips)} clips")
            final_clip = concatenate_videoclips(scene_clips, method="compose")
            
            # Add the audio
            final_clip = final_clip.set_audio(audio_clip)
            
            # Set the duration to match the audio if needed
            if final_clip.duration < audio_clip.duration:
                logger.info(f"Setting final clip duration to match audio: {audio_clip.duration}s")
                final_clip = final_clip.set_duration(audio_clip.duration)
            
            # Write the final video to a temporary file
            output_path = os.path.join(temp_dir, "final_video.mp4")
            logger.info(f"Writing final video to {output_path}")
            
            final_clip.write_videofile(
                output_path, 
                fps=fps, 
                codec="libx264", 
                audio_codec="aac",
                preset="medium",
                threads=4
            )
            
            # Clean up the clips to free memory
            final_clip.close()
            audio_clip.close()
            for clip in scene_clips:
                clip.close()
            
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