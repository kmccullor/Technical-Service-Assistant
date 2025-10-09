#!/usr/bin/env python3
"""
Simple test for AI categorization system without Docker
"""
import sys
import os

# Add the project root to Python path
project_root = '/home/kmccullor/Projects/Technical-Service-Assistant'
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'pdf_processor'))

# Test imports
try:
    from pdf_processor.pdf_utils import classify_document_with_ai, detect_confidentiality
    print("✅ Successfully imported AI categorization functions")
except ImportError as e:
    print(f"❌ Failed to import AI functions: {e}")
    exit(1)

# Test AI categorization
sample_text = """
RNI User Guide Version 4.16

This document provides comprehensive instructions for using the RNI platform.
The RNI system is designed for utility management and grid operations.

Table of Contents:
1. Installation and Setup
2. Configuration Management
3. User Interface Overview
4. Advanced Features
5. Troubleshooting Guide

© 2024 Sensus - Confidential and Proprietary
"""

print("\n📋 Testing AI Classification...")
try:
    result = classify_document_with_ai(sample_text, "RNI_User_Guide_4.16.pdf")
    print(f"✅ AI Classification successful!")
    print(f"   Document Type: {result.get('document_type', 'unknown')}")
    print(f"   Product Name: {result.get('product_name', 'unknown')}")
    print(f"   Product Version: {result.get('product_version', 'unknown')}")
    print(f"   Confidence: {result.get('confidence', 0)}")
except Exception as e:
    print(f"❌ AI Classification failed: {e}")

print("\n🔒 Testing Privacy Detection...")
try:
    privacy_level = detect_confidentiality(sample_text)
    print(f"✅ Privacy Detection successful: {privacy_level}")
except Exception as e:
    print(f"❌ Privacy Detection failed: {e}")

print("\n🎯 AI Categorization System Status: READY FOR TESTING")