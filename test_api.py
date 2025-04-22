#!/usr/bin/env python3
"""
Test script for the Prescription Analysis API.
Sends a sample image to the API and displays the response.
"""

import os
import requests
import json
import sys
from pathlib import Path

def test_api(image_path):
    """Test the API with the sample image."""
    # API endpoint
    url = "http://127.0.0.1:55800/analyze-prescription/"
    
    # API key from settings
    api_key = "dev_key"  # This should match the one in config.py
    
    # Check if the image file exists
    if not os.path.exists(image_path):
        print(f"Error: File not found: {image_path}")
        return
    
    # Prepare the file for upload
    files = {
        "prescription": (os.path.basename(image_path), open(image_path, "rb"), "image/jpeg")
    }
    
    # Set headers with API key
    headers = {
        "X-API-Key": api_key
    }
    
    print(f"Sending image {image_path} to the API...")
    
    try:
        # Make the API request
        response = requests.post(url, files=files, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            result = response.json()
            
            # Print the results
            print("\nAPI Response:")
            print(json.dumps(result, indent=2))
            
            # Print medication details
            if result.get("success") and result.get("parsed_data", {}).get("medications"):
                print("\nExtracted Medications:")
                for i, med in enumerate(result["parsed_data"]["medications"], 1):
                    print(f"{i}. {med.get('name', 'Unknown')} - {med.get('dosage', 'N/A')}")
                    if med.get('frequency'):
                        print(f"   Frequency: {med['frequency']}")
                    print()
            
        else:
            print(f"Error: API returned status code {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == "__main__":
    # Check if image path is provided as command-line argument
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # Default to a sample image in the current directory
        # Try to find any image in the current directory
        image_files = list(Path(".").glob("*.jpg")) + list(Path(".").glob("*.png")) + list(Path(".").glob("*.jpeg"))
        
        if image_files:
            image_path = str(image_files[0])
            print(f"Using sample image: {image_path}")
        else:
            print("No image file found. Please provide a path to an image file.")
            print("Usage: python test_api.py /path/to/prescription_image.jpg")
            sys.exit(1)
    
    # Test the API
    test_api(image_path) 