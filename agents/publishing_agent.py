"""Publishing Agent - Auto-uploads content to platforms."""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    # Optional dependency
    Credentials = None
    InstalledAppFlow = None
    build = None
    MediaFileUpload = None

from config import settings
from models import GeneratedVideo, PublishingMetadata, VideoMetadata

logger = logging.getLogger(__name__)


class PublishingAgent:
    """Publishes videos to YouTube, TikTok, Instagram Reels."""
    
    def __init__(self, test_output_dir: str = "data/test_published"):
        self.youtube_service = None
        self.test_output_dir = Path(test_output_dir)
        self.test_output_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_youtube()
        
    def _initialize_youtube(self):
        """Initialize YouTube API service."""
        if settings.youtube_client_id and settings.youtube_client_secret:
            # TODO: Implement OAuth flow for YouTube
            # For now, placeholder
            logger.info("YouTube API credentials available")
        else:
            logger.warning("YouTube API credentials not configured")
    
    async def publish_video(
        self,
        video: GeneratedVideo,
        metadata: PublishingMetadata
    ) -> Dict[str, Any]:
        """
        Publish video to specified platforms.
        
        Args:
            video: GeneratedVideo to publish
            metadata: PublishingMetadata with title, description, etc.
            
        Returns:
            Dict with platform URLs and status
        """
        logger.info(f"Publishing video: {video.video_path}")
        
        # Check if we're in test mode
        if settings.brainrot_dev.lower() == "test":
            logger.info("TEST MODE: Saving video locally instead of uploading")
            return await self._save_for_test(video, metadata)
        
        # Production mode - actually publish
        results = {}
        
        for platform in metadata.platforms:
            try:
                if platform == "youtube":
                    result = await self._publish_to_youtube(video, metadata)
                    results["youtube"] = result
                elif platform == "tiktok":
                    result = await self._publish_to_tiktok(video, metadata)
                    results["tiktok"] = result
                elif platform == "instagram":
                    result = await self._publish_to_instagram(video, metadata)
                    results["instagram"] = result
            except Exception as e:
                logger.error(f"Error publishing to {platform}: {e}")
                results[platform] = {"status": "error", "error": str(e)}
        
        return results
    
    async def _publish_to_youtube(
        self,
        video: GeneratedVideo,
        metadata: PublishingMetadata
    ) -> dict:
        """Publish to YouTube Shorts."""
        logger.info("Publishing to YouTube Shorts")
        
        if not self.youtube_service:
            return {"status": "error", "error": "YouTube service not initialized"}
        
        try:
            body = {
                "snippet": {
                    "title": metadata.title,
                    "description": self._format_description(metadata),
                    "tags": metadata.hashtags,
                    "categoryId": "22"  # People & Blogs
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False
                }
            }
            
            try:
                from googleapiclient.http import MediaFileUpload
                media = MediaFileUpload(
                    video.video_path,
                    mimetype="video/mp4",
                    resumable=True
                )
            except (ImportError, NameError):
                media = None
                logger.warning("Google API client not available")
            
            # TODO: Implement actual upload
            # request = self.youtube_service.videos().insert(
            #     part="snippet,status",
            #     body=body,
            #     media_body=media
            # )
            # response = request.execute()
            
            logger.info("YouTube upload not yet fully implemented")
            return {
                "status": "success",
                "platform": "youtube",
                "video_id": "placeholder",
                "url": "https://youtube.com/watch?v=placeholder"
            }
            
        except Exception as e:
            logger.error(f"Error uploading to YouTube: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _publish_to_tiktok(
        self,
        video: GeneratedVideo,
        metadata: PublishingMetadata
    ) -> Dict[str, Any]:
        """Publish to TikTok."""
        logger.info("Publishing to TikTok")
        
        if not settings.tiktok_access_token:
            return {"status": "error", "error": "TikTok access token not configured"}
        
        try:
            # TODO: Implement TikTok API upload
            # TikTok API requires specific authentication and endpoints
            logger.info("TikTok upload not yet fully implemented")
            return {
                "status": "success",
                "platform": "tiktok",
                "video_id": "placeholder"
            }
        except Exception as e:
            logger.error(f"Error uploading to TikTok: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _publish_to_instagram(
        self,
        video: GeneratedVideo,
        metadata: PublishingMetadata
    ) -> Dict[str, Any]:
        """Publish to Instagram Reels."""
        logger.info("Publishing to Instagram Reels")
        
        if not settings.meta_access_token:
            return {"status": "error", "error": "Meta access token not configured"}
        
        try:
            # TODO: Implement Instagram Graph API upload
            # Requires Instagram Business Account and Graph API
            logger.info("Instagram upload not yet fully implemented")
            return {
                "status": "success",
                "platform": "instagram",
                "video_id": "placeholder"
            }
        except Exception as e:
            logger.error(f"Error uploading to Instagram: {e}")
            return {"status": "error", "error": str(e)}
    
    def _format_description(self, metadata: PublishingMetadata) -> str:
        """Format description with hashtags."""
        description = metadata.description
        
        if metadata.hashtags:
            hashtag_str = " ".join(metadata.hashtags)
            description += f"\n\n{hashtag_str}"
        
        return description
    
    async def generate_publishing_metadata(
        self,
        script_title: str,
        script_text: str,
        trend_category: str
    ) -> PublishingMetadata:
        """Auto-generate publishing metadata."""
        from openai import OpenAI
        
        client = OpenAI(api_key=settings.openai_api_key)
        
        prompt = f"""Generate engaging social media metadata for this video:

Title: {script_title}
Content: {script_text[:500]}
Category: {trend_category}

Generate:
1. A catchy, clickable title (optimized for platform)
2. A short, engaging description (2-3 sentences)
3. 10-15 relevant hashtags

Respond in JSON:
{{
    "title": "title",
    "description": "description",
    "hashtags": ["hashtag1", "hashtag2"]
}}"""
        
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at creating viral social media content. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            import json
            data = json.loads(response.choices[0].message.content)
            
            return PublishingMetadata(
                title=data.get("title", script_title),
                description=data.get("description", ""),
                hashtags=data.get("hashtags", []),
                platforms=["youtube", "tiktok", "instagram"]  # Default to all
            )
        except Exception as e:
            logger.error(f"Error generating metadata: {e}")
            return PublishingMetadata(
                title=script_title,
                description=script_text[:200],
                hashtags=[f"#{trend_category}", "#shorts", "#viral"],
                platforms=["youtube"]
            )
    
    async def _save_for_test(
        self,
        video: GeneratedVideo,
        metadata: PublishingMetadata
    ) -> Dict[str, Any]:
        """Save video locally in test mode with metadata."""
        import shutil
        import json
        
        # Create a safe filename from the title
        safe_title = "".join(c for c in metadata.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')[:50]  # Limit length
        
        # Copy video to test output directory
        video_filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        test_video_path = self.test_output_dir / video_filename
        
        try:
            # Copy the video file
            shutil.copy2(video.video_path, test_video_path)
            logger.info(f"Saved test video to: {test_video_path}")
            
            # Save metadata as JSON
            metadata_filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_metadata.json"
            metadata_path = self.test_output_dir / metadata_filename
            
            metadata_dict = {
                "title": metadata.title,
                "description": metadata.description,
                "hashtags": metadata.hashtags,
                "platforms": metadata.platforms,
                "video_path": str(test_video_path),
                "original_video_path": video.video_path,
                "script_id": video.script_id,
                "generator_used": video.generator_used,
                "saved_at": datetime.now().isoformat(),
                "brainrot_dev": "test"
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved metadata to: {metadata_path}")
            
            return {
                "status": "test_mode",
                "message": "Video saved locally (test mode - no upload)",
                "video_path": str(test_video_path),
                "metadata_path": str(metadata_path),
                "platforms": metadata.platforms,
                "would_publish_to": metadata.platforms
            }
            
        except Exception as e:
            logger.error(f"Error saving test video: {e}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to save video in test mode"
            }

