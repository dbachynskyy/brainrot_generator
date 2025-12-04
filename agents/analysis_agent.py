"""Analysis Agent - Analyzes video content using LLMs."""
import logging
from typing import Dict, Any
import json

from openai import OpenAI

from config import settings
from models import VideoAnalysis, VideoMetadata, TranscriptSegment, HookType, TrendCategory

logger = logging.getLogger(__name__)


class AnalysisAgent:
    """Analyzes video content to extract patterns and styles."""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
    async def analyze_video(
        self,
        video: VideoMetadata,
        transcript: list[TranscriptSegment],
        reference_frames: list = None
    ) -> VideoAnalysis:
        """
        Analyze video content comprehensively.
        
        Args:
            video: Video metadata
            transcript: List of transcript segments
            reference_frames: List of reference frame paths/descriptions
            
        Returns:
            VideoAnalysis object
        """
        logger.info(f"Analyzing video: {video.video_id}")
        
        # Combine transcript text
        transcript_text = " ".join([seg.text for seg in transcript])
        
        # Analyze hook
        hook_analysis = await self._analyze_hook(transcript, video.title)
        
        # Analyze plot structure
        plot_analysis = await self._analyze_plot(transcript_text, video.description)
        
        # Analyze visual style (from description and metadata)
        visual_analysis = await self._analyze_visual_style(
            video.description, 
            reference_frames or []
        )
        
        # Analyze characters
        character_analysis = await self._analyze_characters(transcript_text, video.description)
        
        # Determine trend category
        trend_category = await self._classify_trend_category(
            transcript_text, 
            video.description,
            hook_analysis
        )
        
        # Analyze audio style
        audio_style = await self._analyze_audio_style(transcript_text, video.description)
        
        # Build analysis result
        # Ensure plot_structure is a string (handle case where LLM returns dict)
        plot_structure = plot_analysis.get("structure", "")
        if isinstance(plot_structure, dict):
            # Convert dict to string representation
            import json
            plot_structure = json.dumps(plot_structure, indent=2)
        elif not isinstance(plot_structure, str):
            plot_structure = str(plot_structure)
        
        analysis = VideoAnalysis(
            video_id=video.video_id,
            hook_type=hook_analysis.get("type", HookType.OTHER),
            hook_text=hook_analysis.get("text"),
            hook_duration=hook_analysis.get("duration", 0.0),
            plot_structure=plot_structure,
            story_arc=plot_analysis.get("arc", ""),
            tone=plot_analysis.get("tone", ""),
            emotion=plot_analysis.get("emotion", ""),
            visual_style=visual_analysis.get("style", ""),
            color_palette=visual_analysis.get("colors", []),
            framing_style=visual_analysis.get("framing", ""),
            camera_motion=visual_analysis.get("camera", ""),
            character_aesthetics=character_analysis.get("aesthetics", []),
            character_roles=character_analysis.get("roles", []),
            trend_category=trend_category,
            audio_style=audio_style,
            transcript=transcript,
            identified_patterns={
                "hook_analysis": hook_analysis,
                "plot_analysis": plot_analysis,
                "visual_analysis": visual_analysis,
                "character_analysis": character_analysis
            }
        )
        
        return analysis
    
    async def _analyze_hook(
        self, 
        transcript: list[TranscriptSegment], 
        title: str
    ) -> Dict[str, Any]:
        """Analyze the hook of the video."""
        # Get first few seconds of transcript
        hook_segments = [seg for seg in transcript if seg.start_time < 3.0]
        hook_text = " ".join([seg.text for seg in hook_segments])
        
        prompt = f"""Analyze the hook of this video. The title is: "{title}"
        
First 3 seconds of transcript: "{hook_text}"

Determine:
1. Hook type (shock, relatable_moment, motivational, funny_pov, question, visual_shock, other)
2. Hook text (the actual hook phrase)
3. Hook duration in seconds

Respond in JSON format:
{{
    "type": "hook_type",
    "text": "hook text",
    "duration": 2.5,
    "reasoning": "why this is the hook"
}}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing viral video hooks. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Error analyzing hook: {e}")
        
        return {"type": HookType.OTHER, "text": hook_text[:50], "duration": 2.0}
    
    async def _analyze_plot(
        self, 
        transcript_text: str, 
        description: str
    ) -> Dict[str, Any]:
        """Analyze plot structure and story arc."""
        prompt = f"""Analyze the plot structure of this video:

Description: "{description}"
Transcript: "{transcript_text[:1000]}"

Determine:
1. Plot structure - Provide a TEXT DESCRIPTION of the plot structure (setup, conflict, resolution, etc.). This must be a STRING, not an object.
2. Story arc type - The type of story arc
3. Overall tone - The tone of the video
4. Primary emotion - The primary emotion conveyed

IMPORTANT: The "structure" field must be a STRING description, not a JSON object.

Respond in JSON:
{{
    "structure": "A clear text description of the plot structure as a single string",
    "arc": "story arc type",
    "tone": "tone description",
    "emotion": "primary emotion"
}}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing video narratives. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            result_text = response.choices[0].message.content
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Error analyzing plot: {e}")
        
        return {
            "structure": "unknown",
            "arc": "unknown",
            "tone": "neutral",
            "emotion": "neutral"
        }
    
    async def _analyze_visual_style(
        self, 
        description: str, 
        reference_frames: list
    ) -> Dict[str, Any]:
        """Analyze visual style."""
        prompt = f"""Based on this video description, analyze the visual style:

Description: "{description}"

Determine:
1. Visual style (anime, real footage, skit, sigma edit, meme-style captions, etc.)
2. Color palette (list main colors)
3. Framing style (close-up, wide shot, etc.)
4. Camera motion (static, pan, zoom, etc.)

Respond in JSON:
{{
    "style": "visual style",
    "colors": ["color1", "color2"],
    "framing": "framing style",
    "camera": "camera motion"
}}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing visual styles. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            result_text = response.choices[0].message.content
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Error analyzing visual style: {e}")
        
        return {
            "style": "unknown",
            "colors": [],
            "framing": "unknown",
            "camera": "static"
        }
    
    async def _analyze_characters(
        self, 
        transcript_text: str, 
        description: str
    ) -> Dict[str, Any]:
        """Analyze characters and their aesthetics."""
        prompt = f"""Analyze the characters in this video:

Description: "{description}"
Transcript: "{transcript_text[:1000]}"

Determine:
1. Character aesthetics (list descriptive terms)
2. Character roles (protagonist, antagonist, etc.)

Respond in JSON:
{{
    "aesthetics": ["aesthetic1", "aesthetic2"],
    "roles": ["role1", "role2"]
}}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing characters. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            result_text = response.choices[0].message.content
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Error analyzing characters: {e}")
        
        return {
            "aesthetics": [],
            "roles": []
        }
    
    async def _classify_trend_category(
        self, 
        transcript_text: str, 
        description: str,
        hook_analysis: Dict[str, Any]
    ) -> TrendCategory:
        """Classify the trend category."""
        prompt = f"""Classify this video into a trend category:

Description: "{description}"
Hook: "{hook_analysis.get('text', '')}"
Transcript snippet: "{transcript_text[:500]}"

Categories: motivational, gaming, animated_skits, sigma_edits, funny_pov, relationship, meme, other

Respond with ONLY the category name (lowercase, no quotes)."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at classifying viral video trends. Respond with only the category name."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            category = response.choices[0].message.content.strip().lower()
            # Remove quotes if present
            category = category.strip('"\'')
            
            try:
                return TrendCategory(category)
            except ValueError:
                return TrendCategory.OTHER
        except Exception as e:
            logger.error(f"Error classifying trend: {e}")
        
        return TrendCategory.OTHER
    
    async def _analyze_audio_style(
        self, 
        transcript_text: str, 
        description: str
    ) -> str:
        """Analyze audio style."""
        prompt = f"""Describe the audio style of this video:

Description: "{description}"
Transcript: "{transcript_text[:500]}"

Respond with a brief description of the audio style (e.g., "energetic music with voiceover", "dialogue-heavy", "background music only", etc.)."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing audio styles."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error analyzing audio style: {e}")
        
        return "unknown"

