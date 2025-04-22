from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables or .env file."""
    groq_api_key: str = "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"
    api_key: str = "dev_key"  # API key for securing endpoints
    ocr_config: str = "--oem 3 --psm 6"
    tesseract_path: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Path to Tesseract executable
    fuzzy_match_threshold: int = 80
    enable_ai_correction: bool = True
    debug_mode: bool = False
    log_level: str = "INFO"
    max_image_size_mb: int = 10
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create global settings instance
settings = Settings()

# Setup logging
import logging

logging_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(
    level=logging_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("prescription_api.log")
    ]
)
logger = logging.getLogger("prescription_analyzer")