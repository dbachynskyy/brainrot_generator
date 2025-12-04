"""Pattern Agent - Identifies patterns and creates trend blueprints."""
import logging
import json
from typing import List, Dict, Any
from collections import Counter, defaultdict
import statistics

from openai import OpenAI

from config import settings
from models import VideoAnalysis, TrendBlueprint, TrendCategory

logger = logging.getLogger(__name__)


class PatternAgent:
    """Identifies patterns across multiple videos and creates trend blueprints."""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        
    async def identify_patterns(
        self, 
        analyses: List[VideoAnalysis]
    ) -> List[TrendBlueprint]:
        """
        Identify patterns across multiple video analyses.
        
        Args:
            analyses: List of VideoAnalysis objects
            
        Returns:
            List of TrendBlueprint objects
        """
        logger.info(f"Identifying patterns from {len(analyses)} video analyses")
        
        # Group by trend category
        by_category = defaultdict(list)
        for analysis in analyses:
            by_category[analysis.trend_category].append(analysis)
        
        blueprints = []
        
        # Create blueprint for each category with enough samples
        for category, category_analyses in by_category.items():
            if len(category_analyses) >= 3:  # Need at least 3 videos to identify patterns
                blueprint = await self._create_blueprint(category, category_analyses)
                blueprints.append(blueprint)
        
        return blueprints
    
    async def _create_blueprint(
        self, 
        category: TrendCategory, 
        analyses: List[VideoAnalysis]
    ) -> TrendBlueprint:
        """Create a trend blueprint from analyses."""
        # Calculate average metrics
        hook_durations = [a.hook_duration for a in analyses if a.hook_duration > 0]
        avg_hook_duration = statistics.mean(hook_durations) if hook_durations else 2.5
        
        # Extract common hook words
        hook_texts = [a.hook_text for a in analyses if a.hook_text]
        hook_words = self._extract_common_words(hook_texts, top_n=10)
        
        # Extract common plot arcs
        plot_arcs = [a.story_arc for a in analyses if a.story_arc]
        common_arcs = Counter(plot_arcs).most_common(3)
        
        # Analyze visual styles
        visual_styles = [a.visual_style for a in analyses]
        common_style = Counter(visual_styles).most_common(1)[0][0] if visual_styles else "unknown"
        
        # Extract character types
        all_characters = []
        for analysis in analyses:
            all_characters.extend(analysis.character_roles)
        common_characters = [char for char, count in Counter(all_characters).most_common(5)]
        
        # Analyze editing patterns using LLM
        editing_patterns = await self._analyze_editing_patterns(analyses)
        
        # Determine CTA and meme archetype
        cta_analysis = await self._analyze_cta(analyses)
        
        # Calculate confidence score
        confidence = min(len(analyses) / 10.0, 1.0)  # More samples = higher confidence
        
        # Ensure cta and meme_archetype are strings (handle case where LLM returns list/dict)
        cta = cta_analysis.get("cta", "")
        if isinstance(cta, list):
            cta = ", ".join(str(item) for item in cta) if cta else ""
        elif isinstance(cta, dict):
            import json
            cta = json.dumps(cta, indent=2)
        elif not isinstance(cta, str):
            cta = str(cta) if cta else ""
        
        meme_archetype = cta_analysis.get("archetype", "")
        if isinstance(meme_archetype, list):
            meme_archetype = ", ".join(str(item) for item in meme_archetype) if meme_archetype else ""
        elif isinstance(meme_archetype, dict):
            import json
            meme_archetype = json.dumps(meme_archetype, indent=2)
        elif not isinstance(meme_archetype, str):
            meme_archetype = str(meme_archetype) if meme_archetype else ""
        
        blueprint = TrendBlueprint(
            trend_name=f"{category.value}_trend",
            trend_category=category,
            average_length=15.0,  # Typical Shorts length
            hook_duration=avg_hook_duration,
            hook_words=hook_words,
            common_plot_arcs=[arc[0] for arc in common_arcs],
            editing_timing_patterns=editing_patterns,
            cta=cta,
            meme_archetype=meme_archetype,
            visual_style={
                "style": common_style,
                "common_colors": self._extract_common_colors(analyses),
                "framing": self._extract_common_framing(analyses),
                "camera": self._extract_common_camera(analyses)
            },
            character_types=common_characters,
            example_video_ids=[a.video_id for a in analyses[:5]],
            confidence_score=confidence
        )
        
        return blueprint
    
    def _extract_common_words(self, texts: List[str], top_n: int = 10) -> List[str]:
        """Extract most common words from texts."""
        from collections import Counter
        import re
        
        all_words = []
        for text in texts:
            if text:
                words = re.findall(r'\b\w+\b', text.lower())
                all_words.extend(words)
        
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how'}
        
        filtered_words = [w for w in all_words if w not in stop_words and len(w) > 2]
        common_words = [word for word, count in Counter(filtered_words).most_common(top_n)]
        
        return common_words
    
    def _extract_common_colors(self, analyses: List[VideoAnalysis]) -> List[str]:
        """Extract common colors from analyses."""
        all_colors = []
        for analysis in analyses:
            all_colors.extend(analysis.color_palette)
        
        return [color for color, count in Counter(all_colors).most_common(5)]
    
    def _extract_common_framing(self, analyses: List[VideoAnalysis]) -> str:
        """Extract most common framing style."""
        framings = [a.framing_style for a in analyses if a.framing_style]
        if framings:
            return Counter(framings).most_common(1)[0][0]
        return "unknown"
    
    def _extract_common_camera(self, analyses: List[VideoAnalysis]) -> str:
        """Extract most common camera motion."""
        cameras = [a.camera_motion for a in analyses if a.camera_motion]
        if cameras:
            return Counter(cameras).most_common(1)[0][0]
        return "static"
    
    async def _analyze_editing_patterns(
        self, 
        analyses: List[VideoAnalysis]
    ) -> Dict[str, Any]:
        """Analyze editing timing patterns using LLM."""
        # Summarize analyses for LLM
        summary = self._summarize_analyses(analyses)
        
        prompt = f"""Based on these video analyses, identify common editing timing patterns:

{summary}

Identify patterns like:
- Cut frequency
- Scene duration
- Transition styles
- Pacing

Respond in JSON:
{{
    "cut_frequency": "description",
    "scene_duration": "average seconds",
    "transitions": "transition style",
    "pacing": "fast/slow/medium"
}}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing video editing patterns. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Error analyzing editing patterns: {e}")
        
        return {
            "cut_frequency": "unknown",
            "scene_duration": "unknown",
            "transitions": "unknown",
            "pacing": "medium"
        }
    
    async def _analyze_cta(
        self, 
        analyses: List[VideoAnalysis]
    ) -> Dict[str, Any]:
        """Analyze call-to-action and meme archetype."""
        summary = self._summarize_analyses(analyses)
        
        prompt = f"""Based on these video analyses, identify:

1. Common call-to-action (CTA) patterns - Provide a TEXT DESCRIPTION as a STRING, not an object or list
2. Meme archetype if applicable - Provide a TEXT DESCRIPTION as a STRING, not an object or list

{summary}

IMPORTANT: Both "cta" and "archetype" fields must be STRING values, not arrays or objects.

Respond in JSON:
{{
    "cta": "A clear text description of the call to action pattern as a single string",
    "archetype": "A clear text description of the meme archetype as a single string, or empty string if not applicable"
}}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing viral video CTAs and meme archetypes. Respond only with valid JSON."},
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
            logger.error(f"Error analyzing CTA: {e}")
        
        return {
            "cta": None,
            "archetype": None
        }
    
    def _summarize_analyses(self, analyses: List[VideoAnalysis]) -> str:
        """Create a summary of analyses for LLM processing."""
        summary_parts = []
        
        for i, analysis in enumerate(analyses[:5], 1):  # Limit to 5 for token efficiency
            summary_parts.append(f"""
Video {i}:
- Hook: {analysis.hook_type.value} - "{analysis.hook_text}"
- Plot: {analysis.plot_structure}
- Style: {analysis.visual_style}
- Category: {analysis.trend_category.value}
""")
        
        return "\n".join(summary_parts)

