# Enhanced medication database with categories
MEDICINE_DB = {
    "painkillers": ["Paracetamol", "Ibuprofen", "Aspirin", "Tramadol", "Codeine", "Diclofenac", "Naproxen"],
    "antibiotics": ["Amoxicillin", "Azithromycin", "Ciprofloxacin", "Doxycycline", "Metronidazole"],
    "antidiabetics": ["Metformin", "Glimepiride", "Sitagliptin", "Insulin", "Empagliflozin"],
    "statins": ["Atorvastatin", "Simvastatin", "Rosuvastatin", "Pravastatin"],
    "antihypertensives": ["Amlodipine", "Lisinopril", "Losartan", "Hydrochlorothiazide", "Enalapril"],
    "antihistamines": ["Cetirizine", "Loratadine", "Fexofenadine", "Chlorpheniramine"],
    "corticosteroids": ["Prednisolone", "Dexamethasone", "Hydrocortisone", "Budesonide"],
}

# Flattened medicine list for fuzzy matching
ALL_MEDICINES = [med for category in MEDICINE_DB.values() for med in category]