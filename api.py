"""FastAPI server for Brainrot Generator."""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import asyncio
import logging

from orchestrator import BrainrotOrchestrator
from models import TrendBlueprint, Script, GeneratedVideo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Brainrot Generator API", version="1.0.0")

# Global orchestrator instance
orchestrator: Optional[BrainrotOrchestrator] = None


@app.on_event("startup")
async def startup():
    """Initialize orchestrator on startup."""
    global orchestrator
    orchestrator = BrainrotOrchestrator()
    await orchestrator.initialize()
    logger.info("API server started")


@app.on_event("shutdown")
async def shutdown():
    """Clean up on shutdown."""
    global orchestrator
    if orchestrator:
        await orchestrator.close()
    logger.info("API server stopped")


class PipelineRequest(BaseModel):
    """Request for running pipeline."""
    max_videos: Optional[int] = 50
    generate_video: bool = True
    publish: bool = False
    brand_style: Optional[str] = None


class ScriptRequest(BaseModel):
    """Request for generating script."""
    blueprint_id: str
    brand_style: Optional[str] = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Brainrot Generator API",
        "version": "1.0.0",
        "endpoints": [
            "/discover",
            "/analyze",
            "/patterns",
            "/generate-script",
            "/generate-video",
            "/publish",
            "/pipeline"
        ]
    }


@app.post("/pipeline")
async def run_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run the full pipeline."""
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    try:
        results = await orchestrator.run_full_pipeline(
            max_videos=request.max_videos,
            generate_video=request.generate_video,
            publish=request.publish,
            brand_style=request.brand_style
        )
        return JSONResponse(content=results)
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/discover")
async def discover_videos(max_videos: int = 50):
    """Discover trending videos."""
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    
    try:
        videos = await orchestrator.discovery.discover_trending_shorts(max_videos=max_videos)
        return {"videos": [v.dict() for v in videos]}
    except Exception as e:
        logger.error(f"Discovery error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "orchestrator_initialized": orchestrator is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

