"""Test transcription extraction on existing videos."""
import asyncio
import logging
from pathlib import Path
from agents.extraction_agent import ExtractionAgent
from models import VideoMetadata
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_transcription():
    """Test transcription extraction on an existing video."""
    
    # Find an existing video file
    extracted_dir = Path("data/extracted")
    video_files = list(extracted_dir.glob("*.mp4"))
    
    if not video_files:
        logger.error("No video files found in data/extracted/")
        return
    
    # Use the first video found
    video_file = video_files[0]
    video_id = video_file.stem
    
    logger.info(f"Testing transcription on: {video_file}")
    logger.info(f"Video ID: {video_id}")
    
    # Create a mock VideoMetadata object
    video_metadata = VideoMetadata(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title="Test Video",
        description="Test",
        channel_id="test",
        channel_name="Test Channel",
        view_count=1000,
        like_count=100,
        upload_time=datetime.now(),
        hashtags=[],
        duration=0.0
    )
    
    # Initialize extraction agent
    extraction_agent = ExtractionAgent()
    
    # Test transcription extraction
    logger.info("=" * 80)
    logger.info("TESTING TRANSCRIPTION EXTRACTION")
    logger.info("=" * 80)
    
    transcript = await extraction_agent._extract_transcript(
        video_path=video_file,
        video_id=video_id,
        video_url=video_metadata.url
    )
    
    logger.info("=" * 80)
    logger.info("TRANSCRIPTION RESULTS")
    logger.info("=" * 80)
    
    if transcript:
        logger.info(f"✅ Successfully extracted {len(transcript)} transcript segments!")
        logger.info("\nFirst 5 segments:")
        for i, segment in enumerate(transcript[:5], 1):
            logger.info(f"\n{i}. [{segment.start_time:.2f}s - {segment.end_time:.2f}s]")
            logger.info(f"   Text: {segment.text}")
            logger.info(f"   Confidence: {segment.confidence:.2f}")
        
        if len(transcript) > 5:
            logger.info(f"\n... and {len(transcript) - 5} more segments")
        
        # Save transcript to file
        transcript_file = extracted_dir / f"{video_id}_transcript.txt"
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(f"TRANSCRIPT FOR VIDEO: {video_id}\n")
            f.write("=" * 80 + "\n\n")
            for segment in transcript:
                f.write(f"[{segment.start_time:.2f}s - {segment.end_time:.2f}s] ")
                f.write(f"(confidence: {segment.confidence:.2f})\n")
                f.write(f"{segment.text}\n\n")
        
        logger.info(f"\n✅ Full transcript saved to: {transcript_file}")
        
    else:
        logger.warning("❌ No transcript extracted - all methods failed")
        logger.warning("This could mean:")
        logger.warning("1. Video has no subtitles/auto-captions")
        logger.warning("2. yt-dlp subtitle extraction failed")
        logger.warning("3. WhisperX/Whisper not installed")
        logger.warning("4. Video language is not English")


if __name__ == "__main__":
    asyncio.run(test_transcription())

