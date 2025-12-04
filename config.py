"""
Configuration module for API credentials and settings.
"""
import os
from typing import Optional
from dotenv import load_dotenv
load_dotenv()


class Config:
    """Central configuration for all API clients."""
    
    # Writer API
    WRITER_API_KEY: str = os.getenv("WRITER_API_KEY", "")
    WRITER_API_URL: str = "https://api.writer.com/v1/completions"
    WRITER_MODEL: str = "palmyra-x-004"
    WRITER_MAX_UNITS: int = 100000
    
    # Monday.com API
    MONDAY_API_KEY: str = os.getenv("MONDAY_API_KEY", "")
    MONDAY_API_URL: str = "https://api.monday.com/v2"
    
    # Processing settings
    CHUNK_OVERLAP: int = 2  # Number of items to overlap between chunks
    
    @classmethod
    def validate(cls) -> None:
        """Validate that required API keys are set."""
        if not cls.WRITER_API_KEY:
            raise ValueError("WRITER_API_KEY environment variable is required")
        if not cls.MONDAY_API_KEY:
            raise ValueError("MONDAY_API_KEY environment variable is required")
    
    @classmethod
    def get_writer_headers(cls) -> dict[str, str]:
        """Get headers for Writer API requests."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.WRITER_API_KEY}"
        }
    
    @classmethod
    def get_monday_headers(cls) -> dict[str, str]:
        """Get headers for Monday.com API requests."""
        return {
            "Content-Type": "application/json",
            "Authorization": cls.MONDAY_API_KEY
        }