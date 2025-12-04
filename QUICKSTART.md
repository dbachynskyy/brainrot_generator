# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 2. Get API Keys

**Required:**
- **OpenAI API Key**: Get from https://platform.openai.com/api-keys
- **YouTube API Key**: Get from https://console.cloud.google.com/apis/credentials

**Optional (for full functionality):**
- Video generation APIs (Runway, Pika, Kling, Luma)
- Publishing API credentials

### 3. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your keys:
# OPENAI_API_KEY=sk-...
# YOUTUBE_API_KEY=...
```

### 4. Run Your First Discovery

```bash
# Simple discovery example
python example.py discovery

# Or run the full pipeline
python example.py full
```

### 5. Start API Server (Optional)

```bash
python api.py
# Visit http://localhost:8000
```

## 📋 What Each Example Does

### `python example.py discovery`
- Discovers top 10 trending YouTube Shorts
- Shows video titles, views, likes, URLs
- No video processing (fast)

### `python example.py full`
- Full pipeline: discover → analyze → generate script
- Processes 20 videos
- Creates trend blueprints
- Generates a new script
- Takes longer but shows complete workflow

### `python example.py custom`
- Step-by-step workflow
- Shows individual agent operations
- Good for understanding the system

## 🎯 Next Steps

1. **Customize Brand Style**: Edit `example.py` to add your brand voice
2. **Adjust Settings**: Modify `config.py` or `.env` for your needs
3. **Add Video Generators**: Configure API keys for Runway/Pika/Kling/Luma
4. **Set Up Publishing**: Configure OAuth for YouTube/TikTok/Instagram

## ⚠️ Common Issues

### "YouTube API not available"
- Make sure you've set `YOUTUBE_API_KEY` in `.env`
- Check that the API key is valid and has YouTube Data API v3 enabled

### "WhisperX not available"
- WhisperX is optional for MVP
- Install with: `pip install whisperx`
- Requires CUDA for GPU acceleration

### "Playwright browser not found"
- Run: `playwright install chromium`

### FFmpeg errors
- Install FFmpeg: https://ffmpeg.org/download.html
- Make sure it's in your PATH

## 📚 Learn More

- See `README.md` for full documentation
- Check `orchestrator.py` for pipeline details
- Explore `agents/` directory for individual agent implementations

