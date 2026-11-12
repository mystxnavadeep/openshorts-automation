"""
Application configuration loaded from environment variables and .env file.
"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GitHub configuration
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_OWNER: str = os.getenv("GITHUB_OWNER", "mystxnavadeep")
    GITHUB_REPO: str = os.getenv("GITHUB_REPO", "openshorts-automation")
    GITHUB_WORKFLOW_ID: str = os.getenv("GITHUB_WORKFLOW_ID", "openshorts.yml")
    GITHUB_BRANCH: str = os.getenv("GITHUB_BRANCH", "main")

    # Host & Port binding
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    # Processing defaults
    DEFAULT_GDRIVE_FOLDER: str = os.getenv("DEFAULT_GDRIVE_FOLDER", "OpenShorts")
    DEFAULT_OUTPUT_FORMAT: str = os.getenv("DEFAULT_OUTPUT_FORMAT", "vertical")
    DEFAULT_TARGET_CLIPS: int = int(os.getenv("DEFAULT_TARGET_CLIPS", "3"))
    DEFAULT_CLIP_MIN_SECONDS: int = int(os.getenv("DEFAULT_CLIP_MIN_SECONDS", "15"))
    DEFAULT_CLIP_MAX_SECONDS: int = int(os.getenv("DEFAULT_CLIP_MAX_SECONDS", "60"))

    class Config:
        env_file = ".env"
        extra = "ignore"

    def get_allowed_origins(self) -> List[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    def get_public_config(self) -> dict:
        """Returns safe configuration values to frontend without exposing tokens."""
        return {
            "github_owner": self.GITHUB_OWNER,
            "github_repo": self.GITHUB_REPO,
            "workflow_id": self.GITHUB_WORKFLOW_ID,
            "branch": self.GITHUB_BRANCH,
            "default_gdrive_folder": self.DEFAULT_GDRIVE_FOLDER,
            "default_output_format": self.DEFAULT_OUTPUT_FORMAT,
            "default_target_clips": self.DEFAULT_TARGET_CLIPS,
            "default_clip_min_seconds": self.DEFAULT_CLIP_MIN_SECONDS,
            "default_clip_max_seconds": self.DEFAULT_CLIP_MAX_SECONDS,
            "token_configured": bool(self.GITHUB_TOKEN and len(self.GITHUB_TOKEN) > 5)
        }


settings = Settings()
