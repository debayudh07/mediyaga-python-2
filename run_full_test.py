#!/usr/bin/env python3
"""
Comprehensive test script for the Prescription Analyzer.
This script:
1. Creates a sample prescription image
2. Tests the local image processing (without API)
3. Tests the API if it's running
"""

import os
import sys
import json
import requests
import subprocess
import time
from pathlib import Path

# Add the current directory to the path so imports work correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the test functions
from create_sample_image import create_sample_prescription
from test_local_image import analyze_prescription_image

def check_api_running():
    """Check if the API is running."""
    try:
        response = requests.get("http://127.0.0.1:55800/docs")
        return response.status_code == 200
    except:
        return False

def run_api_test(image_path):
    """Test the API with the sample image."""
    # API endpoint
    url = "http://127.0.0.1:55800/analyze-prescription/"
    
    # API key from settings
    api_key = "dev_key"
    
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
            
            return True
        else:
            print(f"Error: API returned status code {response.status_code}")
            print(response.text)
            return False
    
    except Exception as e:
        print(f"Error calling API: {e}")
        return False

def main():
    """Run all the tests."""
    print("=" * 80)
    print("DocEase Prescription Analyzer Test Suite")
    print("=" * 80)
    
    # Step 1: Create a sample prescription image
    print("\n1. Creating sample prescription image...")
    image_path = create_sample_prescription()
    
    # Step 2: Test local image processing
    print("\n2. Testing local image processing...")
    local_result = analyze_prescription_image(image_path)
    if local_result:
        print("Local image processing successful!")
        print("\nExtracted Data:")
        print(json.dumps(local_result, indent=2))
    else:
        print("Local image processing failed!")
    
    # Step 3: Test the API if it's running
    print("\n3. Checking if API is running...")
    if check_api_running():
        print("API is running. Testing API...")
        api_result = run_api_test(image_path)
        if api_result:
            print("API test successful!")
        else:
            print("API test failed!")
    else:
        print("API is not running. Starting API...")
        try:
            # Start the API in a new process
            api_process = subprocess.Popen(
                ["python", "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for the API to start
            print("Waiting for API to start...")
            time.sleep(5)
            
            # Test the API
            if check_api_running():
                print("API started successfully. Testing API...")
                api_result = run_api_test(image_path)
                if api_result:
                    print("API test successful!")
                else:
                    print("API test failed!")
            else:
                print("Failed to start API.")
            
            # Keep the API running
            print("\nAPI is now running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        
        except KeyboardInterrupt:
            # Stop the API when user presses Ctrl+C
            print("\nStopping API...")
            api_process.terminate()
            print("API stopped.")
        
        except Exception as e:
            print(f"Error starting API: {e}")

if __name__ == "__main__":
    main() 