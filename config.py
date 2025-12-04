"""Configuration settings for Brainrot Generator."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    
    # API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    youtube_api_key: Optional[str] = None
    assemblyai_api_key: Optional[str] = None
    
    # Video Generation APIs
    runway_api_key: Optional[str] = None
    pika_api_key: Optional[str] = None
    kling_api_key: Optional[str] = None
    luma_api_key: Optional[str] = None
    
    # Publishing APIs
    youtube_client_id: Optional[str] = None
    youtube_client_secret: Optional[str] = None
    tiktok_access_token: Optional[str] = None
    meta_access_token: Optional[str] = None
    
    # Database
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    
    # Storage
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_s3_bucket: Optional[str] = None
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Configuration
    brainrot_dev: str = "test"  # "test" or "prod" - in test mode, videos are saved locally and not uploaded
    log_level: str = "INFO"
    max_videos_to_scrape: int = 50
    min_growth_rate: float = 0.20
    frame_extraction_interval: float = 0.5
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        # Map environment variable - allow both ENVIRONMENT and BRAINROT_DEV
        extra = "ignore"  # Ignore extra fields from .env


settings = Settings()

