"""Content Generation Agent - Creates scripts based on trend patterns."""
import logging
from typing import List, Dict, Any

from openai import OpenAI

from config import settings
from models import TrendBlueprint, Script

logger = logging.getLogger(__name__)


class ContentGenerationAgent:
    """Generates new scripts following trend patterns."""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
    async def generate_script(
        self,
        blueprint: TrendBlueprint,
        brand_style: str = None
    ) -> Script:
        """
        Generate a new script based on trend blueprint.
        
        Args:
            blueprint: TrendBlueprint to follow
            brand_style: Optional brand/style to inject ("our spin")
            
        Returns:
            Script object
        """
        logger.info(f"Generating script for trend: {blueprint.trend_name}")
        
        # Build prompt from blueprint
        prompt = self._build_generation_prompt(blueprint, brand_style)
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating viral short-form video scripts. You understand trends, hooks, and what makes content engaging. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,  # Higher creativity
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            import json
            script_data = json.loads(result_text)
            
            # Convert to Script object
            script = Script(
                title=script_data.get("title", "Untitled Video"),
                script_text=script_data.get("script_text", ""),
                shot_list=script_data.get("shot_list", []),
                visual_style_instructions=script_data.get("visual_style_instructions", ""),
                camera_motion=script_data.get("camera_motion", []),
                dialogue=script_data.get("dialogue", []),
                caption_text=script_data.get("caption_text", []),
                estimated_duration=script_data.get("estimated_duration", blueprint.average_length),
                trend_blueprint_id=blueprint.trend_name
            )
            
            return script
            
        except Exception as e:
            logger.error(f"Error generating script: {e}")
            # Return fallback script
            return self._create_fallback_script(blueprint)
    
    def _build_generation_prompt(
        self, 
        blueprint: TrendBlueprint, 
        brand_style: str = None
    ) -> str:
        """Build the prompt for script generation."""
        prompt = f"""Create a viral short-form video script following this trend blueprint:

TREND: {blueprint.trend_name}
CATEGORY: {blueprint.trend_category.value}

PATTERN REQUIREMENTS:
- Average length: {blueprint.average_length} seconds
- Hook duration: {blueprint.hook_duration} seconds
- Common hook words: {', '.join(blueprint.hook_words[:5])}
- Common plot arcs: {', '.join(blueprint.common_plot_arcs)}
- Visual style: {blueprint.visual_style.get('style', 'unknown')}
- Character types: {', '.join(blueprint.character_types[:3])}
- Editing patterns: {blueprint.editing_timing_patterns.get('pacing', 'medium')} pacing
"""
        
        if blueprint.cta:
            prompt += f"- CTA: {blueprint.cta}\n"
        
        if blueprint.meme_archetype:
            prompt += f"- Meme archetype: {blueprint.meme_archetype}\n"
        
        if brand_style:
            prompt += f"\nBRAND STYLE (inject this into the content): {brand_style}\n"
        
        prompt += """
Create a complete script that:
1. Follows the trend pattern but adds originality
2. Has a strong hook in the first few seconds
3. Maintains engagement throughout
4. Includes visual and camera instructions
5. Has dialogue/captions that match the style

Respond with JSON in this exact format:
{
    "title": "Video title (engaging, clickable)",
    "script_text": "Full script text with scene descriptions",
    "shot_list": [
        {
            "shot_number": 1,
            "description": "Shot description",
            "duration": 2.5,
            "visual_elements": ["element1", "element2"],
            "camera_action": "camera instruction"
        }
    ],
    "visual_style_instructions": "Detailed visual style description",
    "camera_motion": ["instruction1", "instruction2"],
    "dialogue": [
        {
            "speaker": "Character or Narrator",
            "text": "Dialogue text",
            "timestamp": 0.0
        }
    ],
    "caption_text": ["Caption 1", "Caption 2"],
    "estimated_duration": 15.0
}"""
        
        return prompt
    
    def _create_fallback_script(self, blueprint: TrendBlueprint) -> Script:
        """Create a basic fallback script if generation fails."""
        return Script(
            title=f"{blueprint.trend_name.replace('_', ' ').title()} Video",
            script_text=f"Create a {blueprint.trend_category.value} video following the {blueprint.trend_name} trend.",
            shot_list=[
                {
                    "shot_number": 1,
                    "description": "Opening hook shot",
                    "duration": blueprint.hook_duration,
                    "visual_elements": [],
                    "camera_action": "static"
                }
            ],
            visual_style_instructions=blueprint.visual_style.get("style", "unknown"),
            camera_motion=["static"],
            dialogue=[],
            caption_text=[],
            estimated_duration=blueprint.average_length,
            trend_blueprint_id=blueprint.trend_name
        )

