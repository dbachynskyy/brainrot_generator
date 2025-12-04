# 🧠 Brainrot Generator

An AI-powered pipeline that discovers trending YouTube Shorts, analyzes their patterns, and generates new viral content following those trends.

## 🎯 Overview

The Brainrot Generator is a multi-agent system that automates the entire content creation pipeline:

1. **Discovery Agent** - Scrapes YouTube Shorts for fast-growing channels and trending videos
2. **Extraction Agent** - Downloads videos and extracts frames, transcripts, and references
3. **Analysis Agent** - Analyzes content structure, hooks, visual style, and trends
4. **Pattern Agent** - Identifies patterns and creates trend blueprints
5. **Content Generation Agent** - Creates new scripts based on identified patterns
6. **Production Agent** - Generates videos using AI video generators (Runway, Pika, Kling, Luma)
7. **Publishing Agent** - Auto-uploads to YouTube Shorts, TikTok, and Instagram Reels

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- FFmpeg installed and in PATH
- YouTube API key
- OpenAI API key (for analysis and script generation)
- (Optional) Video generation API keys (Runway, Pika, Kling, Luma)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd brainrot_generator
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Install Playwright browsers**
```bash
playwright install chromium
```

5. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

### Environment Configuration

**Important**: Set `BRAINROT_DEV=test` in your `.env` file for testing. In test mode:
- Videos are saved locally to `data/test_published/` instead of being uploaded
- Metadata is saved as JSON files alongside videos
- No actual publishing occurs (safe for testing)

Set `BRAINROT_DEV=prod` when ready to actually publish to platforms.

### Required API Keys

Minimum required:
- `OPENAI_API_KEY` - For content analysis and script generation
- `YOUTUBE_API_KEY` - For discovering and scraping YouTube Shorts

Optional (for full functionality):
- `RUNWAY_API_KEY` - For Runway Gen-3 video generation
- `PIKA_API_KEY` - For Pika video generation
- `KLING_API_KEY` - For Kling AI video generation
- `LUMA_API_KEY` - For Luma Dream Machine video generation
- Publishing API credentials (YouTube OAuth, TikTok, Instagram)

## 📖 Usage

### Command Line

Run the MVP pipeline:
```bash
python orchestrator.py
```

This will:
1. Discover top 50 trending Shorts
2. Download and analyze 10 videos
3. Identify trend patterns
4. Generate a new script
5. Create a video (if API keys are configured)

### API Server

Start the FastAPI server:
```bash
python api.py
# Or with uvicorn:
uvicorn api:app --reload
```

API endpoints:
- `GET /` - API information
- `GET /health` - Health check
- `GET /discover?max_videos=50` - Discover trending videos
- `POST /pipeline` - Run full pipeline

Example API request:
```bash
curl -X POST "http://localhost:8000/pipeline" \
  -H "Content-Type: application/json" \
  -d '{
    "max_videos": 50,
    "generate_video": true,
    "publish": false,
    "brand_style": "energetic and motivational"
  }'
```

### Python Script

```python
from orchestrator import BrainrotOrchestrator
import asyncio

async def main():
    orchestrator = BrainrotOrchestrator()
    await orchestrator.initialize()
    
    results = await orchestrator.run_full_pipeline(
        max_videos=50,
        generate_video=True,
        publish=False,
        brand_style="Your brand style here"
    )
    
    print(f"Generated script: {results['generated_script']['title']}")
    
    await orchestrator.close()

asyncio.run(main())
```

## 🏗️ Architecture

### Agent Workflow

```
Discovery Agent
    ↓
Extraction Agent (downloads, extracts frames/transcript)
    ↓
Analysis Agent (analyzes content structure, style, trends)
    ↓
Pattern Agent (identifies patterns, creates blueprints)
    ↓
Content Generation Agent (creates new script)
    ↓
Production Agent (generates video using AI tools)
    ↓
Publishing Agent (uploads to platforms)
```

### Key Components

#### Discovery Agent
- Uses YouTube Data API v3 to search for Shorts
- Uses Playwright to scrape Shorts page for additional data
- Filters by growth rate and engagement metrics
- Ranks by virality score

#### Extraction Agent
- Downloads videos using `yt-dlp`
- Extracts frames at configurable intervals
- Extracts transcripts using WhisperX
- Identifies key reference frames

#### Analysis Agent
- Uses GPT-4 to analyze:
  - Hook type and structure
  - Plot and story arc
  - Visual style and aesthetics
  - Character roles
  - Trend category
  - Audio style

#### Pattern Agent
- Identifies common patterns across videos
- Creates trend blueprints with:
  - Average length
  - Hook patterns
  - Plot arcs
  - Visual styles
  - Editing patterns
  - CTA patterns

#### Content Generation Agent
- Generates scripts following trend blueprints
- Injects brand/style customization
- Creates shot lists and visual instructions
- Generates dialogue and captions

#### Production Agent
- Selects best video generator based on style
- Supports: Runway Gen-3, Pika, Kling AI, Luma Dream Machine
- Adds subtitles and formatting

#### Publishing Agent
- Auto-generates titles, descriptions, hashtags
- Uploads to YouTube Shorts, TikTok, Instagram Reels
- Supports scheduling

## 📁 Project Structure

```
brainrot_generator/
├── agents/
│   ├── __init__.py
│   ├── discovery_agent.py      # YouTube scraping & trend discovery
│   ├── extraction_agent.py     # Video download & frame extraction
│   ├── analysis_agent.py        # Content analysis using LLMs
│   ├── pattern_agent.py         # Pattern identification
│   ├── content_generation_agent.py  # Script generation
│   ├── production_agent.py      # Video generation orchestration
│   └── publishing_agent.py      # Platform publishing
├── data/
│   ├── extracted/               # Downloaded videos and frames
│   └── generated/               # Generated videos
├── api.py                       # FastAPI server
├── orchestrator.py              # Main pipeline orchestrator
├── config.py                    # Configuration settings
├── models.py                    # Data models
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
└── README.md                    # This file
```

## ⚙️ Configuration

Edit `config.py` or set environment variables:

- `BRAINROT_DEV` - Set to `"test"` or `"prod"` (default: `"test"`)
  - **test**: Videos saved locally to `data/test_published/` with metadata JSON
  - **prod**: Videos actually published to platforms
- `MAX_VIDEOS_TO_SCRAPE` - Maximum videos to discover (default: 50)
- `MIN_GROWTH_RATE` - Minimum weekly growth rate (default: 0.20 = 20%)
- `FRAME_EXTRACTION_INTERVAL` - Seconds between frame extractions (default: 0.5)
- `LOG_LEVEL` - Logging level (default: INFO)

## 🔧 Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests (when implemented)
pytest
```

### Adding New Video Generators

1. Add API key to `config.py` and `.env.example`
2. Implement generation method in `ProductionAgent`
3. Add selection logic in `_select_best_generator()`

### Adding New Platforms

1. Implement publishing method in `PublishingAgent`
2. Add platform to `PublishingMetadata.platforms` enum
3. Update API endpoints if needed

## 🚧 MVP Status

Current implementation includes:
- ✅ Discovery agent (YouTube API + Playwright)
- ✅ Extraction agent (yt-dlp, frame extraction, WhisperX)
- ✅ Analysis agent (GPT-4 based analysis)
- ✅ Pattern agent (pattern identification)
- ✅ Content generation agent (script generation)
- ✅ Production agent (structure ready, API integrations pending)
- ✅ Publishing agent (structure ready, API integrations pending)
- ✅ FastAPI orchestrator
- ✅ Full pipeline workflow

**Note**: Video generation and publishing API integrations are structured but require actual API implementations. The framework is ready for integration.

## 📝 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]

## 📧 Contact

[Add contact information here]

## 🙏 Acknowledgments

- YouTube Data API v3
- OpenAI GPT-4
- WhisperX for transcription
- yt-dlp for video downloading
- Playwright for web scraping
- Various AI video generation platforms
