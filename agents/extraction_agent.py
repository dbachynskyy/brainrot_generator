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

try:
    import whisper
except ImportError:
    whisper = None

logger = logging.getLogger(__name__)
if not whisperx and not whisper:
    logger.warning("WhisperX and Whisper not available, transcription will use yt-dlp subtitles or be skipped")

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
            result["transcript"] = await self._extract_transcript(video_path, video.video_id, video.url)
        
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
        video_id: str,
        video_url: str = None
    ) -> List[TranscriptSegment]:
        """Extract transcript using multiple fallback methods."""
        # Method 1: Try yt-dlp to extract subtitles (fastest, most accurate if available)
        if video_url:
            try:
                subtitles = await self._extract_subtitles_with_ytdlp(video_url)
                if subtitles:
                    logger.info(f"Extracted {len(subtitles)} transcript segments using yt-dlp subtitles")
                    return subtitles
            except Exception as e:
                logger.debug(f"yt-dlp subtitle extraction failed: {e}")
        
        # Method 2: Try WhisperX (best quality with alignment)
        if whisperx:
            try:
                return await self._extract_with_whisperx(video_path)
            except Exception as e:
                logger.warning(f"WhisperX transcription failed: {e}")
        
        # Method 3: Try OpenAI Whisper (simpler, no alignment)
        if whisper:
            try:
                return await self._extract_with_whisper(video_path)
            except Exception as e:
                logger.warning(f"Whisper transcription failed: {e}")
        
        logger.warning("All transcription methods failed, returning empty transcript")
        return []
    
    async def _extract_subtitles_with_ytdlp(self, video_url: str) -> List[TranscriptSegment]:
        """Extract subtitles using yt-dlp if available."""
        import tempfile
        import json
        
        # Create temp directory for subtitle files
        temp_dir = Path(tempfile.mkdtemp())
        temp_srt_base = temp_dir / "subtitle"
        
        try:
            # First, check what subtitles are available
            check_cmd = [
                "yt-dlp",
                "--list-subs",
                "--sub-lang", "en,en-US,en-GB,en.*",
                video_url
            ]
            
            check_result = subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            # Check if subtitles are available
            if "Available subtitles" not in check_result.stdout and "Available automatic captions" not in check_result.stdout:
                logger.debug(f"No subtitles available for {video_url}")
                # Try to get JSON info to see what's available
                json_cmd = [
                    "yt-dlp",
                    "--dump-json",
                    "--skip-download",
                    video_url
                ]
                json_result = subprocess.run(
                    json_cmd,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if json_result.returncode == 0:
                    try:
                        video_info = json.loads(json_result.stdout)
                        subtitles = video_info.get('subtitles', {})
                        auto_captions = video_info.get('automatic_captions', {})
                        if not subtitles and not auto_captions:
                            logger.debug(f"Video has no subtitles or auto-captions available")
                        else:
                            logger.debug(f"Video has subtitles: {list(subtitles.keys())}, auto-captions: {list(auto_captions.keys())}")
                    except:
                        pass
            
            # Try to download subtitles
            cmd = [
                "yt-dlp",
                "--write-auto-subs",  # Try auto-generated first (more likely to exist)
                "--write-subs",  # Then try manual subtitles
                "--sub-lang", "en,en-US,en-GB,en.*",  # Try multiple English variants
                "--skip-download",
                "--sub-format", "srt",
                "--convert-subs", "srt",  # Ensure SRT format
                "-o", str(temp_srt_base) + ".%(ext)s",  # Better output pattern
                video_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=45
            )
            
            if result.returncode != 0:
                logger.debug(f"yt-dlp subtitle download failed: {result.stderr[:300]}")
            
            # yt-dlp creates files with pattern: {base}.{lang}.{ext}
            # Look for SRT files in temp directory (check parent if needed)
            srt_files = list(temp_dir.glob("*.srt"))
            if not srt_files:
                # Check parent directory (yt-dlp might create files there)
                parent_dir = temp_dir.parent
                srt_files = list(parent_dir.glob(f"{temp_srt_base.name}*.srt"))
            
            # Also check for files with .en. in the name
            if not srt_files:
                srt_files = list(temp_dir.glob("*en*.srt"))
                if not srt_files:
                    srt_files = list(temp_dir.parent.glob("*en*.srt"))
            
            if srt_files:
                # Use the first SRT file found
                srt_path = srt_files[0]
                segments = self._parse_srt_file(srt_path)
                if segments:
                    logger.info(f"Successfully extracted {len(segments)} segments from {srt_path.name}")
                    return segments
                else:
                    logger.debug(f"SRT file found but parsing returned no segments: {srt_path}")
            else:
                logger.debug(f"No subtitle files found. stdout: {result.stdout[:200]}, stderr: {result.stderr[:200]}")
            
        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp subtitle extraction timed out")
        except Exception as e:
            logger.warning(f"yt-dlp subtitle extraction error: {e}", exc_info=True)
        finally:
            # Clean up temp directory
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
        
        return []
    
    def _parse_srt_file(self, srt_path: Path) -> List[TranscriptSegment]:
        """Parse SRT subtitle file into TranscriptSegment objects."""
        segments = []
        
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple SRT parser
            import re
            pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\n*$)'
            matches = re.findall(pattern, content, re.DOTALL)
            
            for match in matches:
                start_str = match[1].replace(',', '.')
                end_str = match[2].replace(',', '.')
                text = match[3].strip().replace('\n', ' ')
                
                # Convert time to seconds
                start_time = self._srt_time_to_seconds(start_str)
                end_time = self._srt_time_to_seconds(end_str)
                
                segments.append(TranscriptSegment(
                    text=text,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=1.0  # SRT subtitles are usually accurate
                ))
        except Exception as e:
            logger.error(f"Error parsing SRT file: {e}")
        
        return segments
    
    def _srt_time_to_seconds(self, time_str: str) -> float:
        """Convert SRT time format (HH:MM:SS.mmm) to seconds."""
        parts = time_str.split(':')
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    
    async def _extract_with_whisperx(self, video_path: Path) -> List[TranscriptSegment]:
        """Extract transcript using WhisperX."""
        import torch
        
        # Detect device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        
        # Load model if not loaded
        if self.whisper_model is None:
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
            device=device
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
        
        logger.info(f"Extracted transcript with {len(segments)} segments using WhisperX")
        return segments
    
    async def _extract_with_whisper(self, video_path: Path) -> List[TranscriptSegment]:
        """Extract transcript using OpenAI Whisper (simpler fallback)."""
        import torch
        
        # Detect device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load model
        model = whisper.load_model("base", device=device)
        
        # Transcribe
        result = model.transcribe(str(video_path))
        
        # Convert to TranscriptSegment objects
        segments = []
        for segment in result.get("segments", []):
            segments.append(TranscriptSegment(
                text=segment.get("text", "").strip(),
                start_time=segment.get("start", 0.0),
                end_time=segment.get("end", 0.0),
                confidence=segment.get("no_speech_prob", 0.0)  # Lower is better
            ))
        
        logger.info(f"Extracted transcript with {len(segments)} segments using Whisper")
        return segments

