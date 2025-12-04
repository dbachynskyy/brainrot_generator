"""Data models for Brainrot Generator."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TrendCategory(str, Enum):
    """Trend categories."""
    MOTIVATIONAL = "motivational"
    GAMING = "gaming"
    ANIMATED_SKITS = "animated_skits"
    SIGMA_EDITS = "sigma_edits"
    FUNNY_POV = "funny_pov"
    RELATIONSHIP = "relationship"
    MEME = "meme"
    OTHER = "other"


class HookType(str, Enum):
    """Hook types."""
    SHOCK = "shock"
    RELATABLE = "relatable_moment"
    MOTIVATIONAL = "motivational"
    FUNNY_POV = "funny_pov"
    QUESTION = "question"
    VISUAL_SHOCK = "visual_shock"


class VideoMetadata(BaseModel):
    """Metadata for a YouTube video."""
    video_id: str
    url: str
    title: str
    description: str
    channel_id: str
    channel_name: str
    view_count: int
    like_count: int
    upload_time: datetime
    hashtags: List[str] = Field(default_factory=list)
    duration: float = 0.0  # in seconds


class ChannelMetadata(BaseModel):
    """Metadata for a YouTube channel."""
    channel_id: str
    channel_name: str
    subscriber_count: int
    video_count: int
    weekly_growth_rate: float = 0.0


class TranscriptSegment(BaseModel):
    """Transcript segment with timestamp."""
    text: str
    start_time: float
    end_time: float
    confidence: float = 0.0


class VideoAnalysis(BaseModel):
    """Analysis results for a video."""
    video_id: str
    hook_type: HookType
    hook_text: Optional[str] = None
    hook_duration: float = 0.0  # seconds
    
    plot_structure: str
    story_arc: str
    
    tone: str
    emotion: str
    
    visual_style: str
    color_palette: List[str] = Field(default_factory=list)
    framing_style: str
    camera_motion: str
    
    character_aesthetics: List[str] = Field(default_factory=list)
    character_roles: List[str] = Field(default_factory=list)
    
    trend_category: TrendCategory
    audio_style: str
    
    transcript: List[TranscriptSegment] = Field(default_factory=list)
    
    identified_patterns: Dict[str, Any] = Field(default_factory=dict)


class ReferenceFrame(BaseModel):
    """Reference frame extracted from video."""
    frame_path: str
    timestamp: float
    description: str
    pose_detected: bool = False
    style_tags: List[str] = Field(default_factory=list)


class TrendBlueprint(BaseModel):
    """Blueprint for a trend pattern."""
    trend_name: str
    trend_category: TrendCategory
    
    average_length: float  # seconds
    hook_duration: float  # seconds
    hook_words: List[str] = Field(default_factory=list)
    
    common_plot_arcs: List[str] = Field(default_factory=list)
    editing_timing_patterns: Dict[str, Any] = Field(default_factory=dict)
    
    cta: Optional[str] = None
    meme_archetype: Optional[str] = None
    
    visual_style: Dict[str, Any] = Field(default_factory=dict)
    character_types: List[str] = Field(default_factory=list)
    
    example_video_ids: List[str] = Field(default_factory=list)
    confidence_score: float = 0.0


class Script(BaseModel):
    """Generated script for video."""
    title: str
    script_text: str
    shot_list: List[Dict[str, Any]] = Field(default_factory=list)
    visual_style_instructions: str
    camera_motion: List[str] = Field(default_factory=list)
    dialogue: List[Dict[str, Any]] = Field(default_factory=list)
    caption_text: List[str] = Field(default_factory=list)
    estimated_duration: float = 0.0
    trend_blueprint_id: Optional[str] = None


class ProductionRequest(BaseModel):
    """Request for video production."""
    script: Script
    reference_frames: List[ReferenceFrame] = Field(default_factory=list)
    style_prompt: str
    camera_motion_instructions: str
    generator_preference: Optional[str] = None  # "runway", "pika", "kling", "luma"


class GeneratedVideo(BaseModel):
    """Generated video metadata."""
    video_path: str
    script_id: str
    generator_used: str
    generation_time: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublishingMetadata(BaseModel):
    """Metadata for publishing."""
    title: str
    description: str
    hashtags: List[str] = Field(default_factory=list)
    thumbnail_path: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    platforms: List[str] = Field(default_factory=list)  # "youtube", "tiktok", "instagram"

