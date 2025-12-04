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
        Discover trending YouTube Shorts by finding channels with explosive growth.
        
        Strategy: Find channels that recently started posting shorts and had explosive growth,
        then analyze their successful videos to understand what made them go viral.
        
        Args:
            max_videos: Maximum number of videos to discover
            min_growth_rate: Minimum weekly growth rate (default 0.20 = 20%)
            
        Returns:
            List of VideoMetadata objects
        """
        max_videos = max_videos or settings.max_videos_to_scrape
        min_growth_rate = min_growth_rate or settings.min_growth_rate
        
        logger.info(f"Discovering trending Shorts via breakout channel analysis (max: {max_videos})")
        
        # NEW STRATEGY: Find channels with explosive growth from recent shorts
        breakout_videos = await self._find_breakout_channel_shorts(max_videos)
        logger.info(f"Found {len(breakout_videos)} videos from breakout channels")
        
        # Fallback: Use traditional search if breakout discovery doesn't find enough
        if len(breakout_videos) < max_videos // 2:
            logger.info("Not enough breakout videos found, supplementing with traditional search")
            api_videos = await self._search_shorts_via_api(max_videos // 2)
            logger.info(f"Found {len(api_videos)} videos via traditional API search")
            breakout_videos.extend(api_videos)
        
        # Filter for English and quality
        trending_videos = [v for v in breakout_videos if v.view_count > 1000]
        logger.info(f"After filtering (views > 1000): {len(trending_videos)} videos remain")
        
        # Rank by virality score
        ranked_videos = self._rank_by_virality(trending_videos)
        logger.info(f"After ranking: {len(ranked_videos)} videos")
        
        result = ranked_videos[:max_videos]
        logger.info(f"Returning {len(result)} videos (requested max: {max_videos})")
        return result
    
    async def _find_breakout_channel_shorts(self, max_videos: int) -> List[VideoMetadata]:
        """
        Find videos from channels that had explosive growth after posting shorts.
        
        Strategy:
        1. Search for recent popular shorts
        2. Get their channel IDs
        3. Check channel statistics (subscriber count, video count, recent growth)
        4. Identify channels that are "breaking out" (recent subscriber spike, few total videos)
        5. Get their recent shorts
        """
        videos = []
        
        if not self.youtube_api:
            logger.warning("YouTube API not available, skipping breakout channel discovery")
            return videos
        
        try:
            # Step 1: Find recent popular shorts to get channel IDs
            logger.info("Step 1: Finding recent popular shorts to identify channels...")
            search_request = self.youtube_api.search().list(
                part='snippet',
                q='#shorts',
                type='video',
                maxResults=50,  # Get more to find diverse channels
                order='viewCount',
                videoDuration='short',
                relevanceLanguage='en',
                publishedAfter=(datetime.now() - timedelta(days=14)).isoformat() + 'Z'  # Last 2 weeks
            )
            
            search_response = search_request.execute()
            
            # Collect unique channel IDs
            channel_ids = set()
            for item in search_response.get('items', []):
                channel_id = item['snippet'].get('channelId')
                if channel_id:
                    channel_ids.add(channel_id)
            
            logger.info(f"Found {len(channel_ids)} unique channels from recent shorts")
            
            # Step 2: Analyze channels to find "breakout" ones
            logger.info("Step 2: Analyzing channels for breakout patterns...")
            breakout_channels = []
            
            # Process channels in batches (YouTube API limit is 50 per request)
            channel_list = list(channel_ids)
            for i in range(0, min(len(channel_list), 50), 50):  # Limit to 50 to avoid quota issues
                batch = channel_list[i:i+50]
                
                # Get channel statistics
                channels_request = self.youtube_api.channels().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch)
                )
                channels_response = channels_request.execute()
                
                for channel_data in channels_response.get('items', []):
                    stats = channel_data.get('statistics', {})
                    snippet = channel_data.get('snippet', {})
                    
                    subscriber_count = int(stats.get('subscriberCount', 0))
                    video_count = int(stats.get('videoCount', 0))
                    view_count = int(stats.get('viewCount', 0))
                    
                    # Identify breakout channels:
                    # - Recent growth (subscriber count suggests recent spike)
                    # - Small-medium size (10K-500K subscribers - sweet spot for breakout)
                    # - Few videos relative to subscribers (high sub-to-video ratio = explosive growth)
                    # - High view-to-sub ratio (viral content)
                    
                    if subscriber_count < 1000 or subscriber_count > 2000000:  # Skip too small or too large
                        continue
                    
                    if video_count == 0:
                        continue
                    
                    # Calculate ratios
                    sub_to_video_ratio = subscriber_count / max(video_count, 1)
                    view_to_sub_ratio = view_count / max(subscriber_count, 1)
                    
                    # Breakout indicators:
                    # - High sub-to-video ratio (>100 = each video brought many subs)
                    # - High view-to-sub ratio (>50 = viral reach)
                    # - Recent channel (created in last 2 years)
                    
                    created_at = snippet.get('publishedAt', '')
                    if created_at:
                        try:
                            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            days_old = (datetime.now(created_date.tzinfo) - created_date).days
                            
                            # Prefer channels created in last 2 years
                            if days_old > 730:
                                continue
                        except:
                            pass
                    
                    # Score breakout potential
                    breakout_score = 0
                    if sub_to_video_ratio > 100:
                        breakout_score += 3
                    elif sub_to_video_ratio > 50:
                        breakout_score += 2
                    elif sub_to_video_ratio > 20:
                        breakout_score += 1
                    
                    if view_to_sub_ratio > 100:
                        breakout_score += 2
                    elif view_to_sub_ratio > 50:
                        breakout_score += 1
                    
                    # Prefer channels with 10-500K subs (sweet spot)
                    if 10000 <= subscriber_count <= 500000:
                        breakout_score += 2
                    elif 1000 <= subscriber_count < 10000:
                        breakout_score += 1
                    
                    if breakout_score >= 3:  # Minimum threshold
                        breakout_channels.append({
                            'channel_id': channel_data['id'],
                            'channel_title': snippet.get('title', ''),
                            'subscriber_count': subscriber_count,
                            'video_count': video_count,
                            'breakout_score': breakout_score,
                            'sub_to_video_ratio': sub_to_video_ratio,
                            'view_to_sub_ratio': view_to_sub_ratio
                        })
                        logger.info(f"Found breakout channel: {snippet.get('title', 'Unknown')} "
                                  f"(subs: {subscriber_count:,}, videos: {video_count}, "
                                  f"score: {breakout_score}, sub/video: {sub_to_video_ratio:.1f})")
            
            # Sort by breakout score
            breakout_channels.sort(key=lambda x: x['breakout_score'], reverse=True)
            logger.info(f"Identified {len(breakout_channels)} breakout channels")
            
            # Step 3: Get recent shorts from breakout channels
            logger.info("Step 3: Getting recent shorts from breakout channels...")
            for channel_info in breakout_channels[:10]:  # Limit to top 10 breakout channels
                channel_id = channel_info['channel_id']
                
                try:
                    # Get channel's uploads playlist
                    channels_request = self.youtube_api.channels().list(
                        part='contentDetails',
                        id=channel_id
                    )
                    channels_response = channels_request.execute()
                    
                    if not channels_response.get('items'):
                        continue
                    
                    uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                    
                    # Get recent videos from uploads playlist
                    playlist_request = self.youtube_api.playlistItems().list(
                        part='snippet,contentDetails',
                        playlistId=uploads_playlist_id,
                        maxResults=10  # Get last 10 videos
                    )
                    playlist_response = playlist_request.execute()
                    
                    # Get video IDs
                    video_ids = [item['contentDetails']['videoId'] for item in playlist_response.get('items', [])]
                    
                    if not video_ids:
                        continue
                    
                    # Get video details (filter for shorts)
                    videos_request = self.youtube_api.videos().list(
                        part='snippet,statistics,contentDetails',
                        id=','.join(video_ids)
                    )
                    videos_response = videos_request.execute()
                    
                    for video_data in videos_response.get('items', []):
                        snippet = video_data['snippet']
                        stats = video_data['statistics']
                        content_details = video_data.get('contentDetails', {})
                        
                        # Check if it's a short (duration < 60 seconds or has #shorts in title)
                        duration_str = content_details.get('duration', '')
                        is_short = duration_str and self._parse_duration(duration_str) <= 60
                        title_lower = snippet.get('title', '').lower()
                        has_shorts_tag = '#shorts' in title_lower or 'short' in title_lower
                        
                        if not (is_short or has_shorts_tag):
                            continue
                        
                        # Language filtering
                        default_language = snippet.get('defaultLanguage', '').lower()
                        default_audio_language = snippet.get('defaultAudioLanguage', '').lower()
                        
                        if default_language and default_language not in ['en', 'en-us', 'en-gb']:
                            continue
                        if default_audio_language and default_audio_language not in ['en', 'en-us', 'en-gb']:
                            continue
                        
                        video_id = video_data['id']
                        videos.append(VideoMetadata(
                            video_id=video_id,
                            url=f"https://www.youtube.com/shorts/{video_id}",
                            title=snippet.get('title', ''),
                            description=snippet.get('description', ''),
                            channel_id=channel_id,
                            channel_name=snippet.get('channelTitle', ''),
                            view_count=int(stats.get('viewCount', 0)),
                            like_count=int(stats.get('likeCount', 0)),
                            upload_time=datetime.fromisoformat(
                                snippet['publishedAt'].replace('Z', '+00:00')
                            ),
                            hashtags=self._extract_hashtags(snippet.get('description', '')),
                            default_language=default_language or None,
                            default_audio_language=default_audio_language or None,
                            duration=self._parse_duration(duration_str)
                        ))
                        
                        if len(videos) >= max_videos:
                            break
                    
                    if len(videos) >= max_videos:
                        break
                        
                except Exception as e:
                    logger.warning(f"Error getting videos from channel {channel_id}: {e}")
                    continue
            
            logger.info(f"Collected {len(videos)} videos from {len(breakout_channels)} breakout channels")
            
        except Exception as e:
            logger.error(f"Error in breakout channel discovery: {e}", exc_info=True)
        
        return videos
    
    async def _search_shorts_via_api(self, max_results: int) -> List[VideoMetadata]:
        """Search for Shorts using YouTube Data API."""
        videos = []
        
        if not self.youtube_api:
            logger.warning("YouTube API not available, skipping API search")
            return videos
        
        try:
            # Search for Shorts with variety - use different search terms and orders
            import random
            
            # Vary search terms to get different results
            search_terms = [
                '#shorts',
                'shorts',
                'short video',
                'viral shorts',
                'trending shorts',
                'funny shorts',
                'comedy shorts'
            ]
            search_term = random.choice(search_terms)
            
            # Vary sort order to get different results
            sort_orders = ['viewCount', 'rating', 'relevance', 'date']
            sort_order = random.choice(sort_orders)
            
            # Vary time range to get fresher content
            days_back = random.choice([1, 2, 3, 5, 7])
            
            logger.info(f"Searching with term: '{search_term}', order: '{sort_order}', days: {days_back}")
            
            # Search for Shorts (duration < 4 minutes, typically < 60 seconds)
            # Filter for English language only
            request = self.youtube_api.search().list(
                part='snippet',
                q=search_term,
                type='video',
                maxResults=min(max_results, 50),
                order=sort_order,
                videoDuration='short',
                relevanceLanguage='en',  # Prefer English content
                publishedAfter=(datetime.now() - timedelta(days=days_back)).isoformat() + 'Z'
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
                    
                    # Filter for English language videos only - STRICT FILTERING
                    default_language = snippet.get('defaultLanguage', '').lower()
                    default_audio_language = snippet.get('defaultAudioLanguage', '').lower()
                    title = snippet.get('title', '').lower()
                    description = snippet.get('description', '').lower()
                    
                    # Check 1: Explicit language tags (must be English if set)
                    if default_language and default_language not in ['en', 'en-us', 'en-gb']:
                        logger.info(f"Skipping video {video_id}: explicit language={default_language} (not English)")
                        continue
                    if default_audio_language and default_audio_language not in ['en', 'en-us', 'en-gb']:
                        logger.info(f"Skipping video {video_id}: explicit audio_language={default_audio_language} (not English)")
                        continue
                    
                    # Check 2: If no language tags, check title/description for non-English indicators
                    # Common non-English patterns
                    non_english_patterns = [
                        r'[\u4e00-\u9fff]',  # Chinese
                        r'[\u3040-\u309f\u30a0-\u30ff]',  # Japanese
                        r'[\u0400-\u04ff]',  # Cyrillic
                        r'[\u0600-\u06ff]',  # Arabic
                        r'[\u0590-\u05ff]',  # Hebrew
                        r'[\u0e00-\u0e7f]',  # Thai
                        r'[\u1100-\u11ff\uac00-\ud7af]',  # Korean
                    ]
                    
                    import re
                    has_non_english = False
                    for pattern in non_english_patterns:
                        if re.search(pattern, title) or re.search(pattern, description):
                            has_non_english = True
                            break
                    
                    if has_non_english:
                        logger.info(f"Skipping video {video_id}: detected non-English characters in title/description")
                        continue
                    
                    # Check 3: If language is not set, require at least some English indicators
                    # (common English words or hashtags)
                    if not default_language and not default_audio_language:
                        english_indicators = ['#shorts', 'the', 'and', 'or', 'is', 'are', 'was', 'were', 'this', 'that', 'with', 'from']
                        has_english_indicators = any(indicator in title or indicator in description for indicator in english_indicators)
                        # If title/description is very short and has no English indicators, skip
                        if len(title) < 10 and len(description) < 20 and not has_english_indicators:
                            logger.info(f"Skipping video {video_id}: no language tags and no clear English indicators")
                            continue
                    
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

