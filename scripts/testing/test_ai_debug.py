#!/usr/bin/env python3
"""
Debug script to test AI categorization functionality
"""
import sys
import os
sys.path.append('/home/kmccullor/Projects/Technical-Service-Assistant')
sys.path.append('/home/kmccullor/Projects/Technical-Service-Assistant/pdf_processor')

from pdf_processor.pdf_utils import classify_document_with_ai

# Test with sample text
sample_text = """
RNI User Guide Version 4.16

This document provides comprehensive instructions for using the RNI platform.
The RNI system is designed for utility management and grid operations.

Table of Contents:
1. Installation
2. Configuration
3. User Interface
4. Advanced Features
5. Troubleshooting
"""

print("Testing AI classification...")
result = classify_document_with_ai(sample_text, "RNI_User_Guide_4.16.pdf")
print(f"Classification result: {result}")