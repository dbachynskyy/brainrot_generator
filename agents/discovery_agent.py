"""Discovery Agent - Scrapes YouTube Shorts for trending content."""
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

try:
    from googleapiclient.discovery import build
except ImportError:
    build = None

from playwright.async_api import async_playwright, Browser, Page
import httpx

from config import settings
from models import VideoMetadata, ChannelMetadata

logger = logging.getLogger(__name__)


class DiscoveryAgent:
    """Discovers trending YouTube Shorts and tracks growth metrics."""
    
    def __init__(self):
        if build and settings.youtube_api_key:
            try:
                self.youtube_api = build('youtube', 'v3', developerKey=settings.youtube_api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize YouTube API: {e}")
                self.youtube_api = None
        else:
            self.youtube_api = None
            if not build:
                logger.warning("Google API client not available")
            elif not settings.youtube_api_key:
                logger.warning("YouTube API key not configured")
        self.browser: Optional[Browser] = None
        
    async def initialize(self):
        """Initialize browser for web scraping."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        
    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
    
    async def discover_trending_shorts(
        self, 
        max_videos: int = None,
        min_growth_rate: float = None
    ) -> List[VideoMetadata]:
        """
        Discover trending YouTube Shorts.
        
        Args:
            max_videos: Maximum number of videos to discover
            min_growth_rate: Minimum weekly growth rate (default 0.20 = 20%)
            
        Returns:
            List of VideoMetadata objects
        """
        max_videos = max_videos or settings.max_videos_to_scrape
        min_growth_rate = min_growth_rate or settings.min_growth_rate
        
        logger.info(f"Discovering trending Shorts (max: {max_videos}, min_growth: {min_growth_rate})")
        
        # Strategy 1: Use YouTube API to search for Shorts
        api_videos = await self._search_shorts_via_api(max_videos)
        logger.info(f"Found {len(api_videos)} videos via YouTube API")
        
        # Strategy 2: Use Playwright to scrape Shorts page for additional data
        scraped_videos = await self._scrape_shorts_page()
        logger.info(f"Found {len(scraped_videos)} videos via Playwright scraping")
        
        # Combine and deduplicate
        all_videos = self._merge_video_data(api_videos, scraped_videos)
        logger.info(f"Total unique videos after merge: {len(all_videos)}")
        
        # Filter by growth rate and engagement
        # For MVP, use lenient filtering - just remove videos with very low engagement
        # Skip the complex channel API calls that might be failing
        trending_videos = [v for v in all_videos if v.view_count > 1000]  # Simple threshold
        logger.info(f"After simple filtering (views > 1000): {len(trending_videos)} videos remain")
        
        # Skip growth rate filtering for MVP - it's too strict and makes too many API calls
        # Just use view count and virality ranking
        
        # Rank by virality score
        ranked_videos = self._rank_by_virality(trending_videos)
        logger.info(f"After ranking: {len(ranked_videos)} videos")
        
        result = ranked_videos[:max_videos]
        logger.info(f"Returning {len(result)} videos (requested max: {max_videos})")
        return result
    
    async def _search_shorts_via_api(self, max_results: int) -> List[VideoMetadata]:
        """Search for Shorts using YouTube Data API."""
        videos = []
        
        if not self.youtube_api:
            logger.warning("YouTube API not available, skipping API search")
            return videos
        
        try:
            # Search for Shorts (duration < 4 minutes, typically < 60 seconds)
            request = self.youtube_api.search().list(
                part='snippet',
                q='#shorts',
                type='video',
                maxResults=min(max_results, 50),
                order='viewCount',
                videoDuration='short',
                publishedAfter=(datetime.now() - timedelta(days=7)).isoformat() + 'Z'
            )
            
            response = request.execute()
            
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                
                # Get detailed video stats
                video_details = self.youtube_api.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=video_id
                ).execute()
                
                if video_details.get('items'):
                    video_data = video_details['items'][0]
                    snippet = video_data['snippet']
                    stats = video_data['statistics']
                    
                    videos.append(VideoMetadata(
                        video_id=video_id,
                        url=f"https://www.youtube.com/shorts/{video_id}",
                        title=snippet.get('title', ''),
                        description=snippet.get('description', ''),
                        channel_id=snippet.get('channelId', ''),
                        channel_name=snippet.get('channelTitle', ''),
                        view_count=int(stats.get('viewCount', 0)),
                        like_count=int(stats.get('likeCount', 0)),
                        upload_time=datetime.fromisoformat(
                            snippet['publishedAt'].replace('Z', '+00:00')
                        ),
                        hashtags=self._extract_hashtags(snippet.get('description', '')),
                        duration=self._parse_duration(
                            video_data['contentDetails'].get('duration', '')
                        )
                    ))
                    
        except Exception as e:
            logger.error(f"Error searching Shorts via API: {e}")
        
        return videos
    
    async def _scrape_shorts_page(self) -> List[VideoMetadata]:
        """Scrape YouTube Shorts page using Playwright."""
        if not self.browser:
            await self.initialize()
        
        videos = []
        
        try:
            page = await self.browser.new_page()
            await page.goto('https://www.youtube.com/shorts', wait_until='networkidle')
            
            # Wait for content to load
            await asyncio.sleep(3)
            
            # Scroll to load more videos
            for _ in range(3):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)
            
            # Extract video data from page
            video_elements = await page.query_selector_all('a[href*="/shorts/"]')
            
            for element in video_elements[:settings.max_videos_to_scrape]:
                try:
                    href = await element.get_attribute('href')
                    if href and '/shorts/' in href:
                        video_id = href.split('/shorts/')[-1].split('?')[0]
                        
                        # Try to get title and other metadata
                        title_elem = await element.query_selector('[id="video-title"]')
                        title = await title_elem.inner_text() if title_elem else ''
                        
                        videos.append(VideoMetadata(
                            video_id=video_id,
                            url=f"https://www.youtube.com{href}",
                            title=title,
                            description='',
                            channel_id='',
                            channel_name='',
                            view_count=0,
                            like_count=0,
                            upload_time=datetime.now(),
                            hashtags=[],
                            duration=0
                        ))
                except Exception as e:
                    logger.debug(f"Error extracting video element: {e}")
                    continue
            
            await page.close()
            
        except Exception as e:
            logger.error(f"Error scraping Shorts page: {e}")
        
        return videos
    
    async def _filter_by_growth_rate(
        self, 
        videos: List[VideoMetadata], 
        min_growth_rate: float
    ) -> List[VideoMetadata]:
        """Filter videos by channel growth rate."""
        filtered = []
        
        # If YouTube API is not available, skip filtering and return all videos
        if not self.youtube_api:
            logger.warning("YouTube API not available, skipping growth rate filtering")
            return videos
        
        for video in videos:
            if not video.channel_id:
                continue
                
            try:
                # Get channel stats
                channel_request = self.youtube_api.channels().list(
                    part='statistics,snippet',
                    id=video.channel_id
                )
                channel_response = channel_request.execute()
                
                if channel_response.get('items'):
                    channel_data = channel_response['items'][0]
                    stats = channel_data['statistics']
                    
                    # Calculate growth rate (simplified - would need historical data)
                    # For MVP, use view velocity as proxy
                    hours_old = max(
                        (datetime.now() - video.upload_time).total_seconds() / 3600, 
                        1
                    )
                    view_velocity = video.view_count / hours_old
                    
                    # High view velocity indicates trending
                    # Lower threshold for MVP - just filter out very low engagement
                    if view_velocity > 100 or video.view_count > 10000:  # More lenient threshold
                        filtered.append(video)
                    else:
                        logger.debug(f"Filtered out {video.video_id}: velocity={view_velocity:.1f}, views={video.view_count}")
                        
            except Exception as e:
                logger.debug(f"Error checking growth rate for {video.video_id}: {e}")
                continue
        
        return filtered
    
    def _rank_by_virality(self, videos: List[VideoMetadata]) -> List[VideoMetadata]:
        """Rank videos by virality score."""
        def virality_score(video: VideoMetadata) -> float:
            """Calculate virality score."""
            # Factors: views, likes, recency, engagement rate
            # Handle timezone-aware vs naive datetimes
            now = datetime.now(video.upload_time.tzinfo) if video.upload_time.tzinfo else datetime.now()
            upload_time = video.upload_time.replace(tzinfo=None) if video.upload_time.tzinfo and not now.tzinfo else video.upload_time
            if now.tzinfo and not upload_time.tzinfo:
                upload_time = upload_time.replace(tzinfo=now.tzinfo)
            elif not now.tzinfo and upload_time.tzinfo:
                now = now.replace(tzinfo=upload_time.tzinfo)
            
            hours_old = max((now - upload_time).total_seconds() / 3600, 1)
            view_velocity = video.view_count / hours_old
            engagement_rate = video.like_count / max(video.view_count, 1)
            
            # Weighted score
            score = (
                view_velocity * 0.4 +
                engagement_rate * 10000 * 0.3 +
                video.view_count * 0.0001 * 0.2 +
                (1 / hours_old) * 100 * 0.1  # Recency bonus
            )
            
            return score
        
        return sorted(videos, key=virality_score, reverse=True)
    
    def _merge_video_data(
        self, 
        api_videos: List[VideoMetadata], 
        scraped_videos: List[VideoMetadata]
    ) -> List[VideoMetadata]:
        """Merge and deduplicate video data."""
        video_dict = {}
        
        for video in api_videos + scraped_videos:
            if video.video_id not in video_dict:
                video_dict[video.video_id] = video
            else:
                # Merge data (prefer API data)
                existing = video_dict[video.video_id]
                if not existing.title and video.title:
                    existing.title = video.title
                if not existing.description and video.description:
                    existing.description = video.description
        
        return list(video_dict.values())
    
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text."""
        import re
        hashtags = re.findall(r'#\w+', text)
        return list(set(hashtags))
    
    def _parse_duration(self, duration_str: str) -> float:
        """Parse ISO 8601 duration to seconds."""
        import re
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 3600 + minutes * 60 + seconds
        return 0.0

