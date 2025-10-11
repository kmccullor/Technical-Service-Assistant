#!/usr/bin/env python3
"""
Privacy Classification Test Script

This script demonstrates and tests the confidentiality detection functionality
by processing sample documents and showing the classification results.
"""

import sys
import os

# Add app path for imports
sys.path.append('/app')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pdf_processor.pdf_utils import detect_confidentiality


def test_privacy_classification():
    """Test privacy classification with various document examples."""

    print("=" * 60)
    print("PRIVACY CLASSIFICATION TEST")
    print("=" * 60)

    # Test cases with expected results
    test_cases = [
        {
            "name": "Public Annual Report",
            "text": """
            Annual Report 2023

            This public document summarizes our company's financial performance
            for the fiscal year 2023. The information contained herein is
            available to all shareholders and the general public.

            Our revenue increased by 15% compared to the previous year.
            """,
            "expected": "public"
        },
        {
            "name": "Confidential Business Plan",
            "text": """
            CONFIDENTIAL BUSINESS PLAN

            This document contains proprietary information about our upcoming
            product launch strategy. The contents are strictly confidential
            and should not be shared outside the executive team.
            """,
            "expected": "private"
        },
        {
            "name": "Internal Memo",
            "text": """
            Internal Memo - FOR INTERNAL USE ONLY

            Subject: Restructuring Plans

            This memo outlines our plans for the upcoming organizational
            restructuring. Please do not distribute this information
            outside the company.
            """,
            "expected": "private"
        },
        {
            "name": "Legal Document",
            "text": """
            ATTORNEY-CLIENT PRIVILEGED COMMUNICATION

            Re: Merger and Acquisition Analysis

            This communication contains legal advice regarding the proposed
            merger with ABC Corporation. This document is protected by
            attorney-client privilege.
            """,
            "expected": "private"
        },
        {
            "name": "Trade Secret Documentation",
            "text": """
            Manufacturing Process Documentation

            This document contains trade secret information about our
            proprietary manufacturing process. Unauthorized disclosure
            would cause significant competitive harm.
            """,
            "expected": "private"
        },
        {
            "name": "Employee Handbook (Public Section)",
            "text": """
            Employee Handbook - Chapter 1: Welcome

            Welcome to our company! This section of the handbook provides
            general information about our company culture and values.

            Our mission is to provide excellent service to our customers
            while maintaining the highest ethical standards.
            """,
            "expected": "public"
        },
        {
            "name": "HR Personnel File",
            "text": """
            Personnel File - Contains PII

            Employee: John Doe
            Social Security Number: ***-**-****

            This file contains personally identifiable information
            and sensitive personnel records. Access is restricted
            to authorized HR personnel only.
            """,
            "expected": "private"
        },
        {
            "name": "Research Paper Draft",
            "text": """
            Research Paper: Analysis of Market Trends

            This paper analyzes current market trends in the technology sector.
            The research methodology and findings will be published in an
            upcoming academic journal.
            """,
            "expected": "public"
        },
        {
            "name": "Board Meeting Minutes",
            "text": """
            Board of Directors Meeting Minutes
            Classification: Private

            These minutes contain sensitive discussions about executive
            compensation and strategic planning. Distribution is limited
            to board members only.
            """,
            "expected": "private"
        },
        {
            "name": "Press Release",
            "text": """
            FOR IMMEDIATE RELEASE

            Company Announces New Product Launch

            [City, Date] - We are excited to announce the launch of our
            new product line. This press release may be freely distributed
            to media outlets and the public.
            """,
            "expected": "public"
        }
    ]

    # Run tests and collect results
    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print("-" * 40)

        # Show sample of the text (first 100 characters)
        trimmed_text = test_case['text'].strip()
        sample_text = trimmed_text[:100] + "..." if len(trimmed_text) > 100 else trimmed_text
        print(f"Sample: {sample_text}")

        # Classify the document
        result = detect_confidentiality(test_case['text'])
        expected = test_case['expected']

        # Check result
        if result == expected:
            print(f"✅ PASS: Classified as '{result}' (expected '{expected}')")
            passed += 1
        else:
            print(f"❌ FAIL: Classified as '{result}' (expected '{expected}')")
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {len(test_cases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(test_cases)*100):.1f}%")

    if failed == 0:
        print("\n🎉 All tests passed! Privacy classification is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Review the classification logic.")

    return passed == len(test_cases)


def test_keyword_detection():
    """Test individual keyword detection."""
    print("\n" + "=" * 60)
    print("KEYWORD DETECTION TEST")
    print("=" * 60)

    # Test specific keywords
    confidential_keywords = [
        'confidential', 'private', 'restricted', 'classified',
        'proprietary', 'internal', 'sensitive', 'privileged',
        'attorney-client', 'trade secret', 'do not distribute',
        'internal use only', 'not for distribution', 'personally identifiable',
        'pii', 'social security number', 'top secret'
    ]

    for keyword in confidential_keywords:
        test_text = f"This document contains {keyword} information."
        result = detect_confidentiality(test_text)

        if result == 'private':
            print(f"✅ '{keyword}' -> {result}")
        else:
            print(f"❌ '{keyword}' -> {result} (expected 'private')")


def test_edge_cases():
    """Test edge cases and potential issues."""
    print("\n" + "=" * 60)
    print("EDGE CASE TESTS")
    print("=" * 60)

    edge_cases = [
        ("Empty string", "", "public"),
        ("None value", None, "public"),
        ("Whitespace only", "   \n\t   ", "public"),
        ("Very short text", "Hi", "public"),
        ("Mixed case", "This is ConFiDeNtIaL information", "private"),
        ("Multiple keywords", "This CONFIDENTIAL document contains PROPRIETARY data", "private"),
        ("Keyword in context", "We discussed confidentiality policies in the meeting", "private"),
        ("False positive context", "The article about confidentiality was published publicly", "private"),
    ]

    for name, text, expected in edge_cases:
        result = detect_confidentiality(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} {name}: '{text}' -> {result} (expected {expected})")


def interactive_test():
    """Interactive test mode for custom input."""
    print("\n" + "=" * 60)
    print("INTERACTIVE TEST MODE")
    print("=" * 60)
    print("Enter document text to test privacy classification.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            print("-" * 40)
            text = input("Enter document text: ")

            if text.lower().strip() in ['quit', 'exit', 'q']:
                break

            result = detect_confidentiality(text)
            print(f"Classification: {result.upper()}")

            if result == 'private':
                print("🔒 This document would be marked as PRIVATE")
            else:
                print("🌐 This document would be marked as PUBLIC")

        except KeyboardInterrupt:
            print("\nExiting interactive mode...")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main function to run all tests."""
    print("Privacy Classification Test Suite")
    print("Testing confidentiality detection functionality...\n")

    try:
        # Run automated tests
        success = test_privacy_classification()
        test_keyword_detection()
        test_edge_cases()

        # Ask if user wants interactive mode
        if input("\nRun interactive test mode? (y/n): ").lower().startswith('y'):
            interactive_test()

        print("\nTesting complete!")
        return success

    except Exception as e:
        print(f"Error during testing: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
