import re
import pytesseract
from io import BytesIO
from config import settings, logger
from services.image_processor import preprocess_image


def extract_text_from_image(image_file: BytesIO) -> str:
    """Extract text using optimized OCR settings with error handling."""
    try:
        # Set Tesseract path from settings
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path
        
        processed_img = preprocess_image(image_file)
        
        # Apply OCR with custom configuration
        text = pytesseract.image_to_string(
            processed_img, 
            config=settings.ocr_config
        )
        
        # Apply basic text cleaning
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = re.sub(r'[^\w\s.,:\-\(\)]', '', text)  # Remove special characters
        
        return text.strip()
    except Exception as e:
        logger.error(f"OCR extraction error: {e}")
        
        # If Tesseract is not installed, fall back to mock OCR service
        if "tesseract is not installed" in str(e) or "TesseractNotFound" in str(e):
            logger.warning("Falling back to mock OCR service since Tesseract is not available")
            try:
                from services.mock_ocr_service import extract_text_from_image_mock
                return extract_text_from_image_mock(image_file)
            except Exception as mock_error:
                logger.error(f"Mock OCR service also failed: {mock_error}")
                raise ValueError(f"Failed to extract text from image: {e}")
        
        raise ValueError(f"Failed to extract text from image: {e}")