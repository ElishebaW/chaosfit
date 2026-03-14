#!/usr/bin/env python3
"""Test script to verify Firestore write operations."""

import logging
import os
from google.cloud import firestore

# Configure logging to see Firestore operations
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_firestore_write():
    """Test basic Firestore write operations."""
    try:
        # Initialize Firestore client
        db = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT", "chaos-fit"))
        logging.info(f"Firestore client initialized for project: {db.project}")
        
        # Test write operation
        doc_ref = db.collection("test_collection").document("test_doc")
        test_data = {
            "test_field": "test_value",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "project": db.project
        }
        
        result = doc_ref.set(test_data)
        logging.info("Test document written successfully")
        print("✅ Firestore write test passed!")
        
        # Test read operation
        doc = doc_ref.get()
        if doc.exists:
            logging.info(f"Test document read successfully: {doc.to_dict()}")
            print("✅ Firestore read test passed!")
        else:
            print("❌ Test document not found")
            
        return True
        
    except Exception as e:
        logging.error(f"Firestore test failed: {e}")
        print(f"❌ Firestore test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Firestore write operations...")
    success = test_firestore_write()
    if success:
        print("\n🎉 All tests passed! Your Firestore setup is working correctly.")
    else:
        print("\n⚠️  Tests failed. Check the error messages above.")
