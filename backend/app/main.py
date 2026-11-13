"""
OpenShorts Automation FastAPI Server
Provides secure backend for GitHub Actions workflow dispatch, execution tracking,
and serves the mobile-optimized Tailscale dashboard.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import settings
from .github_client import github_client
from .security import (
    canonical_youtube_url,
    check_and_record_dispatch,
    extract_youtube_video_id,
    get_tailscale_ip,
)

app = FastAPI(
    title="OpenShorts Automation API",
    description="Backend API connecting OpenShorts Dashboard to GitHub Actions via Tailscale",
    version="1.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProcessRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL")
    output_format: Optional[str] = Field("vertical", description="vertical, square, horizontal, or auto")
    gemini_model: Optional[str] = Field("gemini-3.1-flash-lite", description="Gemini model for viral moment detection")
    whisper_model: Optional[str] = Field("base", description="Faster-Whisper model size (base, small, tiny)")
    subtitle_language: Optional[str] = Field("auto", description="Subtitle language: auto, te (Telugu), hi (Hindi), en (English)")
    subtitle_script: Optional[str] = Field("romanized", description="Subtitle style: romanized (English alphabet only), original")
    auto_hook: Optional[bool] = Field(True, description="Generate and overlay AI viral hook text")
    workers: Optional[str] = Field("1", description="Concurrent clip render workers")
    gdrive_folder: Optional[str] = Field("OpenShorts", description="Target folder name in Google Drive")


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """System health check endpoint verifying GitHub API connectivity and Tailscale status."""
    tailscale_ip = get_tailscale_ip()
    gh_auth = await github_client.verify_auth()

    return {
        "status": "healthy" if gh_auth.get("authenticated") else "degraded",
        "tailscale": {
            "active": bool(tailscale_ip),
            "ip": tailscale_ip or "Not detected (running on localhost or container)"
        },
        "github": gh_auth,
        "repo": f"{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}",
        "workflow": settings.GITHUB_WORKFLOW_ID
    }


@app.get("/api/config")
async def get_config():
    """Provides safe configuration parameters to the dashboard frontend."""
    tailscale_ip = get_tailscale_ip()
    pub_config = settings.get_public_config()
    pub_config["tailscale_ip"] = tailscale_ip
    return pub_config


@app.post("/api/process")
async def process_video(req: ProcessRequest):
    """
    Validates input YouTube URL, protects against duplicate submissions,
    and triggers the GitHub Actions workflow_dispatch event securely.
    """
    # 1. Validate YouTube URL
    video_id = extract_youtube_video_id(req.url)
    if not video_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YouTube URL. Please provide a valid YouTube video link (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...)"
        )

    canonical_url = canonical_youtube_url(video_id)

    # 2. Check for duplicate dispatch within dedup window
    allowed, remaining = check_and_record_dispatch(video_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"A workflow for this video was already submitted recently. Please wait {remaining} seconds before re-submitting."
        )

    # 3. Format inputs for official OpenShorts GitHub Actions workflow_dispatch
    workflow_inputs = {
        "youtube_url": canonical_url,
        "output_format": req.output_format or "vertical",
        "gemini_model": req.gemini_model or "gemini-3.1-flash-lite",
        "whisper_model": req.whisper_model or "base",
        "subtitle_language": req.subtitle_language or "auto",
        "subtitle_script": req.subtitle_script or "romanized",
        "auto_hook": "true" if req.auto_hook else "false",
        "workers": str(req.workers or "1"),
        "gdrive_folder": req.gdrive_folder or "OpenShorts"
    }

    # 4. Trigger GitHub Actions workflow
    try:
        dispatch_result = await github_client.dispatch_workflow(inputs=workflow_inputs)
        return {
            "status": "success",
            "message": "GitHub Actions processing workflow has been triggered successfully!",
            "video_id": video_id,
            "canonical_url": canonical_url,
            "inputs": workflow_inputs,
            "dispatch": dispatch_result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger GitHub Actions workflow: {str(e)}"
        )


@app.get("/api/workflows")
async def list_workflows(limit: int = 10):
    """Lists recent workflow executions and their status."""
    try:
        runs = await github_client.list_runs(limit=limit)
        return {"runs": runs}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query workflow runs: {str(e)}"
        )


@app.get("/api/workflows/{run_id}")
async def get_workflow_details(run_id: int):
    """Fetches details, execution steps, logs, and artifacts for a specific workflow run."""
    try:
        details = await github_client.get_run_details(run_id=run_id)
        return details
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to fetch workflow run details: {str(e)}"
        )


# Mount dashboard static assets
dashboard_dir = Path(__file__).resolve().parent.parent.parent / "dashboard"

if dashboard_dir.exists():
    app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

    @app.api_route("/", methods=["GET", "HEAD"])
    async def serve_dashboard():
        index_file = dashboard_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse({"message": "OpenShorts API is running. index.html not found in dashboard/"})
