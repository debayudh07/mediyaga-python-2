import time
import spacy
import re
import json
from groq import Groq
from functools import lru_cache
from fuzzywuzzy import process
from config import settings, logger
from db.medicine_db import ALL_MEDICINES

# Define comprehensive medical abbreviations dictionary
MEDICAL_ABBREVIATIONS = {
    "QD": "once daily",
    "BID": "twice daily",
    "TID": "three times daily",
    "QID": "four times daily",
    "PRN": "as needed",
    "PO": "by mouth",
    "SC": "subcutaneous",
    "SQ": "subcutaneous",
    "IM": "intramuscular",
    "IV": "intravenous",
    "AC": "before meals",
    "PC": "after meals",
    "HS": "at bedtime",
    "OD": "right eye",
    "OS": "left eye",
    "OU": "both eyes",
    "AD": "right ear",
    "AS": "left ear",
    "AU": "both ears",
}

# Load medical NLP model with improved error handling
try:
    # Specify full pipeline needs for medical entity recognition
    nlp = spacy.load("en_core_sci_sm", disable=["tok2vec", "tagger", "parser"])
    # Add specific entity ruler patterns for common medications
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    medication_patterns = [
        {"label": "MEDICATION", "pattern": med_name} 
        for med_name in ALL_MEDICINES[:1000]  # Limit to most common for performance
    ]
    ruler.add_patterns(medication_patterns)
    logger.info("Successfully loaded enhanced SpaCy NLP model")
except Exception as e:
    logger.warning(f"Failed to load SpaCy model: {e}. Using fallback model.")
    nlp = spacy.load("en_core_web_sm")


def correct_text_with_groq(text: str) -> str:
    """Use Groq AI model to correct OCR errors with error handling and retries."""
    if not settings.enable_ai_correction:
        logger.info("AI correction disabled")
        return text

    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            # Configure Groq client
            client = Groq(api_key=settings.groq_api_key)
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": (
                        "You are an AI assistant that corrects OCR-extracted text from medical prescriptions. "
                        "Maintain the original format but fix spelling errors, especially in medication names. "
                        "Pay special attention to medical terminology, dosages, and administration instructions. "
                        "Only output the corrected text, nothing else."
                    )},
                    {"role": "user", "content": f"Correct the following OCR text from a medical prescription:\n{text}"}
                ],
                temperature=0.6,  # Lower temperature for more predictable corrections
                max_tokens=1024
            )
            corrected_text = response.choices[0].message.content.strip()
            logger.info("Successfully corrected text with AI")
            return corrected_text
            
        except Exception as e:
            logger.warning(f"Groq API Error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Failed all {max_retries} attempts to correct text with Groq")
                return text  # Return original text if all retries fail


def expand_medical_abbreviations(text):
    """Expand common medical abbreviations in text."""
    expanded = text
    for abbr, meaning in MEDICAL_ABBREVIATIONS.items():
        # Match whole words only with word boundaries
        pattern = re.compile(r'\b' + re.escape(abbr) + r'\b', re.IGNORECASE)
        expanded = pattern.sub(f"{abbr} ({meaning})", expanded)
    return expanded


def extract_medications_with_llm(text: str) -> list:
    """Use LLM to extract structured medication information from complex prescriptions."""
    max_retries = 2
    retry_delay = 1
    
    # Pre-process the text to highlight potential medication terms
    doc = nlp(text)
    highlighted_text = text
    for ent in doc.ents:
        if ent.label_ in ["CHEMICAL", "ORG", "PRODUCT", "MEDICATION"]:
            highlighted_text = highlighted_text.replace(ent.text, f"POTENTIAL_MEDICATION: {ent.text}")
    
    for attempt in range(max_retries):
        try:
            # Configure Groq client
            client = Groq(api_key=settings.groq_api_key)
            
            # Enhanced prompt with medical terminology examples
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": (
                        "You are a medical pharmacist specialized in prescription analysis. "
                        "Extract all medications from the prescription with their complete details. "
                        "Be especially careful to identify common medication spelling variants and abbreviations. "
                        "For each medication, identify: "
                        "1. Exact medication name (use standard names from medical databases) "
                        "2. Dosage (amount and unit) "
                        "3. Route (oral, topical, etc.) if specified "
                        "4. Administration instructions (frequency, timing, relation to food) "
                        "5. Duration if specified "
                        "\nCommon abbreviations: QD (once daily), BID (twice daily), TID (three times daily), "
                        "QID (four times daily), PRN (as needed), PO (by mouth), SC (subcutaneous), "
                        "IM (intramuscular), IV (intravenous)"
                        "\nRespond ONLY with a JSON object with a 'medications' array containing medication objects."
                    )},
                    {"role": "user", "content": f"Extract medications from this prescription:\n{highlighted_text}"}
                ],
                temperature=0.2,  # Low temperature for more deterministic extraction
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content.strip()
            logger.info("Successfully extracted medications with LLM")
            
            try:
                # Parse the JSON response
                parsed_response = json.loads(result)
                medications = parsed_response.get("medications", [])

                # Process each medication to correct names and expand abbreviations
                for med in medications:
                    if "name" in med:
                        med["name"] = correct_medication_name(med["name"])
                    if "instructions" in med:
                        med["instructions"] = expand_medical_abbreviations(med["instructions"])
                
                return medications
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.debug(f"Raw LLM response: {result}")
                return []
            
        except Exception as e:
            logger.warning(f"LLM Extraction Error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Failed all {max_retries} attempts to extract medications with LLM")
                return []  # Return empty list if all retries fail


@lru_cache(maxsize=100)
def correct_medication_name(med_name: str) -> str:
    """Use enhanced fuzzy matching to correct medication names with caching."""
    # Clean input - remove common prefixes like "Tab", "Cap", etc.
    cleaned_name = re.sub(r'^(Tab|Cap|Inj|Susp|Sol|Syp|Oint|Cream)\s+', '', med_name, flags=re.IGNORECASE)
    cleaned_name = cleaned_name.strip()
    
    # If too short, likely not a medication name
    if len(cleaned_name) < 3:
        return med_name
        
    # Try direct match first (faster)
    if cleaned_name.lower() in [m.lower() for m in ALL_MEDICINES]:
        for m in ALL_MEDICINES:
            if m.lower() == cleaned_name.lower():
                return m
    
    # Fall back to fuzzy matching
    matches = process.extractBests(cleaned_name, ALL_MEDICINES, 
                                   score_cutoff=settings.fuzzy_match_threshold, 
                                   limit=3)
    
    if not matches:
        # If no good match, return original
        return med_name
        
    # Log alternate possibilities for debugging
    if len(matches) > 1:
        logger.debug(f"Multiple medication matches for '{med_name}': {matches}")
    
    # Return best match
    return matches[0][0]


def extract_structured_medications(text: str) -> list:
    """Extract structured medication information from prescription text using rule-based approach."""
    
    # Initialize medications list for rule-based extraction
    medications = []
    
    # Process the text with NLP model
    doc = nlp(text)
    
    # Common dosage patterns
    dosage_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|tablet|capsule|tablespoon|teaspoon)', re.IGNORECASE)
    
    # Enhanced frequency patterns including all medical abbreviations
    frequency_keywords = ['once', 'twice', 'three times', 'four times', 
                         'every\\s*\\d+\\s*hours?', 'daily', 'weekly', 'monthly',
                         'morning', 'evening', 'night', 'before meal', 'after meal']
    abbreviation_keywords = list(MEDICAL_ABBREVIATIONS.keys())
    combined_keywords = frequency_keywords + ['\\b' + re.escape(abbr) + '\\b' for abbr in abbreviation_keywords]
    
    frequency_pattern = re.compile(
        '(' + '|'.join(combined_keywords) + ')',
        re.IGNORECASE
    )
    
    # Route patterns
    route_pattern = re.compile(
        r'\b(oral|topical|subcutaneous|intramuscular|intravenous|sublingual|buccal|rectal|vaginal|inhaled|nasal)\b',
        re.IGNORECASE
    )
    
    # Split text into lines to process prescription items
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Look for numbered items or bullet points which often indicate medications
        # Also look for lines containing dosage information or medical abbreviations
        if (re.match(r'^\d+[\.\)]|•', line) or 
            any(keyword in line.lower() for keyword in ['tab', 'capsule', 'mg', 'ml']) or 
            any(re.search(r'\b' + re.escape(abbr) + r'\b', line, re.IGNORECASE) for abbr in MEDICAL_ABBREVIATIONS.keys())):
            
            # Extract medication name
            # First, try to find the dosage pattern to split the line
            dosage_match = dosage_pattern.search(line)
            if dosage_match:
                # The medication name is likely before the dosage
                med_name = line[:dosage_match.start()].strip()
                med_name = re.sub(r'^\d+[\.\)]|•', '', med_name).strip()  # Remove numbering
                
                # Use fuzzy matching to correct medication name
                med_name = correct_medication_name(med_name)
                
                # Extract dosage
                dosage = dosage_match.group(0)
                
                # Extract frequency/instructions
                instructions = ""
                freq_match = frequency_pattern.search(line)
                if freq_match:
                    instructions = line[freq_match.start():].strip()
                elif i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r'^\d+[\.\)]|•', lines[i + 1]):
                    # Check if next line has instructions
                    instructions = lines[i + 1].strip()
                
                # Extract route if present
                route = ""
                route_match = route_pattern.search(line)
                if route_match:
                    route = route_match.group(0)
                
                # Look for and expand medical abbreviations in instructions
                instructions = expand_medical_abbreviations(instructions)
                
                # Create medication object
                medication = {
                    "name": med_name,
                    "dosage": dosage,
                    "route": route,
                    "instructions": instructions
                }
                
                medications.append(medication)
    
    # If no structured medications found, try fallback method using NER
    if not medications:
        for entity in doc.ents:
            if entity.label_ in ["CHEMICAL", "ORG", "PRODUCT", "MEDICATION"]:
                # Try to find dosage near this entity
                context = text[max(0, entity.start_char-50):min(len(text), entity.end_char+50)]
                dosage_match = dosage_pattern.search(context)
                dosage = dosage_match.group(0) if dosage_match else ""
                
                # Try to find route near this entity
                route_match = route_pattern.search(context)
                route = route_match.group(0) if route_match else ""
                
                # Look for frequency/instructions
                instructions = ""
                freq_match = frequency_pattern.search(context)
                if freq_match:
                    instruction_start = freq_match.start()
                    instruction_end = min(instruction_start + 100, len(context))
                    instructions = context[instruction_start:instruction_end].strip()
                    # Truncate at the next sentence or punctuation
                    truncate_match = re.search(r'[.;]', instructions)
                    if truncate_match:
                        instructions = instructions[:truncate_match.end()]
                
                # Expand any abbreviations in instructions
                instructions = expand_medical_abbreviations(instructions)
                
                # Create medication object with limited info
                medication = {
                    "name": correct_medication_name(entity.text),
                    "dosage": dosage,
                    "route": route,
                    "instructions": instructions
                }
                
                medications.append(medication)
    
    return medications


def extract_all_medications(text: str) -> list:
    """Comprehensive medication extraction using both LLM and rule-based methods."""
    
    # First correct any OCR errors in the text
    corrected_text = correct_text_with_groq(text)
    
    # Try LLM extraction first (more accurate for complex prescriptions)
    llm_medications = extract_medications_with_llm(corrected_text)
    
    # Also do rule-based extraction as backup
    rule_based_medications = extract_structured_medications(corrected_text)
    
    # Merge results, prioritizing LLM but filling gaps with rule-based
    if llm_medications:
        # Use LLM results as base
        final_medications = llm_medications
        
        # Look for medications found by rules but not by LLM
        llm_med_names = {med["name"].lower() for med in llm_medications}
        for rule_med in rule_based_medications:
            if rule_med["name"].lower() not in llm_med_names:
                final_medications.append(rule_med)
                
        logger.info(f"Final medication extraction: {len(final_medications)} medications found")
        return final_medications
    else:
        # Fall back to rule-based if LLM failed
        logger.info(f"Using rule-based extraction only: {len(rule_based_medications)} medications found")
        return rule_based_medications


def compare_and_evaluate_extraction_methods(text: str) -> dict:
    """Compare LLM and rule-based extraction methods for debugging and improvement."""
    
    # First correct any OCR errors in the text
    corrected_text = correct_text_with_groq(text)
    
    # Get results from both methods
    llm_medications = extract_medications_with_llm(corrected_text)
    rule_based_medications = extract_structured_medications(corrected_text)
    
    # Final merged results
    final_medications = extract_all_medications(corrected_text)
    
    # Find unique medications from each method
    llm_med_names = {med["name"].lower() for med in llm_medications}
    rule_med_names = {med["name"].lower() for med in rule_based_medications}
    
    # Medications found only by LLM
    llm_only = [med for med in llm_medications if med["name"].lower() not in rule_med_names]
    
    # Medications found only by rule-based
    rule_only = [med for med in rule_based_medications if med["name"].lower() not in llm_med_names]
    
    # Medications found by both
    found_by_both = [med["name"] for med in llm_medications if med["name"].lower() in rule_med_names]
    
    return {
        "llm_count": len(llm_medications),
        "rule_based_count": len(rule_based_medications),
        "final_count": len(final_medications),
        "llm_only": llm_only,
        "rule_only": rule_only,
        "found_by_both": found_by_both,
        "final_medications": final_medications
    }