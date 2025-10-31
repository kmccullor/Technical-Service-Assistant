#!/usr/bin/env python3
"""
Test script for AI-powered document categorization functionality.
"""

import json
import os
import sys

sys.path.append("/home/kmccullor/Projects/Technical-Service-Assistant")

# Set environment variables to avoid app directory issues
os.environ["UPLOADS_DIR"] = "/home/kmccullor/Projects/Technical-Service-Assistant/uploads"
os.environ["ARCHIVE_DIR"] = "/home/kmccullor/Projects/Technical-Service-Assistant/uploads/archive"

# Create logs directory if it doesn't exist
logs_dir = "/home/kmccullor/Projects/Technical-Service-Assistant/logs"
os.makedirs(logs_dir, exist_ok=True)

from pdf_processor.pdf_utils import classify_document_with_ai, get_db_connection, insert_document_with_categorization


def test_ai_classification():
    """Test AI classification with sample document text."""

    # Sample RNI user guide text
    sample_text = """
    RNI 4.16 Security Guide

    This document provides comprehensive security configuration instructions for RNI version 4.16.

    Table of Contents:
    1. Introduction
    2. Security Architecture Overview
    3. Authentication Configuration
    4. Authorization Policies
    5. Encryption Settings
    6. Network Security
    7. Audit Logging
    8. Troubleshooting

    Chapter 1: Introduction

    The RNI (Resource Network Infrastructure) security module provides enterprise-grade
    security features for managing network resources and access control. This guide
    covers installation, configuration, and maintenance of security features in RNI 4.16.

    Key Features:
    - Multi-factor authentication
    - Role-based access control
    - End-to-end encryption
    - Comprehensive audit logging
    - Real-time threat detection
    """

    print("Testing AI Classification System")
    print("=" * 50)

    try:
        # Test AI classification
        print("Running AI classification...")
        classification = classify_document_with_ai(sample_text, "RNI_4.16_Security_Guide.pdf")

        print(f"Classification Results:")
        print(f"  Document Type: {classification.get('document_type', 'unknown')}")
        print(f"  Product Name: {classification.get('product_name', 'unknown')}")
        print(f"  Product Version: {classification.get('product_version', 'unknown')}")
        print(f"  Document Category: {classification.get('document_category', 'unknown')}")
        print(f"  Confidence: {classification.get('confidence', 0.0):.2f}")
        print(f"  AI Metadata: {json.dumps(classification.get('metadata', {}), indent=2)}")

        # Test database insertion
        print("\nTesting database insertion...")
        conn = get_db_connection()
        document_id = insert_document_with_categorization(conn, "test_ai_classification.pdf", "public", classification)
        print(f"Created document record with ID: {document_id}")

        # Verify the record was created correctly
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT file_name, document_type, product_name, product_version,
                       classification_confidence, ai_metadata
                FROM pdf_documents WHERE id = %s;
            """,
                (document_id,),
            )
            result = cur.fetchone()

            if result:
                print("\nDatabase Verification:")
                print(f"  File Name: {result[0]}")
                print(f"  Document Type: {result[1]}")
                print(f"  Product Name: {result[2]}")
                print(f"  Product Version: {result[3]}")
                print(f"  Confidence: {result[4]:.2f}")
                print(f"  AI Metadata: {json.dumps(result[5], indent=2)}")

            # Clean up test record
            cur.execute("DELETE FROM pdf_documents WHERE id = %s;", (document_id,))
            conn.commit()
            print("\nTest record cleaned up successfully")

        conn.close()
        print("\nAI Categorization Test: PASSED")
        return True

    except Exception as e:
        print(f"AI Categorization Test: FAILED - {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_ai_classification()
    sys.exit(0 if success else 1)
