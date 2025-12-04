"""Example usage of Brainrot Generator."""
import asyncio
import logging
from orchestrator import BrainrotOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def example_discovery_only():
    """Example: Just discover trending videos."""
    orchestrator = BrainrotOrchestrator()
    await orchestrator.initialize()
    
    try:
        videos = await orchestrator.discovery.discover_trending_shorts(max_videos=10)
        
        print(f"\n{'='*60}")
        print(f"DISCOVERED {len(videos)} TRENDING VIDEOS")
        print(f"{'='*60}\n")
        
        for i, video in enumerate(videos[:5], 1):
            print(f"{i}. {video.title}")
            print(f"   Views: {video.view_count:,}")
            print(f"   Likes: {video.like_count:,}")
            print(f"   URL: {video.url}")
            print()
    
    finally:
        await orchestrator.close()


async def example_full_pipeline():
    """Example: Run full pipeline."""
    orchestrator = BrainrotOrchestrator()
    await orchestrator.initialize()
    
    try:
        results = await orchestrator.run_full_pipeline(
            max_videos=20,  # Smaller for example
            generate_video=True,
            publish=False,
            brand_style="energetic, motivational, with a touch of humor"
        )
        
        print(f"\n{'='*60}")
        print("PIPELINE RESULTS")
        print(f"{'='*60}\n")
        
        print(f"✓ Discovered: {len(results.get('discovered_videos', []))} videos")
        print(f"✓ Analyzed: {len(results.get('analyses', []))} videos")
        print(f"✓ Blueprints: {len(results.get('blueprints', []))} trends")
        
        if results.get('generated_script'):
            script = results['generated_script']
            print(f"\n✓ Generated Script:")
            print(f"  Title: {script['title']}")
            print(f"  Duration: {script['estimated_duration']}s")
            print(f"  Shots: {len(script['shot_list'])}")
        
        if results.get('generated_video'):
            video = results['generated_video']
            print(f"\n✓ Generated Video:")
            print(f"  Path: {video['video_path']}")
            print(f"  Generator: {video['generator_used']}")
    
    finally:
        await orchestrator.close()


async def example_custom_workflow():
    """Example: Custom workflow with individual agents."""
    orchestrator = BrainrotOrchestrator()
    await orchestrator.initialize()
    
    try:
        # Step 1: Discover
        print("Step 1: Discovering videos...")
        videos = await orchestrator.discovery.discover_trending_shorts(max_videos=5)
        print(f"Found {len(videos)} videos\n")
        
        # Step 2: Extract and analyze one video
        if videos:
            video = videos[0]
            print(f"Step 2: Processing {video.title}...")
            
            extracted = await orchestrator.extraction.extract_video_data(video)
            print(f"Extracted {len(extracted.get('frames', []))} frames")
            print(f"Extracted {len(extracted.get('transcript', []))} transcript segments\n")
            
            # Step 3: Analyze
            print("Step 3: Analyzing content...")
            analysis = await orchestrator.analysis.analyze_video(
                video,
                extracted.get('transcript', []),
                extracted.get('reference_frames', [])
            )
            print(f"Hook type: {analysis.hook_type.value}")
            print(f"Trend category: {analysis.trend_category.value}")
            print(f"Visual style: {analysis.visual_style}\n")
        
    finally:
        await orchestrator.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "discovery":
            asyncio.run(example_discovery_only())
        elif mode == "full":
            asyncio.run(example_full_pipeline())
        elif mode == "custom":
            asyncio.run(example_custom_workflow())
        else:
            print("Usage: python example.py [discovery|full|custom]")
    else:
        print("Running discovery-only example...")
        print("Use 'python example.py full' for full pipeline")
        print("Use 'python example.py custom' for custom workflow\n")
        asyncio.run(example_discovery_only())

