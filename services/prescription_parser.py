import re
from typing import List
from models.schemas import PrescriptionData, Medication
from services.text_processor import nlp, correct_medication_name


def extract_dosage(text: str, medication_name: str) -> str:
    """Extract dosage information for a given medication."""
    # Look for the medication name and try to find dosage after it
    pattern = fr"{re.escape(medication_name)}\s+(\d+(?:\.\d+)?)\s*(mg|ml|g|mcg|tablet|capsule|pill)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return ""


def extract_frequency(text: str) -> List[str]:
    """Extract medication frequency instructions."""
    frequency_patterns = [
        r"(\d+)\s*times?\s*(?:a|per)\s*day",
        r"every\s*(\d+)\s*hours?",
        r"once\s*daily",
        r"twice\s*daily",
        r"(morning|evening|night)",
        r"before\s*meals",
        r"after\s*meals",
        r"with\s*meals",
        r"TID",  # Three times a day
        r"BID",  # Twice a day
        r"QID",  # Four times a day
        r"QD",   # Once daily
        r"Take\s*(?:once|twice|three|four)\s*(?:times)?\s*(?:a|per|each)?\s*day",
    ]
    
    frequencies = []
    for pattern in frequency_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            frequencies.append(match.group(0))
            
    return frequencies


def extract_patient_name(text: str) -> str:
    """Extract patient name from prescription text."""
    # Look specifically for the pattern in your example
    patient_pattern = r"\(Patient's name\)\s*([\w\s\.,]+?)(?:,|$)"
    patient_match = re.search(patient_pattern, text, re.IGNORECASE)
    
    if patient_match:
        # Extract just the name part without military info if possible
        name_parts = patient_match.group(1).split(',')
        return name_parts[0].strip()
    
    # Fall back to other patterns if the specific one doesn't match
    fallback_patterns = [
        r"Patient\s*(?:Name)?\s*:\s*([\w\s]+?)[,\n\.]",
        r"Name\s*:\s*([\w\s]+?)[,\n\.]",
        r"FOR\s*(?:\(.*\))?\s*([\w\s,]+?)[,\n\.]",
        r"(?:Pt|Patient):\s*([\w\s]+?)[,\n\.]",
        r"(?:Prescribed for|For):\s*([\w\s]+?)[,\n\.]"
    ]
    
    for pattern in fallback_patterns:
        patient_match = re.search(pattern, text, re.IGNORECASE)
        if patient_match:
            return patient_match.group(1).strip()
    
    return ""


def extract_medications(text: str, doc) -> List[Medication]:
    """Extract medications and their details from prescription text."""
    medications = []
    
    # Method 1: Look for "Corrected medication name" pattern
    corrected_med_matches = re.finditer(r"(?:Corrected medication name\))\s*([\w\s]+)(?:\s+(\d+(?:\.\d+)?)\s*(mg|ml|g|mcg|tablet|capsule|pill))?", text, re.IGNORECASE)
    
    for match in corrected_med_matches:
        med_name = match.group(1).strip()
        
        # Check if dosage information is available
        dosage = ""
        if match.group(2) and match.group(3):
            dosage = f"{match.group(2)} {match.group(3)}"
        else:
            # Look for dosage information elsewhere in the text for this medication
            dosage = extract_dosage(text, med_name)
        
        # Look for frequency information near this medication
        med_index = match.start()
        next_section = text[med_index:med_index + 200]  # Look further ahead
        
        frequencies = extract_frequency(next_section)
        frequency = ", ".join(frequencies) if frequencies else None
        
        medications.append(Medication(
            name=med_name,
            dosage=dosage,
            frequency=frequency
        ))
    
    # Method 2: Extract using numbered list format if Method 1 finds nothing
    if not medications:
        med_matches = re.findall(r"(?:\d+\.?\s*)([\w\s]+)\s+(\d+(?:\.\d+)?)\s*(mg|ml|g|mcg|tablet|capsule|pill)", text)
        
        for match in med_matches:
            med_name = match[0].strip()
            corrected_name = correct_medication_name(med_name)
            dosage = f"{match[1]} {match[2]}"
            
            # Try to find frequency for this medication
            med_index = text.find(med_name)
            if med_index != -1:
                # Look for frequency in the next 100 characters after medication
                next_section = text[med_index:med_index + 100]
                frequencies = extract_frequency(next_section)
                frequency = ", ".join(frequencies) if frequencies else None
                
                medications.append(Medication(
                    name=corrected_name,
                    dosage=dosage,
                    frequency=frequency
                ))
    
    # Method 3: Use SpaCy NER for medications not found by regex
    if not medications:
        for ent in doc.ents:
            if ent.label_ == "CHEMICAL":
                med_name = ent.text
                corrected_name = correct_medication_name(med_name)
                dosage = extract_dosage(text, med_name)
                
                if dosage:  # Only add if we found a dosage
                    # Check if we've already added this medication
                    if not any(med.name == corrected_name for med in medications):
                        # Look for frequency
                        med_index = text.find(med_name)
                        if med_index != -1:
                            next_section = text[med_index:med_index + 100]
                            frequencies = extract_frequency(next_section)
                            frequency = ", ".join(frequencies) if frequencies else None
                            
                            medications.append(Medication(
                                name=corrected_name,
                                dosage=dosage,
                                frequency=frequency
                            ))
    
    return medications


def parse_prescription_text(text: str) -> PrescriptionData:
    """Parse prescription details without adding explanatory text at newlines."""
    # Initialize empty prescription data object
    prescription_data = PrescriptionData()
    
    # Clean input text - normalize newlines and whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Process with SpaCy for NER
    doc = nlp(text)
    
    # Extract data fields without adding explanatory text
    prescription_data.patient = extract_patient_name(text)
    prescription_data.medications = extract_medications(text, doc)
    
    # Extract doctor's name
    doctor_patterns = [
        r"Dr\.?\s*([\w\s]+?)[,\n\.]",
        r"Doctor\s*:\s*([\w\s]+?)[,\n\.]",
        r"Physician\s*:\s*([\w\s]+?)[,\n\.]",
        r"(?:SIGNATURE|SIGNED BY)\s*([\w\s\.]+)(?:\n|$)",
        r"(?:Bottle|Dr\.?)\s*([\w\s\.]+)(?:\n|$)"
    ]
    
    for pattern in doctor_patterns:
        doctor_match = re.search(pattern, text, re.IGNORECASE)
        if doctor_match:
            prescription_data.doctor = doctor_match.group(1).strip()
            break
    
    # Extract date
    date_patterns = [
        r"DATE\s*:\s*(\d{1,2}[\/\-\s]*[A-Za-z]*[\/\-\s]*\d{2,4})",
        r"DATE\s+(\d{1,2}[\/\-\s]*[A-Za-z]*[\/\-\s]*\d{2,4})",
        r"(\d{1,2}[\/\-\s]*[A-Za-z]*[\/\-\s]*\d{2,4})"
    ]
    
    for pattern in date_patterns:
        date_match = re.search(pattern, text)
        if date_match:
            prescription_data.date = date_match.group(1).strip()
            break
    
    # Extract hospital/clinic
    hospital_match = re.search(r"([\w\s]+\s*Hospital|[\w\s]+\s*Clinic|[\w\s]+\s*Medical\s*Center|MEDICAL FACILITY)", text, re.IGNORECASE)
    if hospital_match:
        prescription_data.hospital = hospital_match.group(1).strip()
    
    # Extract notes/additional instructions
    notes_match = re.search(r"(?:Notes|Instructions|Directions|Signa):\s*([\w\s.,;]+)(?:\n|$)", text, re.IGNORECASE)
    if notes_match:
        prescription_data.notes = notes_match.group(1).strip()
    
    return prescription_data