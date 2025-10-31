#!/usr/bin/env python3
"""
Simple test for security classification patterns.
"""

import re

# Security document classification patterns from our implementation
SECURITY_DOCUMENT_PATTERNS = {
    "filename_patterns": [
        r".*security.*guide.*",
        r".*security.*manual.*",
        r".*hsm.*installation.*",
        r".*hardware.*security.*module.*",
        r".*security.*configuration.*",
        r".*encryption.*guide.*",
        r".*certificate.*management.*",
        r".*cryptographic.*",
        r".*key.*management.*",
        r".*authentication.*guide.*",
        r".*firewall.*configuration.*",
        r".*vpn.*setup.*",
        r".*ssl.*tls.*configuration.*",
    ],
    "content_patterns": [
        r"hardware\s+security\s+module",
        r"hsm\s+installation",
        r"cryptographic\s+keys?",
        r"certificate\s+management",
        r"security\s+configuration",
        r"authentication\s+mechanisms?",
        r"encryption\s+standards?",
        r"security\s+protocols?",
        r"access\s+control\s+lists?",
        r"firewall\s+rules?",
        r"intrusion\s+detection",
        r"vulnerability\s+assessment",
        r"penetration\s+testing",
        r"security\s+audit",
        r"compliance\s+requirements?",
        r"security\s+best\s+practices?",
    ],
}


def test_security_patterns():
    """Test security pattern matching."""
    print("🔒 Testing Security Document Pattern Matching")
    print("=" * 60)

    test_cases = [
        {
            "filename": "RNI_4.16_Hardware_Security_Module_Installation_Guide.pdf",
            "text": "This guide provides instructions for installing and configuring hardware security modules (HSM).",
            "should_match": True,
            "reason": "Contains HSM installation keywords",
        },
        {
            "filename": "Security_Configuration_Manual.pdf",
            "text": "Security configuration procedures for authentication mechanisms and access control.",
            "should_match": True,
            "reason": "Security manual with relevant content",
        },
        {
            "filename": "FlexNet_User_Guide.pdf",
            "text": "This user guide covers the basic functionality of FlexNet licensing system.",
            "should_match": False,
            "reason": "Regular user guide without security content",
        },
        {
            "filename": "RNI_Installation_Guide.pdf",
            "text": "Standard installation procedures for RNI software deployment.",
            "should_match": False,
            "reason": "Installation guide but not security-related",
        },
        {
            "filename": "Certificate_Management_Guide.pdf",
            "text": "This document covers certificate management for SSL/TLS configuration.",
            "should_match": True,
            "reason": "Certificate management is security-related",
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['filename']}")
        print(f"Reason: {test_case['reason']}")

        filename_lower = test_case["filename"].lower()
        text_lower = test_case["text"].lower()

        # Check filename patterns
        filename_match = any(
            re.search(pattern, filename_lower) for pattern in SECURITY_DOCUMENT_PATTERNS["filename_patterns"]
        )

        # Check content patterns
        content_match = any(
            re.search(pattern, text_lower) for pattern in SECURITY_DOCUMENT_PATTERNS["content_patterns"]
        )

        matches = filename_match or content_match

        if matches == test_case["should_match"]:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"{status}: Expected match={test_case['should_match']}, Got match={matches}")
        if filename_match:
            print("   - Filename pattern matched")
        if content_match:
            print("   - Content pattern matched")

    print("\n" + "=" * 60)
    print("Security pattern matching test completed!")


if __name__ == "__main__":
    test_security_patterns()
