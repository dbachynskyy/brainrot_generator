"""Production Agent - Orchestrates video generation using AI tools."""
import logging
import httpx
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from config import settings
from models import ProductionRequest, GeneratedVideo, Script, ReferenceFrame

logger = logging.getLogger(__name__)


class ProductionAgent:
    """Orchestrates video generation using various AI video generators."""
    
    def __init__(self, output_dir: str = "data/generated"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def generate_video(
        self,
        request: ProductionRequest
    ) -> GeneratedVideo:
        """
        Generate video from production request.
        
        Args:
            request: ProductionRequest with script and references
            
        Returns:
            GeneratedVideo object
        """
        logger.info(f"Generating video for script: {request.script.title}")
        
        # Select generator
        generator = request.generator_preference or self._select_best_generator(request)
        
        # Generate video based on selected generator
        if generator == "runway":
            video_path = await self._generate_with_runway(request)
        elif generator == "pika":
            video_path = await self._generate_with_pika(request)
        elif generator == "kling":
            video_path = await self._generate_with_kling(request)
        elif generator == "luma":
            video_path = await self._generate_with_luma(request)
        else:
            # Default to Pika for MVP
            video_path = await self._generate_with_pika(request)
        
        # Save plot/story structure to text file next to the video
        self._save_plot_to_file(video_path, request.script)
        
        return GeneratedVideo(
            video_path=str(video_path),
            script_id=request.script.title,
            generator_used=generator,
            generation_time=0.0,  # Would track actual time
            metadata={
                "script_title": request.script.title,
                "style_prompt": request.style_prompt,
                "reference_frames_count": len(request.reference_frames)
            }
        )
    
    def _select_best_generator(self, request: ProductionRequest) -> str:
        """Select the best generator based on request characteristics and available API keys."""
        script = request.script
        
        # Check which generators have API keys available
        available_generators = []
        if settings.runway_api_key:
            available_generators.append("runway")
        if settings.pika_api_key:
            available_generators.append("pika")
        if settings.kling_api_key:
            available_generators.append("kling")
        if settings.luma_api_key:
            available_generators.append("luma")
        
        # If no API keys available, default to pika (will create placeholder)
        if not available_generators:
            logger.warning("No video generation API keys found, will create placeholder videos")
            return "pika"
        
        # Check visual style to select best match from available generators
        visual_style = script.visual_style_instructions.lower()
        
        # Prefer generators that match the style AND have API keys
        if "realistic" in visual_style or "cinematic" in visual_style:
            if "runway" in available_generators:
                return "runway"
        elif "animated" in visual_style or "meme" in visual_style or "edit" in visual_style:
            if "pika" in available_generators:
                return "pika"
        elif "action" in visual_style or "dynamic" in visual_style:
            if "kling" in available_generators:
                return "kling"
        
        # Fallback: use first available generator
        logger.info(f"Using available generator: {available_generators[0]}")
        return available_generators[0]
    
    def _sanitize_filename(self, title: str) -> str:
        """Sanitize filename for Windows compatibility."""
        # Remove or replace invalid characters for Windows filenames
        invalid_chars = '<>:"/\\|?*!'
        safe_title = ''.join(c if c not in invalid_chars else '_' for c in title)
        # Remove leading/trailing spaces and dots
        safe_title = safe_title.strip(' .')
        # Limit length
        return safe_title[:100]
    
    def _save_plot_to_file(self, video_path: Path, script: Script):
        """Save plot/story structure to a text file next to the generated video."""
        try:
            # Create plot file path (same name as video but with .txt extension)
            plot_path = video_path.with_suffix('.txt')
            
            with open(plot_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("VIDEO SCRIPT & PLOT STRUCTURE\n")
                f.write("=" * 80 + "\n\n")
                
                f.write(f"TITLE: {script.title}\n\n")
                
                f.write("-" * 80 + "\n")
                f.write("SCRIPT TEXT\n")
                f.write("-" * 80 + "\n")
                f.write(f"{script.script_text}\n\n")
                
                f.write("-" * 80 + "\n")
                f.write("VISUAL STYLE INSTRUCTIONS\n")
                f.write("-" * 80 + "\n")
                f.write(f"{script.visual_style_instructions}\n\n")
                
                if script.camera_motion:
                    f.write("-" * 80 + "\n")
                    f.write("CAMERA MOTION\n")
                    f.write("-" * 80 + "\n")
                    for i, motion in enumerate(script.camera_motion, 1):
                        f.write(f"{i}. {motion}\n")
                    f.write("\n")
                
                if script.shot_list:
                    f.write("-" * 80 + "\n")
                    f.write("SHOT LIST\n")
                    f.write("-" * 80 + "\n")
                    for i, shot in enumerate(script.shot_list, 1):
                        f.write(f"\nShot {i}:\n")
                        if isinstance(shot, dict):
                            for key, value in shot.items():
                                f.write(f"  {key}: {value}\n")
                        else:
                            f.write(f"  {shot}\n")
                    f.write("\n")
                
                if script.dialogue:
                    f.write("-" * 80 + "\n")
                    f.write("DIALOGUE\n")
                    f.write("-" * 80 + "\n")
                    for i, line in enumerate(script.dialogue, 1):
                        if isinstance(line, dict):
                            speaker = line.get('speaker', 'Unknown')
                            text = line.get('text', '')
                            timestamp = line.get('timestamp', '')
                            f.write(f"{i}. [{timestamp}] {speaker}: {text}\n")
                        else:
                            f.write(f"{i}. {line}\n")
                    f.write("\n")
                
                if script.caption_text:
                    f.write("-" * 80 + "\n")
                    f.write("CAPTION TEXT\n")
                    f.write("-" * 80 + "\n")
                    for i, caption in enumerate(script.caption_text, 1):
                        f.write(f"{i}. {caption}\n")
                    f.write("\n")
                
                f.write("-" * 80 + "\n")
                f.write("METADATA\n")
                f.write("-" * 80 + "\n")
                f.write(f"Estimated Duration: {script.estimated_duration:.1f} seconds\n")
                if script.trend_blueprint_id:
                    f.write(f"Trend Blueprint ID: {script.trend_blueprint_id}\n")
            
            logger.info(f"Saved plot/story structure to: {plot_path}")
            
        except Exception as e:
            logger.error(f"Error saving plot to file: {e}", exc_info=True)
    
    def _image_to_data_uri(self, image_path: Path) -> str:
        """Convert an image file to a data URI for Runway API."""
        import base64
        
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Determine MIME type from extension
        ext = path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'image/jpeg')
        
        # Read and encode image
        with open(path, 'rb') as f:
            image_data = f.read()
        
        base64_data = base64.b64encode(image_data).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"
    
    async def _generate_with_runway(self, request: ProductionRequest) -> Path:
        """Generate video using Runway Gen-3 Alpha Turbo via image_to_video API."""
        logger.info("Generating with Runway Gen-3 Alpha Turbo")
        
        safe_title = self._sanitize_filename(request.script.title)
        output_path = self.output_dir / f"runway_{safe_title}.mp4"
        
        if not settings.runway_api_key:
            logger.warning("Runway API key not set, creating placeholder video")
            await self._create_placeholder_video(output_path, request.script)
            return output_path
        
        # Check if we have a reference frame (required for image_to_video)
        if not request.reference_frames:
            logger.warning("No reference frames available for Runway image_to_video. Creating placeholder.")
            await self._create_placeholder_video(output_path, request.script)
            return output_path
        
        try:
            # Use the first reference frame as the prompt image
            reference_frame = request.reference_frames[0]
            frame_path = Path(reference_frame.frame_path)
            
            if not frame_path.exists():
                logger.error(f"Reference frame not found: {frame_path}")
                await self._create_placeholder_video(output_path, request.script)
                return output_path
            
            # Convert image to data URI
            prompt_image_uri = self._image_to_data_uri(frame_path)
            logger.info(f"Using reference frame: {frame_path}")
            logger.warning(f"⚠️  WARNING: Reference frame is from a different video. Runway will try to transform this image to match the script, but results may not match perfectly.")
            
            # Build prompt text - make it very descriptive to help Runway transform the image
            prompt_text = self._build_runway_prompt(request)
            
            # Enhance prompt to be more explicit about transformation
            enhanced_prompt = f"Transform this scene to show: {prompt_text}. The image is a starting reference - create a new scene that matches the description."
            prompt_text = enhanced_prompt
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                headers = {
                    "Authorization": f"Bearer {settings.runway_api_key}",
                    "Content-Type": "application/json",
                    "X-Runway-Version": "2024-11-06"  # Exact version required by Runway API
                }
                
                # Calculate duration (must be between 2-10 seconds)
                duration = max(2, min(int(request.script.estimated_duration or 5), 10))
                
                payload = {
                    "model": "gen3a_turbo",
                    "promptImage": prompt_image_uri,  # Required: data URI or HTTPS URL
                    "promptText": prompt_text,  # Optional description
                    "ratio": "768:1280",  # Vertical for Shorts (must be exact format per API: "768:1280" or "1280:768")
                    "duration": duration
                }
                
                # Log payload details (without full base64 image)
                logger.info("=" * 80)
                logger.info("RUNWAY API PAYLOAD SANITY CHECK")
                logger.info("=" * 80)
                logger.info(f"Model: {payload['model']}")
                logger.info(f"Prompt Image: {frame_path} (converted to data URI, length: {len(prompt_image_uri)} chars)")
                logger.info(f"Prompt Text: {prompt_text[:200]}..." if len(prompt_text) > 200 else f"Prompt Text: {prompt_text}")
                logger.info(f"Ratio: {payload['ratio']}")
                logger.info(f"Duration: {payload['duration']} seconds")
                logger.info(f"Script Title: {request.script.title}")
                logger.info(f"Script Text: {request.script.script_text[:200]}..." if len(request.script.script_text) > 200 else f"Script Text: {request.script.script_text}")
                logger.info(f"Visual Style: {request.script.visual_style_instructions[:200]}..." if len(request.script.visual_style_instructions) > 200 else f"Visual Style: {request.script.visual_style_instructions}")
                logger.info(f"Reference Frame Source: {frame_path}")
                logger.info("=" * 80)
                
                logger.info(f"Submitting Runway image_to_video request (duration: {duration}s)...")
                response = await client.post(
                    "https://api.dev.runwayml.com/v1/image_to_video",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error(f"Runway API error: {response.status_code} - {response.text}")
                    await self._create_placeholder_video(output_path, request.script)
                    return output_path
                
                result = response.json()
                task_id = result.get("id")
                
                if not task_id:
                    logger.error(f"Runway API did not return task ID: {result}")
                    await self._create_placeholder_video(output_path, request.script)
                    return output_path
                
                # Poll for completion using /v1/tasks/{id}
                logger.info(f"Polling for Runway task {task_id}...")
                video_url = await self._poll_runway_generation(client, headers, task_id)
                
                if video_url:
                    # Download the video
                    logger.info(f"Downloading video from {video_url}")
                    video_response = await client.get(video_url)
                    if video_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(video_response.content)
                        logger.info(f"Successfully generated video: {output_path}")
                        return output_path
                    else:
                        logger.error(f"Failed to download video: {video_response.status_code}")
                else:
                    logger.error("Video generation timed out or failed")
                
        except Exception as e:
            logger.error(f"Error generating video with Runway: {e}", exc_info=True)
        
        # Fallback to placeholder
        await self._create_placeholder_video(output_path, request.script)
        return output_path
    
    def _build_runway_prompt(self, request: ProductionRequest) -> str:
        """Build a detailed prompt for Runway from the production request."""
        script = request.script
        
        # Build a comprehensive prompt that describes the scene
        prompt_parts = []
        
        # Start with the main script/story
        if script.script_text:
            prompt_parts.append(f"Scene: {script.script_text}")
        
        # Add visual style details
        if script.visual_style_instructions:
            prompt_parts.append(f"Visual style: {script.visual_style_instructions}")
        
        # Add camera motion if specified
        if request.camera_motion_instructions:
            prompt_parts.append(f"Camera movement: {request.camera_motion_instructions}")
        
        # Add shot descriptions if available
        if script.shot_list:
            shot_descriptions = []
            for shot in script.shot_list[:3]:  # Limit to first 3 shots
                if isinstance(shot, dict):
                    desc = shot.get('description', '')
                    if desc:
                        shot_descriptions.append(desc)
                elif isinstance(shot, str):
                    shot_descriptions.append(shot)
            if shot_descriptions:
                prompt_parts.append(f"Key moments: {'; '.join(shot_descriptions)}")
        
        # Combine all parts
        prompt = ". ".join(prompt_parts)
        
        # Ensure prompt is descriptive but not too long
        if len(prompt) > 500:
            prompt = prompt[:500] + "..."
        
        # If prompt is too short, add more context
        if len(prompt) < 50:
            prompt = f"{script.title}. {script.script_text[:200]}"
        
        return prompt
    
    async def _poll_runway_generation(
        self, 
        client: httpx.AsyncClient, 
        headers: dict, 
        task_id: str,
        max_attempts: int = 60,
        poll_interval: int = 5
    ) -> Optional[str]:
        """Poll Runway API for task completion using /v1/tasks/{id} endpoint."""
        for attempt in range(max_attempts):
            try:
                response = await client.get(
                    f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.warning(f"Polling error: {response.status_code} - {response.text}")
                    await asyncio.sleep(poll_interval)
                    continue
                
                task = response.json()
                status = task.get("status", "").upper()  # RUNNING, SUCCEEDED, FAILED, etc.
                
                if status == "SUCCEEDED":
                    # Extract video URL from task output
                    output = task.get("output")
                    if isinstance(output, list) and len(output) > 0:
                        video_url = output[0]
                    elif isinstance(output, str):
                        video_url = output
                    elif isinstance(output, dict):
                        video_url = output.get("url") or output.get("videoUrl")
                    else:
                        logger.error(f"Unexpected output format: {output}")
                        return None
                    
                    if video_url:
                        logger.info(f"Task succeeded, video URL: {video_url}")
                        return video_url
                    else:
                        logger.error(f"Task succeeded but no video URL in output: {task}")
                        return None
                
                elif status in ["FAILED", "CANCELLED", "THROTTLED"]:
                    error_msg = task.get("error", f"Task failed with status: {status}")
                    logger.error(f"Runway task failed: {error_msg}")
                    return None
                
                # Still processing (RUNNING, PENDING, etc.)
                logger.debug(f"Task status: {status} (attempt {attempt + 1}/{max_attempts})")
                await asyncio.sleep(poll_interval)
                    
            except Exception as e:
                logger.warning(f"Error polling Runway: {e}")
                await asyncio.sleep(poll_interval)
        
        logger.error(f"Generation timed out after {max_attempts} attempts")
        return None
    
    async def _generate_with_pika(self, request: ProductionRequest) -> Path:
        """Generate video using Pika API."""
        logger.info("Generating with Pika")
        
        safe_title = self._sanitize_filename(request.script.title)
        output_path = self.output_dir / f"pika_{safe_title}.mp4"
        
        if not settings.pika_api_key:
            logger.warning("Pika API key not set, creating placeholder video")
            await self._create_placeholder_video(output_path, request.script)
            return output_path
        
        try:
            # Pika API integration
            # API endpoint: https://api.pika.art/v1/generate
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Prepare the prompt from script
                prompt = self._build_pika_prompt(request)
                
                # Submit generation request
                headers = {
                    "Authorization": f"Bearer {settings.pika_api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "promptText": prompt,
                    "model": "1.5",  # Use Pika 1.5 model
                    "options": {
                        "aspectRatio": "9:16",  # Vertical for Shorts
                        "frameRate": 24,
                        "camera": {
                            "rotate": None,
                            "zoom": None,
                            "tilt": None,
                            "pan": None
                        },
                        "parameters": {
                            "guidanceScale": 12,
                            "motion": 1,
                            "negativePrompt": "",
                            "seed": None
                        },
                        "extend": False
                    }
                }
                
                logger.info(f"Submitting Pika generation request: {prompt[:100]}...")
                response = await client.post(
                    "https://api.pika.art/v1/generate",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    logger.error(f"Pika API error: {response.status_code} - {response.text}")
                    await self._create_placeholder_video(output_path, request.script)
                    return output_path
                
                result = response.json()
                generation_id = result.get("id")
                
                if not generation_id:
                    logger.error(f"Pika API did not return generation ID: {result}")
                    await self._create_placeholder_video(output_path, request.script)
                    return output_path
                
                # Poll for completion
                logger.info(f"Polling for Pika generation {generation_id}...")
                video_url = await self._poll_pika_generation(client, headers, generation_id)
                
                if video_url:
                    # Download the video
                    logger.info(f"Downloading video from {video_url}")
                    video_response = await client.get(video_url)
                    if video_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(video_response.content)
                        logger.info(f"Successfully generated video: {output_path}")
                        return output_path
                    else:
                        logger.error(f"Failed to download video: {video_response.status_code}")
                else:
                    logger.error("Video generation timed out or failed")
                
        except Exception as e:
            logger.error(f"Error generating video with Pika: {e}", exc_info=True)
        
        # Fallback to placeholder
        await self._create_placeholder_video(output_path, request.script)
        return output_path
    
    def _build_pika_prompt(self, request: ProductionRequest) -> str:
        """Build a prompt for Pika from the production request."""
        script = request.script
        
        # Combine style prompt, script text, and camera instructions
        prompt_parts = []
        
        if request.style_prompt:
            prompt_parts.append(request.style_prompt)
        
        if script.script_text:
            # Extract key visual elements from script
            prompt_parts.append(script.script_text[:200])
        
        if script.visual_style_instructions:
            prompt_parts.append(f"Style: {script.visual_style_instructions}")
        
        if request.camera_motion_instructions:
            prompt_parts.append(f"Camera: {request.camera_motion_instructions}")
        
        prompt = ". ".join(prompt_parts)
        
        # Limit prompt length (Pika has limits)
        if len(prompt) > 500:
            prompt = prompt[:500] + "..."
        
        return prompt
    
    async def _poll_pika_generation(
        self, 
        client: httpx.AsyncClient, 
        headers: dict, 
        generation_id: str,
        max_attempts: int = 60,
        poll_interval: int = 5
    ) -> Optional[str]:
        """Poll Pika API for generation completion."""
        for attempt in range(max_attempts):
            try:
                response = await client.get(
                    f"https://api.pika.art/v1/generate/{generation_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status", "pending")
                    
                    if status == "completed":
                        video_url = result.get("videoUrl") or result.get("url")
                        if video_url:
                            return video_url
                    
                    elif status == "failed":
                        logger.error(f"Pika generation failed: {result.get('error', 'Unknown error')}")
                        return None
                    
                    # Still processing
                    logger.debug(f"Generation status: {status} (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(poll_interval)
                else:
                    logger.warning(f"Polling error: {response.status_code}")
                    await asyncio.sleep(poll_interval)
                    
            except Exception as e:
                logger.warning(f"Error polling Pika: {e}")
                await asyncio.sleep(poll_interval)
        
        logger.error(f"Generation timed out after {max_attempts} attempts")
        return None
    
    async def _generate_with_kling(self, request: ProductionRequest) -> Path:
        """Generate video using Kling AI."""
        logger.info("Generating with Kling AI")
        
        safe_title = self._sanitize_filename(request.script.title)
        output_path = self.output_dir / f"kling_{safe_title}.mp4"
        
        if not settings.kling_api_key:
            logger.warning("Kling API key not set, creating placeholder video")
            await self._create_placeholder_video(output_path, request.script)
        else:
            # TODO: Implement actual Kling API call when API documentation is available
            logger.info("Kling API integration not yet implemented - using placeholder")
            await self._create_placeholder_video(output_path, request.script)
        
        return output_path
    
    async def _generate_with_luma(self, request: ProductionRequest) -> Path:
        """Generate video using Luma Dream Machine 2."""
        logger.info("Generating with Luma Dream Machine 2")
        
        safe_title = self._sanitize_filename(request.script.title)
        output_path = self.output_dir / f"luma_{safe_title}.mp4"
        
        if not settings.luma_api_key:
            logger.warning("Luma API key not set, creating placeholder video")
            await self._create_placeholder_video(output_path, request.script)
        else:
            # TODO: Implement actual Luma API call when API documentation is available
            logger.info("Luma API integration not yet implemented - using placeholder")
            await self._create_placeholder_video(output_path, request.script)
        
        return output_path
    
    async def _create_placeholder_video(self, output_path: Path, script: Script):
        """Create a minimal valid MP4 placeholder video."""
        try:
            # Try using moviepy to create a simple test video
            try:
                from moviepy.editor import ColorClip, TextClip, CompositeVideoClip
                
                # Create a simple colored video with text
                duration = min(script.estimated_duration or 5.0, 10.0)
                video = ColorClip(size=(640, 480), color=(30, 30, 30), duration=duration)
                
                # Add title text
                if script.title:
                    txt_clip = TextClip(
                        script.title[:50], 
                        fontsize=40, 
                        color='white',
                        font='Arial-Bold'
                    ).set_position('center').set_duration(duration)
                    video = CompositeVideoClip([video, txt_clip])
                
                video.write_videofile(
                    str(output_path),
                    fps=24,
                    codec='libx264',
                    audio=False,
                    logger=None
                )
                logger.info(f"Created placeholder video: {output_path}")
            except ImportError:
                # Fallback: create a minimal MP4 using ffmpeg if available
                import subprocess
                try:
                    # Create a simple black video using ffmpeg
                    duration = min(script.estimated_duration or 5.0, 10.0)
                    cmd = [
                        'ffmpeg', '-y',
                        '-f', 'lavfi',
                        '-i', f'color=c=black:s=640x480:d={duration}',
                        '-c:v', 'libx264',
                        '-pix_fmt', 'yuv420p',
                        str(output_path)
                    ]
                    subprocess.run(cmd, capture_output=True, check=True)
                    logger.info(f"Created placeholder video using ffmpeg: {output_path}")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Last resort: create empty file with note
                    logger.warning("Cannot create video - ffmpeg/moviepy not available. Creating empty placeholder.")
                    output_path.touch()
                    # Write a note file
                    note_path = output_path.with_suffix('.txt')
                    with open(note_path, 'w') as f:
                        f.write(f"Placeholder for: {script.title}\n")
                        f.write(f"Script: {script.script_text[:200]}\n")
                        f.write("\nNote: Video generation APIs not yet integrated.\n")
                        f.write("This is a placeholder file. Integrate Pika/Runway/Kling/Luma APIs to generate actual videos.")
        except Exception as e:
            logger.error(f"Error creating placeholder video: {e}")
            output_path.touch()  # At least create the file
    
    async def add_subtitles(
        self,
        video_path: Path,
        script: Script
    ) -> Path:
        """Add subtitles to generated video."""
        logger.info(f"Adding subtitles to {video_path}")
        
        # Use ffmpeg or moviepy to add subtitles
        # For MVP, this is a placeholder
        output_path = self.output_dir / f"{video_path.stem}_subtitled.mp4"
        
        # TODO: Implement subtitle overlay using ffmpeg
        # Example: ffmpeg -i input.mp4 -vf "subtitles=subtitles.srt" output.mp4
        
        return output_path

