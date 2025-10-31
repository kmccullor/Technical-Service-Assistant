"""
Enhanced PDF Processing Pipeline with Accuracy Improvements
Implements the highest-impact changes from the accuracy improvement plan
"""

import json
import os
import re
import sys
from typing import Any, Dict, Tuple

sys.path.append("/app")

# Enhanced classification patterns for better accuracy
ENHANCED_CLASSIFICATION_PATTERNS = {
    "security_installation_guide": {
        "filename_patterns": [
            r"hardware\s+security\s+module.*installation",
            r"hsm.*installation.*guide",
            r"security.*installation.*guide",
        ],
        "content_patterns": [r"hardware security module", r"hsm installation", r"security module setup"],
        "primary_type": "installation_guide",
        "specialization_tags": ["security", "hardware"],
        "confidence_boost": 0.15,
    },
    "system_security_guide": {
        "filename_patterns": [r"system\s+security.*user\s+guide", r"security.*user\s+guide", r"security\s+guide"],
        "content_patterns": [r"system security", r"security configuration", r"security administration"],
        "primary_type": "security_guide",
        "specialization_tags": ["system", "administration"],
        "confidence_boost": 0.2,
    },
    "base_station_security": {
        "filename_patterns": [r"base\s+station\s+security.*user\s+guide"],
        "content_patterns": [r"base station security", r"field device security"],
        "primary_type": "security_guide",
        "specialization_tags": ["base_station", "field_devices"],
        "confidence_boost": 0.2,
    },
}

# Product family synonyms for better query expansion
PRODUCT_SYNONYMS = {
    "rni": ["regional network interface", "rni system", "sensus rni"],
    "flexnet": ["flexnet system", "flex net", "flexnet communication", "flexnet esm"],
    "esm": ["enhanced supervisory message", "flexnet esm", "supervisory message"],
    "multispeak": ["multi speak", "multispeak protocol", "ms protocol"],
    "aclara": ["aclara technologies", "sensus"],
    "device_manager": ["device manager", "dm", "device management"],
}


def extract_enhanced_metadata(pdf_path: str, text: str) -> Dict[str, Any]:
    """
    Enhanced metadata extraction using multiple strategies
    """
    metadata = {
        "title": None,
        "version": None,
        "doc_number": None,
        "ga_date": None,
        "publisher": None,
        "copyright_year": None,
        "product_family": [],
        "service_lines": [],
        "audiences": [],
        "extraction_method": [],
    }

    # Strategy 1: PDF Structure Analysis
    try:
        pdf_metadata = extract_pdf_structure_metadata(pdf_path)
        metadata.update(pdf_metadata)
        if pdf_metadata:
            metadata["extraction_method"].append("pdf_structure")
    except Exception as e:
        print(f"PDF structure extraction failed: {e}")

    # Strategy 2: Enhanced Pattern Matching
    try:
        pattern_metadata = extract_enhanced_patterns(text, os.path.basename(pdf_path))
        for key, value in pattern_metadata.items():
            if value and not metadata.get(key):
                metadata[key] = value
        if pattern_metadata:
            metadata["extraction_method"].append("enhanced_patterns")
    except Exception as e:
        print(f"Enhanced pattern extraction failed: {e}")

    # Strategy 3: Content Structure Analysis
    try:
        structure_metadata = analyze_content_structure(text)
        for key, value in structure_metadata.items():
            if value and not metadata.get(key):
                metadata[key] = value
        if structure_metadata:
            metadata["extraction_method"].append("content_structure")
    except Exception as e:
        print(f"Content structure analysis failed: {e}")

    return metadata


def extract_pdf_structure_metadata(pdf_path: str) -> Dict[str, Any]:
    """Extract metadata from PDF structure and properties"""
    try:
        import fitz

        doc = fitz.open(pdf_path)

        # Get PDF metadata
        pdf_metadata = doc.metadata or {}

        metadata = {}

        # Extract title from PDF properties
        if pdf_metadata.get("title"):
            metadata["title"] = pdf_metadata["title"].strip()

        # Extract creator/publisher
        if pdf_metadata.get("creator"):
            metadata["publisher"] = pdf_metadata["creator"].strip()
        elif pdf_metadata.get("producer"):
            metadata["publisher"] = pdf_metadata["producer"].strip()

        # Analyze first page for title if not in metadata
        if not metadata.get("title") and len(doc) > 0:
            first_page = doc[0]
            blocks = first_page.get_text("dict")["blocks"]

            # Find text blocks and identify likely title
            text_blocks = []
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text_blocks.append(
                                {
                                    "text": span["text"].strip(),
                                    "size": span["size"],
                                    "flags": span["flags"],
                                    "bbox": span["bbox"],
                                }
                            )

            # Sort by font size and position to find title
            if text_blocks:
                # Filter out very small text and sort by size
                large_text = [b for b in text_blocks if b["size"] >= 12 and len(b["text"]) > 5]
                if large_text:
                    # Get largest text that's likely a title
                    title_candidate = max(large_text, key=lambda x: x["size"])
                    if len(title_candidate["text"]) > 10:
                        metadata["title"] = title_candidate["text"]

        doc.close()
        return metadata

    except Exception as e:
        print(f"PDF structure extraction error: {e}")
        return {}


def extract_enhanced_patterns(text: str, filename: str) -> Dict[str, Any]:
    """Enhanced pattern extraction with better regex patterns"""
    metadata = {}

    # Enhanced title extraction patterns
    title_patterns = [
        r"^([A-Z][^.]*(?:User|Installation|Reference|Integration|Security|Release)\s+(?:Guide|Manual|Notes))",
        r"^\s*([A-Z][^.]{10,80})\s*\n",
        r"^([A-Z][^.]*(?:Guide|Manual|Notes)[^.]*)",
        r"GUIDE\s*\n([A-Z][^.]*)\n",
        r"MANUAL\s*\n([A-Z][^.]*)\n",
    ]

    for pattern in title_patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match and not metadata.get("title"):
            candidate = match.group(1).strip()
            if 10 <= len(candidate) <= 100:  # Reasonable title length
                metadata["title"] = candidate
                break

    # Enhanced version extraction
    version_patterns = [
        r"version\s+(\d+\.\d+(?:\.\d+)?)",
        r"v(\d+\.\d+(?:\.\d+)?)",
        r"release\s+(\d+\.\d+(?:\.\d+)?)",
        r"(\d+\.\d+)\s+(?:user|installation|reference)",
        r"RNI\s+(\d+\.\d+(?:\.\d+)?)",
        r"VERSION\s+(\d+\.\d+(?:\.\d+)?)",
    ]

    for pattern in version_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata["version"] = match.group(1)
            break

    # Enhanced document number extraction
    doc_number_patterns = [
        r"([A-Z]{2,4}-\d{4,6}-\d{1,3})",
        r"(AUG-\d{5}-\d{2})",
        r"(ARN-\d{5}-\d{2})",
        r"(AIG-\d{5}-\d{2})",
        r"(AIT-\d{5}-\d{2})",
        r"Document\s+Number[:\s]+([A-Z0-9-]+)",
        r"Doc\.?\s+No\.?[:\s]+([A-Z0-9-]+)",
    ]

    for pattern in doc_number_patterns:
        match = re.search(pattern, text)
        if match:
            metadata["doc_number"] = match.group(1)
            break

    # Enhanced GA date extraction
    date_patterns = [
        r"GA\s+Date[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
        r"General\s+Availability[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
        r"Release\s+Date[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata["ga_date"] = match.group(1)
            break

    # Enhanced copyright extraction
    copyright_patterns = [r"©\s*(\d{4})", r"Copyright\s+©?\s*(\d{4})", r"Copyright\s+\(c\)\s*(\d{4})"]

    for pattern in copyright_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata["copyright_year"] = int(match.group(1))
            break

    # Enhanced publisher extraction
    publisher_patterns = [
        r"(Aclara\s+Technologies)",
        r"(Sensus)",
        r"©\s*\d{4}\s+([A-Za-z\s]+)",
        r"Copyright\s+©?\s*\d{4}\s+([A-Za-z\s]+)",
    ]

    for pattern in publisher_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            publisher = match.group(1).strip()
            if publisher and len(publisher) > 2:
                metadata["publisher"] = publisher
                break

    return metadata


def analyze_content_structure(text: str) -> Dict[str, Any]:
    """Analyze document content structure for additional metadata"""
    metadata = {}

    # Analyze product families based on content
    product_indicators = {
        "RNI": ["regional network interface", "rni system", "rni server", "rni installer"],
        "FlexNet": ["flexnet", "flex net", "flexnet communication", "flexnet esm"],
        "ESM": ["enhanced supervisory message", "esm", "supervisory message"],
        "MultiSpeak": ["multispeak", "multi speak", "multispeak protocol"],
    }

    detected_products = []
    text_lower = text.lower()

    for product, indicators in product_indicators.items():
        for indicator in indicators:
            if indicator in text_lower:
                detected_products.append(product)
                break

    if detected_products:
        metadata["product_family"] = list(set(detected_products))

    # Analyze service lines
    service_indicators = {
        "Electric": ["electric", "electricity", "power", "meter reading", "electric meter"],
        "Gas": ["gas", "natural gas", "gas meter"],
        "Water": ["water", "h2o", "water meter"],
        "Common": ["communication", "protocol", "interface", "network"],
    }

    detected_services = []
    for service, indicators in service_indicators.items():
        for indicator in indicators:
            if indicator in text_lower:
                detected_services.append(service)
                break

    if detected_services:
        metadata["service_lines"] = detected_services

    # Analyze target audiences
    audience_indicators = {
        "RNI administrators": ["administrator", "admin", "system admin", "rni admin"],
        "Utility operations": ["utility", "operations", "operator", "field operations"],
        "Technical support": ["support", "troubleshooting", "maintenance", "tech support"],
        "Developers": ["developer", "api", "integration", "programming", "sdk"],
        "End users": ["user guide", "end user", "customer", "user manual"],
    }

    detected_audiences = []
    for audience, indicators in audience_indicators.items():
        for indicator in indicators:
            if indicator in text_lower:
                detected_audiences.append(audience)
                break

    if detected_audiences:
        metadata["audiences"] = detected_audiences

    return metadata


def enhanced_document_classification(text: str, filename: str) -> Dict[str, Any]:
    """
    Enhanced classification using multiple strategies and pattern matching
    """
    filename_lower = filename.lower()
    text_lower = text.lower()

    # Check enhanced patterns first
    for pattern_name, pattern_config in ENHANCED_CLASSIFICATION_PATTERNS.items():
        # Check filename patterns
        filename_match = any(re.search(pattern, filename_lower) for pattern in pattern_config["filename_patterns"])

        # Check content patterns
        content_match = any(re.search(pattern, text_lower) for pattern in pattern_config["content_patterns"])

        if filename_match or content_match:
            base_confidence = 0.8 if filename_match else 0.7
            confidence = min(base_confidence + pattern_config["confidence_boost"], 0.95)

            return {
                "document_type": pattern_config["primary_type"],
                "product_name": extract_product_name(filename, text),
                "product_version": extract_product_version(filename, text),
                "document_category": get_document_category(pattern_config["primary_type"]),
                "confidence": confidence,
                "metadata": {
                    "classification_method": "enhanced_patterns",
                    "pattern_matched": pattern_name,
                    "specialization_tags": pattern_config["specialization_tags"],
                    "match_type": "filename" if filename_match else "content",
                },
            }

    # Fall back to original classification with improvements
    return improved_fallback_classification(text, filename)


def improved_fallback_classification(text: str, filename: str) -> Dict[str, Any]:
    """Improved fallback classification with better patterns"""
    result = {
        "document_type": "unknown",
        "product_name": "unknown",
        "product_version": "unknown",
        "document_category": "documentation",
        "confidence": 0.5,
        "metadata": {"classification_method": "improved_fallback", "key_topics": [], "target_audience": "technical"},
    }

    filename_lower = filename.lower()
    text_lower = text.lower()

    # Enhanced document type patterns
    doc_type_patterns = {
        "user_guide": [r"user\s+guide", r"user\s+manual", r"users?\s+guide", r"operator\s+guide", r"operator\s+manual"],
        "installation_guide": [
            r"installation\s+guide",
            r"install\s+guide",
            r"setup\s+guide",
            r"deployment\s+guide",
            r"configuration\s+guide",
        ],
        "reference_manual": [
            r"reference\s+manual",
            r"reference\s+guide",
            r"specs?\s+manual",
            r"specification",
            r"technical\s+reference",
        ],
        "release_notes": [
            r"release\s+notes?",
            r"release\s+note",
            r"changelog",
            r"version\s+notes?",
            r"update\s+notes?",
        ],
        "integration_guide": [r"integration\s+guide", r"integration\s+manual", r"api\s+guide", r"sdk\s+guide"],
        "security_guide": [r"security\s+guide", r"security\s+manual", r"security\s+user\s+guide"],
        "administration_guide": [
            r"administration\s+guide",
            r"admin\s+guide",
            r"system\s+admin",
            r"administrator\s+guide",
        ],
    }

    # Check patterns with higher confidence for exact matches
    for doc_type, patterns in doc_type_patterns.items():
        for pattern in patterns:
            if re.search(pattern, filename_lower) or re.search(pattern, text_lower):
                result["document_type"] = doc_type
                result["confidence"] = 0.85 if re.search(pattern, filename_lower) else 0.75
                break
        if result["document_type"] != "unknown":
            break

    # Extract product information with better patterns
    product_patterns = {
        "RNI": [
            r"rni\s+(\d+\.\d+(?:\.\d+)?)",
            r"regional\s+network\s+interface\s+(\d+\.\d+)",
            r"rni\s+version\s+(\d+\.\d+)",
        ],
        "FlexNet": [r"flexnet\s+(\d+\.\d+(?:\.\d+)?)", r"flex\s+net\s+(\d+\.\d+)"],
        "ESM": [r"esm\s+(\d+\.\d+(?:\.\d+)?)", r"enhanced\s+supervisory\s+message"],
        "MultiSpeak": [r"multispeak\s*v?(\d+\.\d+)", r"multi\s+speak\s*v?(\d+\.\d+)"],
    }

    for product, patterns in product_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, filename_lower) or re.search(pattern, text_lower)
            if match:
                result["product_name"] = product
                if match.groups():
                    result["product_version"] = match.group(1)
                result["confidence"] = min(result["confidence"] + 0.15, 0.9)
                break
        if result["product_name"] != "unknown":
            break

    return result


def extract_product_name(filename: str, text: str) -> str:
    """Extract product name with enhanced patterns"""
    combined_text = (filename + " " + text[:500]).lower()

    # Priority order for product detection
    product_patterns = [
        ("RNI", r"\brni\b"),
        ("FlexNet", r"\bflexnet\b|\bflex\s+net\b"),
        ("ESM", r"\besm\b|\benhanced\s+supervisory\s+message\b"),
        ("MultiSpeak", r"\bmultispeak\b|\bmulti\s+speak\b"),
    ]

    for product, pattern in product_patterns:
        if re.search(pattern, combined_text):
            return product

    return "unknown"


def extract_product_version(filename: str, text: str) -> str:
    """Extract product version with enhanced patterns"""
    combined_text = filename + " " + text[:500]

    version_patterns = [
        r"(\d+\.\d+\.\d+)",  # x.y.z
        r"(\d+\.\d+)",  # x.y
        r"v(\d+\.\d+(?:\.\d+)?)",  # vx.y or vx.y.z
        r"version\s+(\d+\.\d+(?:\.\d+)?)",  # version x.y
    ]

    for pattern in version_patterns:
        match = re.search(pattern, combined_text, re.IGNORECASE)
        if match:
            return match.group(1)

    return "unknown"


def get_document_category(doc_type: str) -> str:
    """Map document type to category"""
    category_mapping = {
        "user_guide": "guide",
        "installation_guide": "guide",
        "integration_guide": "guide",
        "security_guide": "guide",
        "administration_guide": "guide",
        "reference_manual": "reference",
        "technical_specification": "reference",
        "release_notes": "notes",
        "api_documentation": "reference",
    }

    return category_mapping.get(doc_type, "documentation")


# Example usage showing how to integrate these improvements
def process_document_with_enhancements(pdf_path: str, text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process a document with all enhancements
    Returns: (enhanced_metadata, enhanced_classification)
    """
    print(f"Processing document with enhancements: {os.path.basename(pdf_path)}")

    # Enhanced metadata extraction
    enhanced_metadata = extract_enhanced_metadata(pdf_path, text)
    print(f"Enhanced metadata extracted: {len([k for k, v in enhanced_metadata.items() if v])} fields populated")

    # Enhanced classification
    enhanced_classification = enhanced_document_classification(text, os.path.basename(pdf_path))
    print(
        f"Enhanced classification: {enhanced_classification['document_type']} (confidence: {enhanced_classification['confidence']:.2f})"
    )

    return enhanced_metadata, enhanced_classification


if __name__ == "__main__":
    # Example test
    test_text = """
    INSTALLATION GUIDE
    AIG-10023-29

    FlexNet RNI Hardware Security Module

    FlexNet® RNI Hardware Security Module Installation Guide

    This guide provides instructions for installing and configuring
    the hardware security module (HSM) for RNI 4.16 systems.
    """

    test_filename = "RNI 4.16 Hardware Security Module Installation Guide.pdf"

    metadata, classification = process_document_with_enhancements("test.pdf", test_text)

    print(f"\nMetadata: {json.dumps(metadata, indent=2)}")
    print(f"\nClassification: {json.dumps(classification, indent=2)}")
