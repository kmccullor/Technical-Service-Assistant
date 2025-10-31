#!/usr/bin/env python3
"""
Test script to validate security classification improvements.
"""

import sys

sys.path.append("/home/kmccullor/Projects/Technical-Service-Assistant")


# Mock the config and logging to avoid Docker dependency issues
class MockSettings:
    def __init__(self):
        self.chat_model = "llama2"
        self.embedding_model = "nomic-embed-text"
        self.temperature = 0.7


def get_settings():
    return MockSettings()


# Mock logging
class MockLogger:
    def info(self, msg):
        print(f"INFO: {msg}")

    def debug(self, msg):
        print(f"DEBUG: {msg}")

    def warning(self, msg):
        print(f"WARNING: {msg}")

    def error(self, msg):
        print(f"ERROR: {msg}")


def setup_logging(*args, **kwargs):
    return MockLogger()


# Patch imports
sys.modules["config"] = type("config", (), {"get_settings": get_settings})()
sys.modules["utils.logging_config"] = type("logging_config", (), {"setup_logging": setup_logging})()

# Now import our functions
from pdf_processor.pdf_utils_enhanced import apply_security_classification_overrides


def test_security_classification():
    """Test security document classification overrides."""
    print("🔒 Testing Security Document Classification Overrides")
    print("=" * 60)

    # Test case 1: Hardware Security Module Installation Guide
    test_cases = [
        {
            "filename": "RNI_4.16_Hardware_Security_Module_Installation_Guide.pdf",
            "text": "This guide provides instructions for installing and configuring hardware security modules (HSM) for cryptographic key management.",
            "expected_type": "security_guide",
        },
        {
            "filename": "Security_Configuration_Manual.pdf",
            "text": "Security configuration procedures for authentication mechanisms and access control.",
            "expected_type": "security_guide",
        },
        {
            "filename": "FlexNet_User_Guide.pdf",
            "text": "This user guide covers the basic functionality of FlexNet licensing system.",
            "expected_type": None,  # Should not trigger security override
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['filename']}")
        print(f"Content: {test_case['text'][:80]}...")

        result = apply_security_classification_overrides(test_case["text"], test_case["filename"])

        if test_case["expected_type"]:
            if result and result["document_type"] == test_case["expected_type"]:
                print(f"✅ PASS: Correctly classified as {result['document_type']}")
                print(f"   Product: {result['product_name']}, Confidence: {result['confidence']}")
            else:
                print(
                    f"❌ FAIL: Expected {test_case['expected_type']}, got {result['document_type'] if result else None}"
                )
        else:
            if result is None:
                print("✅ PASS: Correctly did not apply security override")
            else:
                print(f"❌ FAIL: Unexpectedly applied override: {result['document_type']}")

    print("\n" + "=" * 60)
    print("Security classification test completed!")


if __name__ == "__main__":
    test_security_classification()
