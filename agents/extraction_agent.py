"""Extraction Agent - Downloads videos and extracts frames/transcripts."""
import os
import subprocess
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import cv2

try:
    import whisperx
except ImportError:
    whisperx = None
    logger = logging.getLogger(__name__)
    logger.warning("WhisperX not available, transcription will be limited")

from config import settings
from models import VideoMetadata, ReferenceFrame, TranscriptSegment

logger = logging.getLogger(__name__)


class ExtractionAgent:
    """Extracts video data: frames, transcripts, references."""
    
    def __init__(self, output_dir: str = "data/extracted"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.whisper_model = None
        
    async def extract_video_data(
        self, 
        video: VideoMetadata,
        extract_frames: bool = True,
        extract_transcript: bool = True
    ) -> dict:
        """
        Extract all data from a video.
        
        Returns:
            dict with keys: video_path, frames, transcript, reference_frames
        """
        logger.info(f"Extracting data from video: {video.video_id}")
        
        # Download video
        video_path = await self._download_video(video)
        
        result = {
            "video_path": str(video_path),
            "frames": [],
            "transcript": [],
            "reference_frames": []
        }
        
        if extract_frames:
            result["frames"] = await self._extract_frames(video_path, video.video_id)
            result["reference_frames"] = await self._extract_reference_frames(
                video_path, 
                video.video_id
            )
        
        if extract_transcript:
            result["transcript"] = await self._extract_transcript(video_path, video.video_id)
        
        return result
    
    async def _download_video(self, video: VideoMetadata) -> Path:
        """Download video using yt-dlp."""
        output_path = self.output_dir / f"{video.video_id}.mp4"
        
        if output_path.exists():
            logger.info(f"Video already downloaded: {output_path}")
            return output_path
        
        try:
            cmd = [
                "yt-dlp",
                "-f", "best[height<=720]",  # Download best quality up to 720p
                "-o", str(output_path),
                video.url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Downloaded video: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error downloading video: {e.stderr}")
            raise
    
    async def _extract_frames(
        self, 
        video_path: Path, 
        video_id: str,
        interval: float = None
    ) -> List[str]:
        """Extract frames from video at specified interval."""
        interval = interval or settings.frame_extraction_interval
        
        frames_dir = self.output_dir / video_id / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        
        frame_paths = []
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(fps * interval)
        
        frame_count = 0
        saved_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                frame_path = frames_dir / f"frame_{saved_count:06d}.jpg"
                cv2.imwrite(str(frame_path), frame)
                frame_paths.append(str(frame_path))
                saved_count += 1
            
            frame_count += 1
        
        cap.release()
        logger.info(f"Extracted {len(frame_paths)} frames from {video_id}")
        
        return frame_paths
    
    async def _extract_reference_frames(
        self, 
        video_path: Path, 
        video_id: str
    ) -> List[ReferenceFrame]:
        """Extract key reference frames (poses, style, backgrounds)."""
        frames_dir = self.output_dir / video_id / "frames"
        reference_dir = self.output_dir / video_id / "references"
        reference_dir.mkdir(parents=True, exist_ok=True)
        
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        
        # Extract frames at key moments: start, 25%, 50%, 75%, end
        key_moments = [0.0, duration * 0.25, duration * 0.5, duration * 0.75, duration]
        
        reference_frames = []
        
        for moment in key_moments:
            frame_number = int(moment * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            
            if ret:
                frame_path = reference_dir / f"ref_{moment:.1f}s.jpg"
                cv2.imwrite(str(frame_path), frame)
                
                # TODO: Use CLIP/Vision models to analyze frame
                # For MVP, basic description
                description = f"Frame at {moment:.1f}s"
                
                reference_frames.append(ReferenceFrame(
                    frame_path=str(frame_path),
                    timestamp=moment,
                    description=description,
                    pose_detected=False,
                    style_tags=[]
                ))
        
        cap.release()
        logger.info(f"Extracted {len(reference_frames)} reference frames")
        
        return reference_frames
    
    async def _extract_transcript(
        self, 
        video_path: Path, 
        video_id: str
    ) -> List[TranscriptSegment]:
        """Extract transcript using WhisperX."""
        if not whisperx:
            logger.warning("WhisperX not available, skipping transcription")
            return []
        
        try:
            # Load model if not loaded
            if self.whisper_model is None:
                device = "cuda"  # or "cpu"
                compute_type = "float16"  # or "int8"
                
                self.whisper_model = whisperx.load_model(
                    "base", 
                    device, 
                    compute_type=compute_type
                )
            
            # Transcribe
            audio = whisperx.load_audio(str(video_path))
            result = self.whisper_model.transcribe(audio, batch_size=16)
            
            # Align timestamps
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"], 
                device="cuda"
            )
            result = whisperx.align(
                result["segments"], 
                model_a, 
                metadata, 
                audio, 
                device, 
                return_char_alignments=False
            )
            
            # Convert to TranscriptSegment objects
            segments = []
            for segment in result.get("segments", []):
                segments.append(TranscriptSegment(
                    text=segment.get("text", ""),
                    start_time=segment.get("start", 0.0),
                    end_time=segment.get("end", 0.0),
                    confidence=segment.get("words", [{}])[0].get("score", 0.0) if segment.get("words") else 0.0
                ))
            
            logger.info(f"Extracted transcript with {len(segments)} segments")
            return segments
            
        except Exception as e:
            logger.error(f"Error extracting transcript: {e}")
            # Fallback to basic extraction
            return []

