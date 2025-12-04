"""Main orchestrator for Brainrot Generator pipeline."""
import asyncio
import logging
from typing import List, Optional
from pathlib import Path

from agents import (
    DiscoveryAgent,
    ExtractionAgent,
    AnalysisAgent,
    PatternAgent,
    ContentGenerationAgent,
    ProductionAgent,
    PublishingAgent
)
from models import (
    VideoMetadata,
    VideoAnalysis,
    TrendBlueprint,
    Script,
    ProductionRequest,
    GeneratedVideo,
    PublishingMetadata
)
from typing import Dict, Any
from config import settings

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


class BrainrotOrchestrator:
    """Orchestrates the entire brainrot generation pipeline."""
    
    def __init__(self):
        self.discovery = DiscoveryAgent()
        self.extraction = ExtractionAgent()
        self.analysis = AnalysisAgent()
        self.pattern = PatternAgent()
        self.content_gen = ContentGenerationAgent()
        self.production = ProductionAgent()
        self.publishing = PublishingAgent()
        
    async def initialize(self):
        """Initialize all agents."""
        await self.discovery.initialize()
        logger.info("Orchestrator initialized")
    
    async def close(self):
        """Clean up resources."""
        await self.discovery.close()
        logger.info("Orchestrator closed")
    
    async def run_full_pipeline(
        self,
        max_videos: int = None,
        generate_video: bool = True,
        publish: bool = False,
        brand_style: Optional[str] = None
    ) -> dict:
        """
        Run the complete pipeline from discovery to publishing.
        
        Args:
            max_videos: Maximum videos to discover and analyze
            generate_video: Whether to generate a new video
            publish: Whether to publish the generated video
            brand_style: Optional brand style to inject
            
        Returns:
            Dict with pipeline results
        """
        logger.info("Starting full pipeline")
        
        results = {
            "discovered_videos": [],
            "analyses": [],
            "blueprints": [],
            "generated_script": None,
            "generated_video": None,
            "publishing_results": None
        }
        
        try:
            # Step 1: Discovery
            logger.info("Step 1: Discovering trending videos...")
            videos = await self.discovery.discover_trending_shorts(
                max_videos=max_videos or settings.max_videos_to_scrape
            )
            results["discovered_videos"] = [v.model_dump() for v in videos]
            logger.info(f"Discovered {len(videos)} trending videos")
            
            # Step 2: Extraction & Analysis
            logger.info("Step 2: Extracting and analyzing videos...")
            analyses = []
            all_reference_frames = []  # Collect reference frames for production
            
            # Shuffle videos to get variety (but keep top ones)
            import random
            # Keep top 5 as-is, shuffle the rest
            top_videos = videos[:5]
            rest_videos = videos[5:]
            random.shuffle(rest_videos)
            shuffled_videos = top_videos + rest_videos
            
            for i, video in enumerate(shuffled_videos[:10], 1):  # Limit to 10 for MVP
                logger.info(f"Processing video {i}/{min(10, len(shuffled_videos))}: {video.video_id}")
                
                try:
                    # Extract
                    extracted = await self.extraction.extract_video_data(video)
                    
                    # Verify language using transcript (double-check)
                    transcript = extracted.get("transcript", [])
                    if transcript:
                        transcript_text = " ".join([seg.text for seg in transcript[:10]])  # Check first 10 segments
                        # Check for non-English characters
                        import re
                        non_english_patterns = [
                            r'[\u4e00-\u9fff]',  # Chinese
                            r'[\u3040-\u309f\u30a0-\u30ff]',  # Japanese
                            r'[\u0400-\u04ff]',  # Cyrillic
                            r'[\u0600-\u06ff]',  # Arabic
                        ]
                        has_non_english = any(re.search(pattern, transcript_text) for pattern in non_english_patterns)
                        if has_non_english:
                            logger.warning(f"Skipping video {video.video_id} ({video.title[:50]}): transcript contains non-English characters")
                            continue
                    
                    # Collect reference frames (use from first video with frames)
                    ref_frames = extracted.get("reference_frames", [])
                    if ref_frames and not all_reference_frames:
                        # Use reference frames from the first video that has them
                        all_reference_frames = ref_frames[:4]  # Limit to 4 frames
                        logger.info(f"Collected {len(all_reference_frames)} reference frames from video {video.video_id} ({video.title[:50]})")
                        logger.info(f"Reference frame paths: {[rf.frame_path for rf in all_reference_frames]}")
                    
                    # Analyze
                    analysis = await self.analysis.analyze_video(
                        video,
                        transcript,
                        ref_frames
                    )
                    analyses.append(analysis)
                    
                except Exception as e:
                    logger.error(f"Error processing video {video.video_id}: {e}")
                    continue
            
            results["analyses"] = [a.model_dump() for a in analyses]
            logger.info(f"Analyzed {len(analyses)} videos")
            
            # Step 3: Pattern Identification
            logger.info("Step 3: Identifying patterns...")
            blueprints = await self.pattern.identify_patterns(analyses)
            results["blueprints"] = [b.model_dump() for b in blueprints]
            logger.info(f"Identified {len(blueprints)} trend blueprints")
            
            if not generate_video or not blueprints:
                logger.info("Pipeline complete (no video generation requested)")
                return results
            
            # Step 4: Content Generation
            logger.info("Step 4: Generating script...")
            # Use the highest confidence blueprint
            best_blueprint = max(blueprints, key=lambda b: b.confidence_score)
            script = await self.content_gen.generate_script(best_blueprint, brand_style)
            results["generated_script"] = script.model_dump()
            logger.info(f"Generated script: {script.title}")
            
            # Step 5: Production
            logger.info("Step 5: Generating video...")
            logger.info(f"Using {len(all_reference_frames)} reference frames for video generation")
            production_request = ProductionRequest(
                script=script,
                reference_frames=all_reference_frames,  # Use extracted reference frames
                style_prompt=script.visual_style_instructions,
                camera_motion_instructions=", ".join(script.camera_motion),
                generator_preference=None  # Auto-select
            )
            
            generated_video = await self.production.generate_video(production_request)
            results["generated_video"] = generated_video.model_dump()
            logger.info(f"Generated video: {generated_video.video_path}")
            
            # Step 6: Publishing (optional)
            if publish:
                logger.info("Step 6: Publishing video...")
                publishing_metadata = await self.publishing.generate_publishing_metadata(
                    script.title,
                    script.script_text,
                    best_blueprint.trend_category.value
                )
                
                publishing_results = await self.publishing.publish_video(
                    generated_video,
                    publishing_metadata
                )
                results["publishing_results"] = publishing_results
                logger.info("Publishing complete")
            
            logger.info("Pipeline complete!")
            return results
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            results["error"] = str(e)
            return results
    
    async def run_mvp(self) -> dict:
        """Run MVP version: discover, analyze, generate one video."""
        return await self.run_full_pipeline(
            max_videos=50,
            generate_video=True,
            publish=False
        )


async def main():
    """Main entry point."""
    orchestrator = BrainrotOrchestrator()
    
    try:
        await orchestrator.initialize()
        results = await orchestrator.run_mvp()
        
        # Print summary
        print("\n" + "="*50)
        print("PIPELINE RESULTS")
        print("="*50)
        print(f"Discovered videos: {len(results.get('discovered_videos', []))}")
        print(f"Analyzed videos: {len(results.get('analyses', []))}")
        print(f"Trend blueprints: {len(results.get('blueprints', []))}")
        
        if results.get('generated_script'):
            print(f"\nGenerated Script: {results['generated_script']['title']}")
        
        if results.get('generated_video'):
            print(f"Generated Video: {results['generated_video']['video_path']}")
        
        print("="*50)
        
    finally:
        await orchestrator.close()


if __name__ == "__main__":
    asyncio.run(main())

