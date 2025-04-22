import os
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from config import settings, logger


def validate_image(image_file: BytesIO) -> bool:
    """Validate the uploaded image file."""
    # Check file size
    image_file.seek(0, os.SEEK_END)
    file_size = image_file.tell() / (1024 * 1024)  # Convert to MB
    image_file.seek(0)  # Reset file pointer
    
    if file_size > settings.max_image_size_mb:
        raise ValueError(f"Image size exceeds the {settings.max_image_size_mb}MB limit")
    
    # Validate image format
    try:
        with Image.open(image_file) as img:
            img.verify()
            image_file.seek(0)  # Reset file pointer after verification
            return True
    except Exception as e:
        raise ValueError(f"Invalid image file: {e}")


def preprocess_image(image_file: BytesIO) -> Image.Image:
    """Enhance image for better OCR accuracy with advanced techniques."""
    try:
        # Open and convert to grayscale
        img = Image.open(image_file).convert("L")
        img_np = np.array(img)
        
        # Denoise
        img_np = cv2.fastNlMeansDenoising(img_np, None, 10, 7, 21)
        
        # Apply Adaptive Thresholding
        img_np = cv2.adaptiveThreshold(
            img_np, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 31, 2
        )
        
        # Apply dilation followed by erosion to close gaps in letters
        kernel = np.ones((1, 1), np.uint8)
        img_np = cv2.morphologyEx(img_np, cv2.MORPH_CLOSE, kernel)
        
        # Apply contrast stretching
        p2, p98 = np.percentile(img_np, (2, 98))
        img_np = np.clip(img_np, p2, p98)
        img_np = ((img_np - p2) / (p98 - p2) * 255).astype(np.uint8)
        
        return Image.fromarray(img_np)
    except Exception as e:
        logger.error(f"Image preprocessing error: {e}")
        raise ValueError(f"Failed to preprocess image: {e}")