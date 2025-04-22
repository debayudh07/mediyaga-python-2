import time
from io import BytesIO
from uuid import uuid4
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks, status
from fastapi.security import APIKeyHeader

from config import settings, logger
from models.schemas import PrescriptionResponse, JobStatus, PrescriptionData
from services.image_processor import validate_image
from services.ocr_service import extract_text_from_image
from services.text_processor import correct_text_with_groq, extract_structured_medications
from services.prescription_parser import parse_prescription_text
from utils.job_store import JOB_STORE

router = APIRouter()

# API Key security
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify the API key for protected endpoints."""
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return api_key

# Background task for async processing
def process_prescription_image(job_id: str, image_bytes: BytesIO):
    """Background task to process prescription image."""
    try:
        start_time = time.time()
        
        # Validate and extract text
        validate_image(image_bytes)
        extracted_text = extract_text_from_image(image_bytes)
        
        # AI-Powered Correction
        corrected_text = correct_text_with_groq(extracted_text) if settings.enable_ai_correction else extracted_text
        
        # Extract structured medication data
        medications = extract_structured_medications(corrected_text)
        
        # Parse structured data
        prescription_details = parse_prescription_text(corrected_text)
        
        # Add medications to the response
        prescription_details.medications = medications
        
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Store result
        JOB_STORE[job_id] = {
            "status": "completed",
            "result": PrescriptionResponse(
                success=True,
                raw_text=extracted_text,
                corrected_text=corrected_text,
                parsed_data=prescription_details,
                medications=medications,
                processing_time_ms=processing_time
            )
        }
        logger.info(f"Job {job_id} completed successfully in {processing_time:.2f}ms")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        JOB_STORE[job_id] = {
            "status": "failed",
            "result": PrescriptionResponse(
                success=False,
                error=str(e)
            )
        }

@router.get("/", tags=["Info"])
async def root():
    """API info endpoint."""
    return {
        "name": "Prescription Analysis API",
        "version": "2.0.0",
        "status": "operational"
    }

@router.post("/analyze-prescription/", response_model=PrescriptionResponse, tags=["Prescriptions"])
async def analyze_prescription(
    prescription: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    """Synchronously analyze a prescription image."""
    try:
        start_time = time.time()
        
        # Read and validate image
        image_bytes = BytesIO(await prescription.read())
        validate_image(image_bytes)
        
        # Extract text
        extracted_text = extract_text_from_image(image_bytes)
        
        # AI-Powered Correction
        corrected_text = correct_text_with_groq(extracted_text) if settings.enable_ai_correction else extracted_text
        
        # Extract structured medication data
        medications = extract_structured_medications(corrected_text)
        
        # Parse structured data
        prescription_details = parse_prescription_text(corrected_text)
        
        # Add medications to the response
        prescription_details.medications = medications
        
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        logger.info(f"Processed prescription in {processing_time:.2f}ms")
        
        return PrescriptionResponse(
            success=True,
            raw_text=extracted_text,
            corrected_text=corrected_text,
            parsed_data=prescription_details,
            medications=medications,
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"Prescription analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/analyze-prescription-async/", response_model=JobStatus, tags=["Prescriptions"])
async def analyze_prescription_async(
    background_tasks: BackgroundTasks,
    prescription_image: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    """Asynchronously analyze a prescription image."""
    try:
        # Generate job ID
        job_id = str(uuid4())
        
        # Store image data
        image_bytes = BytesIO(await prescription_image.read())
        
        # Create job entry
        JOB_STORE[job_id] = {"status": "processing"}
        
        # Start background processing
        background_tasks.add_task(process_prescription_image, job_id, image_bytes)
        
        logger.info(f"Started async job {job_id}")
        return JobStatus(job_id=job_id, status="processing")
        
    except Exception as e:
        logger.error(f"Failed to start async job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/job-status/{job_id}", response_model=JobStatus, tags=["Jobs"])
async def get_job_status(job_id: str, api_key: str = Depends(verify_api_key)):
    """Check the status of an async job."""
    if job_id not in JOB_STORE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found"
        )
    
    job_info = JOB_STORE[job_id]
    return JobStatus(
        job_id=job_id,
        status=job_info["status"],
        result=job_info.get("result")
    )

@router.get("/test-prescription/", response_model=PrescriptionResponse, tags=["Testing"])
async def test_prescription(api_key: str = Depends(verify_api_key)):
    """Test with a sample prescription."""
    sample_text = """
    Dr. J. Smith
    General Hospital
    Date: 12 Feb 2025
    
    Patient: John Doe
    
    Rx:
    1. Paracetamol 500 mg tablet
       Take 1 tablet every 8 hours for 5 days
    2. Amoxicillin 250 mg capsule
       Take 1 capsule three times daily after meals
    
    Notes: Drink plenty of fluids. Return if symptoms persist after 7 days.
    """

    # AI Correction (disabled for test endpoint)
    corrected_text = sample_text
    
    # Extract structured medication data
    medications = extract_structured_medications(corrected_text)
    
    # Parse data
    parsed_data = parse_prescription_text(corrected_text)
    
    # Add medications to the response
    parsed_data.medications = medications
    
    return PrescriptionResponse(
        success=True,
        raw_text=sample_text,
        corrected_text=corrected_text,
        parsed_data=parsed_data,
        medications=medications
    )

@router.get("/health", tags=["Info"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}