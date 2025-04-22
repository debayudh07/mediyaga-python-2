from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel


class Medication(BaseModel):
    """Medication information extracted from prescription."""
    name: str
    dosage: str
    frequency: Optional[str] = None
    duration: Optional[str] = None


class PrescriptionData(BaseModel):
    """Structured prescription data."""
    patient: Optional[str] = None
    date: Optional[str] = None
    medications: List[Medication] = []
    doctor: Optional[str] = None
    hospital: Optional[str] = None
    notes: Optional[str] = None


class PrescriptionResponse(BaseModel):
    """API response model for prescription analysis."""
    success: bool
    raw_text: Optional[str] = None
    corrected_text: Optional[str] = None
    parsed_data: Optional[PrescriptionData] = None
    job_id: Optional[str] = None
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None


class JobStatus(BaseModel):
    """Status of an asynchronous job."""
    job_id: str
    status: str
    result: Optional[PrescriptionResponse] = None