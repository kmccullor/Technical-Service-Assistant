import json
import hashlib
import os
import random
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import requests

sys.path.append("/app")
from typing import Any, Dict, List, Optional, Tuple
from config import get_settings
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="pdf_processor_utils",
    log_level="INFO",
    log_file=f'/app/logs/pdf_processor_utils_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True,
)

# Get settings instance
settings = get_settings()

"""NOTE: A previous simple SECURITY_DOCUMENT_PATTERNS dict existed here but was superseded by
the advanced keyed structure below. Removed to avoid accidental overwrites."""

# Enhanced classification patterns for security documents
SECURITY_DOCUMENT_PATTERNS = {
    'hardware_security_module': {
        'filename_patterns': [
            r'hardware\s+security\s+module.*installation',
            r'hsm.*installation.*guide',
            r'security\s+module.*installation'
        ],
        'content_patterns': [
            r'hardware security module',
            r'hsm installation',
            r'security module setup'
        ],
        'override_type': 'security_guide',
        'confidence': 0.92
    },
    'system_security_user_guide': {
        'filename_patterns': [
            r'system\s+security.*user\s+guide',
            r'security.*user\s+guide'
        ],
        'content_patterns': [
            r'system security',
            r'security configuration',
            r'security administration'
        ],
        'override_type': 'security_guide',
        'confidence': 0.90
    },
    'base_station_security': {
        'filename_patterns': [
            r'base\s+station\s+security.*user\s+guide'
        ],
        'content_patterns': [
            r'base station security',
            r'field device security'
        ],
        'override_type': 'security_guide',
        'confidence': 0.88
    },
    'compliance_and_governance': {
        'filename_patterns': [
            r'compliance\s+audit.*',
            r'regulatory\s+requirements.*',
            r'security\s+standards.*',
            r'security\s+policy.*',
            r'privacy\s+controls?.*'
        ],
        'content_patterns': [
            r'regulatory\s+compliance',
            r'security\s+framework',
            r'security\s+governance',
            r'compliance\s+assessment',
            r'gdpr|hipaa'
        ],
        'override_type': 'security_guide',
        'confidence': 0.90
    },
    'threat_and_risk': {
        'filename_patterns': [
            r'threat\s+assessment.*',
            r'risk\s+analysis.*',
            r'vulnerability\s+scan.*',
            r'incident\s+response.*',
            r'penetration\s+test.*'
        ],
        'content_patterns': [
            r'threat\s+modeling',
            r'risk\s+assessment',
            r'security\s+incident',
            r'vulnerability\s+assessment',
            r'penetration\s+testing'
        ],
        'override_type': 'security_guide',
        'confidence': 0.91
    }
}


def extract_text(pdf_path: str) -> str:
    """Extract plain text from a PDF using PyMuPDF (fitz) with structured logging."""
    logger.info(f"Starting text extraction from: {pdf_path}")
    start_time = time.time()

    try:
        import fitz  # PyMuPDF

        logger.debug("PyMuPDF (fitz) imported successfully")
    except Exception as e:
        logger.error(f"Failed to import PyMuPDF (fitz): {e}")
        raise RuntimeError(f"PyMuPDF (fitz) is required for extract_text: {e}")

    try:
        doc = fitz.open(pdf_path)
        logger.info(f"PDF opened successfully. Pages: {len(doc)}")

        text = ""
        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text()
            text += page_text
            logger.debug(f"Page {page_num + 1}: extracted {len(page_text)} characters")

        doc.close()
        extraction_time = time.time() - start_time
        logger.info(f"Text extraction completed. Total characters: {len(text)}, Time: {extraction_time:.2f}s")
        return text

    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        raise


def extract_tables(pdf_path: str) -> List[Any]:
    """Extract tables from a PDF using camelot and return list-of-rows per table."""
    try:
        import camelot
    except Exception as e:
        raise RuntimeError(f"camelot is required for extract_tables: {e}")
    tables = camelot.read_pdf(pdf_path, pages="all")
    table_data = []
    for table in tables:
        table_data.append(table.df.to_dict("records"))
    return table_data


def extract_images(pdf_path: str, output_dir: str) -> List[str]:
    """Extract images from a PDF and write them to output_dir. Returns list of file paths."""
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        raise RuntimeError(f"PyMuPDF (fitz) is required for extract_images: {e}")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    image_paths: List[str] = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image.get("ext", "png")
            image_filename = (
                f"{os.path.splitext(os.path.basename(pdf_path))[0]}_page{page_num+1}_img{img_index+1}.{image_ext}"
            )
            image_path = os.path.join(output_dir, image_filename)
            with open(image_path, "wb") as img_file:
                img_file.write(image_bytes)
            image_paths.append(image_path)
    return image_paths


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of file for deduplication."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def detect_confidentiality(text: str) -> str:
    """
    Analyze document text for confidentiality indicators and classify as 'public' or 'private'.

    Scans for common privacy/confidentiality keywords and patterns to determine
    if a document contains sensitive information.

    Args:
        text: The full document text to analyze

    Returns:
        str: 'private' if confidential content detected, 'public' otherwise

    Example:
        >>> detect_confidentiality("This document is CONFIDENTIAL")
        'private'
        >>> detect_confidentiality("This is a public report")
        'public'
    """
    if not text or not text.strip():
        logger.debug("Empty text provided for confidentiality detection, defaulting to public")
        return 'public'

    # Convert to lowercase for case-insensitive matching
    text_lower = text.lower()

    # Define confidentiality keywords and patterns
    confidentiality_keywords = [
        # Direct privacy indicators
        'confidential', 'private', 'restricted', 'classified',
        'proprietary', 'internal', 'sensitive', 'privileged',

        # Legal/compliance terms
        'attorney-client', 'attorney client', 'work product',
        'trade secret', 'proprietary information',

        # Business sensitivity
        'do not distribute', 'internal use only', 'not for distribution',
        'for internal use', 'company confidential',

        # Personal information indicators
        'personally identifiable', 'pii', 'personal information',
        'social security number', 'ssn', 'credit card',

        # Data classification
        'top secret', 'secret', 'eyes only', 'need to know'
    ]

    # Check for exact keyword matches
    for keyword in confidentiality_keywords:
        if keyword in text_lower:
            logger.info(f"Confidentiality keyword detected: '{keyword}' - classifying as private")
            return 'private'

    # Check for common confidentiality patterns with regex
    confidentiality_patterns = [
        r'\bconfidential\b.*\bdocument\b',  # "confidential document"
        r'\bdo\s+not\s+(share|distribute|disclose)\b',  # "do not share/distribute"
        r'\bfor\s+internal\s+use\s+only\b',  # "for internal use only"
        r'\bnot\s+for\s+(public|external)\b',  # "not for public/external"
        r'\b(strictly|highly)\s+confidential\b',  # "strictly/highly confidential"
        r'\bclassification\s*:\s*(private|confidential|restricted)\b'  # "classification: private"
    ]

    for pattern in confidentiality_patterns:
        if re.search(pattern, text_lower):
            logger.info(f"Confidentiality pattern detected: '{pattern}' - classifying as private")
            return 'private'

    # Check document headers/footers for classification markings
    # Split into lines and check first/last few lines for headers/footers
    lines = text.split('\n')
    header_footer_lines = lines[:5] + lines[-5:]  # First and last 5 lines

    for line in header_footer_lines:
        line_lower = line.lower().strip()
        if any(keyword in line_lower for keyword in ['confidential', 'private', 'restricted']):
            logger.info(f"Confidentiality marking in header/footer: '{line.strip()}' - classifying as private")
            return 'private'

    logger.debug("No confidentiality indicators detected - classifying as public")
    return 'public'


def extract_pdf_structure_metadata(pdf_path: str) -> Dict[str, Any]:
    """
    Extract metadata from PDF structure and properties for better title/metadata extraction.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with extracted structural metadata
    """
    try:
        import fitz
        doc = fitz.open(pdf_path)

        # Get PDF metadata
        pdf_metadata = doc.metadata or {}

        metadata = {}

        # Extract title from PDF properties with improved validation
        if pdf_metadata.get('title'):
            title = pdf_metadata['title'].strip()
            # Improved title validation - remove common non-title patterns
            if (len(title) > 5 and
                not title.lower().startswith(('untitled', 'document', 'page')) and
                not re.match(r'^\d+$', title)):  # Not just numbers
                metadata['title'] = title

        # Extract creator/publisher
        if pdf_metadata.get('creator'):
            metadata['publisher'] = pdf_metadata['creator'].strip()
        elif pdf_metadata.get('producer'):
            metadata['publisher'] = pdf_metadata['producer'].strip()

        # Enhanced first page analysis for title if not in metadata
        if not metadata.get('title') and len(doc) > 0:
            first_page = doc[0]
            blocks = first_page.get_text("dict")["blocks"]

            # Find text blocks and identify likely title
            text_blocks = []
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text and len(text) > 5:
                                text_blocks.append({
                                    'text': text,
                                    'size': span["size"],
                                    'flags': span["flags"],
                                    'bbox': span["bbox"],
                                    'font': span.get("font", ""),
                                    'y_position': span["bbox"][1]  # Top Y coordinate
                                })

            # Enhanced title detection logic
            if text_blocks:
                # Sort by position (top first) and size
                text_blocks.sort(key=lambda x: (x['y_position'], -x['size']))

                # Look for title patterns in top portion of first page
                top_blocks = [b for b in text_blocks if b['y_position'] < 200]  # Top 200 points

                # Filter for large text that could be titles
                title_candidates = []
                for block in top_blocks:
                    if (block['size'] >= 12 and
                        len(block['text']) >= 10 and
                        len(block['text']) <= 150 and
                        not block['text'].lower().startswith(('page', 'copyright', '©', 'confidential')) and
                        not re.match(r'^\d+$', block['text']) and
                        not block['text'].count('.') > 3):  # Not file paths
                        title_candidates.append(block)

                if title_candidates:
                    # Prefer largest font size in top area
                    best_title = max(title_candidates, key=lambda x: x['size'])
                    metadata['title'] = best_title['text']
                    logger.debug(f"Extracted title from structure: {best_title['text']}")

        # Extract additional metadata from document info
        if pdf_metadata.get('subject'):
            metadata['subject'] = pdf_metadata['subject'].strip()

        if pdf_metadata.get('keywords'):
            metadata['keywords'] = pdf_metadata['keywords'].strip()

        # Extract creation/modification dates
        if pdf_metadata.get('creationDate'):
            metadata['creation_date'] = pdf_metadata['creationDate']

        if pdf_metadata.get('modDate'):
            metadata['modification_date'] = pdf_metadata['modDate']

        doc.close()
        logger.debug(f"PDF structure metadata extracted: {len(metadata)} fields")
        return metadata

    except Exception as e:
        logger.warning(f"PDF structure extraction error: {e}")
        return {}


def extract_document_metadata(text: str, filename: str) -> Dict[str, Any]:
    """
    Extract comprehensive document metadata using pattern matching and AI classification.

    Args:
        text: Full document text
        filename: Document filename

    Returns:
        Dictionary with extracted metadata including classification results
    """
    logger.info(f"Extracting document metadata for: {filename}")

    # Initialize metadata structure
    metadata = {
        'title': None,
        'version': None,
        'doc_number': None,
        'ga_date': None,
        'publisher': None,
        'copyright_year': None,
        'product_family': [],
        'service_lines': [],
        'audiences': []
    }

    # Extract title from first few lines
    lines = text.split('\n')[:10]
    for line in lines:
        line = line.strip()
        if line and len(line) > 10 and not line.lower().startswith(('page', 'copyright', '©')):
            if not metadata['title']:
                metadata['title'] = line
                break

    # Extract version patterns (e.g., "4.16", "v1.2.3")
    version_patterns = [
        r'version\s+(\d+\.\d+(?:\.\d+)?)',
        r'v(\d+\.\d+(?:\.\d+)?)',
        r'(\d+\.\d+)\s+(?:user|installation|reference)',
        r'release\s+(\d+\.\d+(?:\.\d+)?)'
    ]

    for pattern in version_patterns:
        match = re.search(pattern, text.lower())
        if match:
            metadata['version'] = match.group(1)
            break

    # Extract document number (e.g., ARN-10003-01)
    doc_number_pattern = r'([A-Z]{2,4}-\d{4,6}-\d{1,3})'
    doc_match = re.search(doc_number_pattern, text)
    if doc_match:
        metadata['doc_number'] = doc_match.group(1)

    # Extract GA date patterns
    date_patterns = [
        r'ga\s+date[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',
        r'general\s+availability[:\s]+(\w+\s+\d{1,2},?\s+\d{4})'
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text.lower())
        if match:
            metadata['ga_date'] = match.group(1)
            break

    # Extract copyright year
    copyright_match = re.search(r'©?\s*(?:copyright\s+)?(\d{4})', text.lower())
    if copyright_match:
        metadata['copyright_year'] = int(copyright_match.group(1))

    # Extract publisher (common patterns)
    if 'aclara' in text.lower():
        metadata['publisher'] = 'Aclara Technologies'
    elif 'sensus' in text.lower():
        metadata['publisher'] = 'Sensus'

    # Extract product families
    product_keywords = {
        'RNI': ['rni', 'regional network interface'],
        'FlexNet': ['flexnet', 'flex net'],
        'ESM': ['esm', 'endpoint service manager'],
        'MultiSpeak': ['multispeak', 'multi speak']
    }

    for product, keywords in product_keywords.items():
        if any(keyword in text.lower() for keyword in keywords):
            metadata['product_family'].append(product)

    # Extract service lines
    service_keywords = {
        'Electric': ['electric', 'electricity', 'power', 'meter reading'],
        'Gas': ['gas', 'natural gas'],
        'Water': ['water', 'h2o'],
        'Common': ['communication', 'protocol', 'interface']
    }

    for service, keywords in service_keywords.items():
        if any(keyword in text.lower() for keyword in keywords):
            metadata['service_lines'].append(service)

    # Extract target audiences
    audience_keywords = {
        'RNI administrators': ['administrator', 'admin', 'system admin'],
        'Utility operations': ['utility', 'operations', 'operator'],
        'Technical support': ['support', 'troubleshooting', 'maintenance'],
        'Developers': ['developer', 'api', 'integration', 'programming'],
        'End users': ['user guide', 'end user', 'customer']
    }

    for audience, keywords in audience_keywords.items():
        if any(keyword in text.lower() for keyword in keywords):
            metadata['audiences'].append(audience)

    logger.info(f"Extracted metadata - Title: {metadata['title'][:50] if metadata['title'] else 'None'}...")
    return metadata


def apply_security_classification_overrides(text: str, filename: str) -> Optional[Dict[str, Any]]:
    """
    Apply security document classification overrides to fix misclassification issues.

    This function checks for security-related patterns in both filename and content
    to correctly classify documents that would otherwise be misidentified.

    Args:
        text: Document content text
        filename: Document filename

    Returns:
        Classification result dict if security patterns match, None otherwise
    """
    filename_lower = filename.lower()
    text_lower = text.lower()

    # Check filename patterns first
    for pattern in SECURITY_DOCUMENT_PATTERNS['filename_patterns']:
        if re.search(pattern, filename_lower):
            logger.info(f"Security filename pattern matched: {pattern} in {filename}")

            # Extract product information from filename/content
            product_name = 'unknown'
            if 'rni' in filename_lower or 'rni' in text_lower:
                product_name = 'RNI'
            elif 'flexnet' in filename_lower or 'flexnet' in text_lower:
                product_name = 'FlexNet'
            elif 'esm' in filename_lower or 'esm' in text_lower:
                product_name = 'ESM'

            # Extract version if available
            version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', filename)
            product_version = version_match.group(1) if version_match else 'unknown'

            return {
                'document_type': 'security_guide',
                'product_name': product_name,
                'product_version': product_version,
                'document_category': 'security',
                'confidence': 0.95,
                'metadata': {
                    'classification_source': 'security_override',
                    'matched_pattern': pattern
                }
            }

    # Check content patterns if filename didn't match
    for pattern in SECURITY_DOCUMENT_PATTERNS['content_patterns']:
        if re.search(pattern, text_lower):
            logger.info(f"Security content pattern matched: {pattern}")

            # Extract product information
            product_name = 'unknown'
            if 'rni' in text_lower:
                product_name = 'RNI'
            elif 'flexnet' in text_lower:
                product_name = 'FlexNet'
            elif 'esm' in text_lower:
                product_name = 'ESM'

            # Extract version from content
            version_match = re.search(r'version\s+(\d+\.\d+(?:\.\d+)?)', text_lower)
            product_version = version_match.group(1) if version_match else 'unknown'

            return {
                'document_type': 'security_guide',
                'product_name': product_name,
                'product_version': product_version,
                'document_category': 'security',
                'confidence': 0.90,
                'metadata': {
                    'classification_source': 'security_override',
                    'matched_pattern': pattern
                }
            }

    return None


def classify_document_with_ai(text: str, filename: str = "") -> Dict[str, Any]:
    from config import get_settings
    settings = get_settings()
    """
    Use AI to classify document type, extract product information, and categorize content.

    Args:
        text: The full document text to analyze
        filename: Optional filename for additional context

    Returns:
        Dict containing classification results with confidence scores

    Example:
        >>> classify_document_with_ai("RNI 4.16 User Guide...", "RNI_4.16_User_Guide.pdf")
        {
            'document_type': 'user_guide',
            'product_name': 'RNI',
            'product_version': '4.16',
            'document_category': 'documentation',
            'confidence': 0.95,
            'metadata': {...}
        }
    """
    if not text or not text.strip():
        logger.debug("Empty text provided for AI classification, returning defaults")
        return {
            'document_type': 'unknown',
            'product_name': 'unknown',
            'product_version': 'unknown',
            'document_category': 'documentation',
            'confidence': 0.0,
            'metadata': {}
        }

    logger.info(f"Starting AI classification for document: {filename}")
    start_time = time.time()

    # Apply security classification overrides before AI analysis
    security_override = apply_security_classification_overrides(text, filename)
    if security_override:
        logger.info(f"Applied security classification override: {security_override['document_type']}")
        return security_override

    # Prepare smaller text sample for faster AI analysis (first 1000 characters)
    analysis_text = text[:1000] if len(text) > 1000 else text

    # Build concise AI prompt for faster classification
    classification_prompt = f"""Classify this document. Return only valid JSON:

File: {filename}
Content: {analysis_text}

JSON format:
{{
    "document_type": "user_guide|installation_guide|reference_manual|release_notes|technical_specification|integration_guide|security_guide|unknown",
    "product_name": "RNI|FlexNet|ESM|MultiSpeak|unknown",
    "product_version": "version (e.g. 4.16)|unknown",
    "document_category": "documentation|specification|guide|manual|notes",
    "confidence": 0.8
}}

Respond with JSON only."""

    try:
        # Use intelligent routing to get the best available Ollama instance
        classification_result = get_ai_classification(classification_prompt)

        if classification_result:
            classification_time = time.time() - start_time
            logger.info(f"AI classification completed successfully in {classification_time:.2f}s")
            return classification_result
        else:
            logger.warning("AI classification returned empty result, using fallback")

    except Exception as e:
        logger.error(f"AI classification failed: {e}")

    # Fallback to rule-based classification if AI fails
    logger.info("Using fallback rule-based classification")
    return classify_document_fallback(text, filename)


def get_ai_classification(prompt: str) -> Optional[Dict[str, Any]]:
    """
    Get AI-powered classification using Ollama with intelligent routing.

    Args:
        prompt: The classification prompt for the AI model

    Returns:
        Parsed classification result or None if failed
    """
    # List of available Ollama instances for load balancing
    ollama_instances = [
        "http://ollama-server-1:11434/api/generate",
        "http://ollama-server-2:11434/api/generate",
        "http://ollama-server-3:11434/api/generate",
        "http://ollama-server-4:11434/api/generate",
    ]

    # Shuffle for load balancing
    urls_to_try = ollama_instances.copy()
    random.shuffle(urls_to_try)

    # Use faster model for classification - mistral is more efficient for structured tasks
    classification_model = settings.chat_model  # Use configured chat model

    last_error = None
    for attempt, url in enumerate(urls_to_try, 1):
        try:
            logger.debug(f"AI classification attempt {attempt}/{len(urls_to_try)}: {url}")

            response = requests.post(
                url,
                json={
                    "model": classification_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent classification
                        "top_p": 0.9,
                        "num_predict": 200   # Shorter response for JSON only
                    }
                },
                timeout=settings.embedding_timeout_seconds  # Configurable timeout
            )
            response.raise_for_status()

            # Parse AI response
            ai_response = response.json()
            if 'response' in ai_response:
                raw_response = ai_response['response'].strip()

                # Try to extract JSON from response
                classification_data = parse_ai_classification_response(raw_response)
                if classification_data:
                    logger.debug(f"AI classification successful from {url}")
                    return classification_data
                else:
                    logger.warning(f"Could not parse AI response from {url}")

        except requests.exceptions.Timeout as e:
            last_error = e
            logger.warning(f"Timeout from {url}: {e}")
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(f"Request failed to {url}: {e}")
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error with {url}: {e}")

    logger.error(f"Failed to get AI classification from all instances. Last error: {last_error}")
    return None


def parse_ai_classification_response(response: str) -> Optional[Dict[str, Any]]:
    """
    Parse AI response and extract classification JSON.

    Args:
        response: Raw AI response text

    Returns:
        Parsed classification dictionary or None if parsing failed
    """
    try:
        # Try direct JSON parsing first
        if response.startswith('{') and response.endswith('}'):
            return json.loads(response)

        # Extract JSON from response text
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)

        # Try to find JSON-like structure
        lines = response.split('\n')
        json_lines = []
        in_json = False

        for line in lines:
            if line.strip().startswith('{'):
                in_json = True
            if in_json:
                json_lines.append(line)
            if in_json and line.strip().endswith('}'):
                break

        if json_lines:
            json_str = '\n'.join(json_lines)
            return json.loads(json_str)

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parsing failed: {e}")
    except Exception as e:
        logger.error(f"Error parsing AI response: {e}")

    return None


def classify_document_fallback(text: str, filename: str = "") -> Dict[str, Any]:
    """
    Fallback rule-based classification when AI classification fails.

    Args:
        text: Document text to analyze
        filename: Optional filename for pattern matching

    Returns:
        Basic classification based on filename and content patterns
    """
    logger.info("Applying rule-based fallback classification")

    # Initialize default classification
    result = {
        'document_type': 'unknown',
        'product_name': 'unknown',
        'product_version': 'unknown',
        'document_category': 'documentation',
        'confidence': 0.5,  # Medium confidence for rule-based
        'metadata': {
            'classification_method': 'rule_based_fallback',
            'key_topics': [],
            'target_audience': 'technical',
            'document_purpose': 'technical documentation'
        }
    }

    filename_lower = filename.lower()
    text_lower = text.lower()

    # Extract product name and version from filename patterns
    # Pattern: RNI 4.16 Document Type.pdf
    product_match = re.search(r'(rni|flexnet|esm|multispeak|ppa)\s*(\d+\.\d+(?:\.\d+)?)', filename_lower)
    if product_match:
        result['product_name'] = product_match.group(1).upper()
        result['product_version'] = product_match.group(2)
        result['confidence'] = 0.8

    # Classify document type based on filename keywords
    doc_type_patterns = {
        'user_guide': ['user guide', 'user manual'],
        'installation_guide': ['installation guide', 'install guide'],
        'reference_manual': ['reference manual', 'reference guide'],
        'release_notes': ['release notes', 'release note'],
        'integration_guide': ['integration guide'],
        'security_guide': ['security guide', 'security user guide'],
        'administration_guide': ['administration guide', 'admin guide', 'system admin'],
        'technical_specification': ['tech note', 'specification', 'specs'],
        'api_documentation': ['api guide', 'api documentation']
    }

    for doc_type, patterns in doc_type_patterns.items():
        if any(pattern in filename_lower for pattern in patterns):
            result['document_type'] = doc_type
            result['confidence'] = min(result['confidence'] + 0.2, 0.9)
            break

    # Determine document category
    if result['document_type'] in ['user_guide', 'installation_guide', 'integration_guide']:
        result['document_category'] = 'guide'
    elif result['document_type'] in ['reference_manual', 'technical_specification']:
        result['document_category'] = 'reference'
    elif result['document_type'] in ['security_guide', 'administration_guide']:
        result['document_category'] = 'administration'
    elif result['document_type'] == 'release_notes':
        result['document_category'] = 'notes'

    # Extract key topics from content (simple keyword analysis)
    topic_keywords = {
        'security': ['security', 'encryption', 'authentication', 'certificate'],
        'installation': ['install', 'setup', 'configure', 'deployment'],
        'integration': ['integration', 'api', 'interface', 'protocol'],
        'administration': ['admin', 'management', 'configuration', 'settings'],
        'networking': ['network', 'connection', 'communication', 'protocol']
    }

    detected_topics = []
    for topic, keywords in topic_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            detected_topics.append(topic)

    result['metadata']['key_topics'] = detected_topics[:5]  # Limit to top 5 topics

    # Apply security document overrides before returning
    security_override = apply_security_classification_overrides(text, filename)
    if security_override:
        logger.info("Applied security classification override in fallback")
        return security_override

    logger.info(f"Enhanced fallback classification: {result['document_type']} for {result['product_name']} {result['product_version']} (confidence: {result['confidence']:.2f})")
    return result


def chunk_text_semantic(text: str, document_name: str = "", max_chunk_size: int = 1000) -> List[Dict[str, Any]]:
    """
    Split text into semantic chunks using sentence boundaries and overlap.
    Enhanced version with better structure preservation.
    """
    try:
        import nltk
        from nltk.tokenize import sent_tokenize, word_tokenize
    except Exception:
        raise RuntimeError("NLTK and the punkt tokenizer are required for chunk_text_semantic")

    # Ensure required NLTK data is available
    try:
        nltk.data.find("tokenizers/punkt")
    except Exception:
        nltk.download("punkt", quiet=True)

    try:
        nltk.data.find("tokenizers/punkt_tab")
    except Exception:
        nltk.download("punkt_tab", quiet=True)

    logger.info(f"Starting semantic chunking for {document_name}")

    # Split text into paragraphs first to preserve structure
    paragraphs = text.split("\n\n")
    chunks = []
    chunk_index = 0

    for para_idx, paragraph in enumerate(paragraphs):
        if not paragraph.strip():
            continue

        # Tokenize paragraph into sentences
        sentences = sent_tokenize(paragraph.strip())

        current_chunk = ""
        current_sentences = []

        for sent_idx, sentence in enumerate(sentences):
            # Check if adding this sentence would exceed max chunk size
            potential_chunk = current_chunk + " " + sentence if current_chunk else sentence

            if len(potential_chunk) <= max_chunk_size:
                current_chunk = potential_chunk
                current_sentences.append(sentence)
            else:
                # Save current chunk if it has content
                if current_chunk:
                    # Add overlap from previous sentence for context
                    overlap_text = ""
                    if chunk_index > 0 and current_sentences:
                        overlap_text = current_sentences[0] + " "

                    chunk_content = overlap_text + current_chunk

                    # Generate content hash for deduplication
                    content_hash = hashlib.sha256(current_chunk.encode()).hexdigest()[:16]

                    chunks.append({
                        "content": chunk_content,
                        "content_hash": content_hash,
                        "chunk_index": chunk_index,
                        "page_number": para_idx + 1,  # Use paragraph as proxy for page
                        "section_title": None,  # Could be enhanced with header detection
                        "chunk_type": "text",
                        "metadata": {
                            "document": document_name,
                            "paragraph_index": para_idx,
                            "sentence_count": len(current_sentences),
                            "char_count": len(current_chunk)
                        }
                    })
                    chunk_index += 1

                # Start new chunk with current sentence
                current_chunk = sentence
                current_sentences = [sentence]

        # Don't forget the last chunk in this paragraph
        if current_chunk:
            # Add overlap from previous sentence for context
            overlap_text = ""
            if chunk_index > 0 and current_sentences:
                overlap_text = current_sentences[0] + " "

            chunk_content = overlap_text + current_chunk
            content_hash = hashlib.sha256(current_chunk.encode()).hexdigest()[:16]

            chunks.append({
                "content": chunk_content,
                "content_hash": content_hash,
                "chunk_index": chunk_index,
                "page_number": para_idx + 1,
                "section_title": None,
                "chunk_type": "text",
                "metadata": {
                    "document": document_name,
                    "paragraph_index": para_idx,
                    "sentence_count": len(current_sentences),
                    "char_count": len(current_chunk)
                }
            })
            chunk_index += 1

    logger.info(f"Semantic chunking completed: {len(chunks)} chunks created")
    return chunks


def chunk_text(text: str, document_name: str = "", start_index: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    """Split text into small chunks (by paragraph/sentence) and attach simple metadata."""
    try:
        import nltk
        from nltk.tokenize import sent_tokenize
    except Exception:
        raise RuntimeError("NLTK and the punkt tokenizer are required for chunk_text")
    # Ensure punkt is available; caller may want to silence download
    try:
        nltk.data.find("tokenizers/punkt")
    except Exception:
        nltk.download("punkt", quiet=True)

    paragraphs = text.split("\n\n")
    chunks = []
    page_number = start_index
    for para_idx, para in enumerate(paragraphs):
        if not para.strip():
            continue
        sentences = sent_tokenize(para)
        for sent_idx, sentence in enumerate(sentences):
            chunk_text_content = ""
            if sent_idx > 0:
                chunk_text_content += sentences[sent_idx - 1] + " "
            chunk_text_content += sentence
            metadata = {"document": document_name, "type": "text", "paragraph": para_idx, "sentence": sent_idx}
            chunks.append({"text": chunk_text_content, "metadata": metadata, "page_number": page_number})
            page_number += 1
    return chunks, page_number


def chunk_tables(tables: List[Any], document_name: str = "", start_index: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    chunks = []
    page_number = start_index
    for table_idx, table in enumerate(tables):
        for row_idx, row in enumerate(table):
            row_text = ", ".join([f"{k}: {v}" for k, v in row.items()])
            metadata = {"document": document_name, "type": "table", "table": table_idx, "row": row_idx}
            chunks.append({"text": row_text, "metadata": metadata, "page_number": page_number})
            page_number += 1
    return chunks, page_number


def chunk_images(
    image_paths: List[str], document_name: str = "", start_index: int = 0
) -> Tuple[List[Dict[str, Any]], int]:
    chunks = []
    page_number = start_index
    for img_idx, img_path in enumerate(image_paths):
        img_text = f"Reference to image: {os.path.basename(img_path)}"
        metadata = {"document": document_name, "type": "image", "path": img_path, "image_index": img_idx}
        chunks.append({"text": img_text, "metadata": metadata, "page_number": page_number})
        page_number += 1
    return chunks, page_number


def get_embedding(text: str, model: Optional[str] = None, ollama_url: Optional[str] = None) -> List[float]:
    """Get embedding using intelligent routing across multiple Ollama instances with detailed logging."""
    from config import get_settings
    settings = get_settings()
    
    start_time = time.time()
    text_length = len(text)
    model = model or settings.embedding_model

    logger.info(f"Starting embedding generation. Text length: {text_length}, Model: {model}")

    # List of all available Ollama instances for load balancing
    ollama_instances = [
        "http://ollama-server-1:11434/api/embed",
        "http://ollama-server-2:11434/api/embed",
        "http://ollama-server-3:11434/api/embed",
        "http://ollama-server-4:11434/api/embed",
    ]

    # Use provided URL or use multi-instance load balancing (ignore settings.ollama_url default)
    if ollama_url:
        urls_to_try = [ollama_url]
        logger.debug(f"Using provided URL: {ollama_url}")
    else:
        # Shuffle instances for load balancing across all 4 instances
        urls_to_try = ollama_instances.copy()
        random.shuffle(urls_to_try)
        logger.debug(f"Using load-balanced instances: {urls_to_try}")

    last_error = None
    for attempt, url in enumerate(urls_to_try, 1):
        try:
            logger.debug(f"Attempt {attempt}/{len(urls_to_try)}: Calling {url}")
            response = requests.post(url, json={"model": model, "input": text}, timeout=settings.embedding_timeout_seconds)
            response.raise_for_status()

            embedding = response.json().get("embeddings", [None])[0]
            if embedding:
                embedding_time = time.time() - start_time
                logger.info(
                    f"Embedding successful from {url}. Dimensions: {len(embedding)}, Time: {embedding_time:.2f}s"
                )
                return embedding
            else:
                logger.warning(f"No embedding returned from {url}")

        except requests.exceptions.Timeout as e:
            last_error = e
            logger.warning(f"Timeout from {url}: {e}")
        except requests.exceptions.ConnectionError as e:
            last_error = e
            logger.warning(f"Connection error to {url}: {e}")
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(f"Request failed to {url}: {e}")
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error with {url}: {e}")

    total_time = time.time() - start_time
    logger.error(f"Failed to get embedding from all instances. Total time: {total_time:.2f}s")
    raise RuntimeError(f"Failed to get embedding from all available Ollama instances. Last error: {last_error}")


def get_db_connection():
    """Get database connection using centralized config."""
    return psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
    )


def remove_existing_document(conn, file_hash: str, file_name: str = "") -> Optional[int]:
    """
    Remove existing document by hash and all its related data before importing new version.
    Returns the document_id if it existed, None otherwise.
    """
    logger.info(f"Checking for existing document to remove: {file_name} (hash: {file_hash[:8]}...)")

    try:
        with conn.cursor() as cur:
            # First check if document exists by hash
            cur.execute("SELECT id, file_name FROM documents WHERE file_hash = %s;", (file_hash,))
            result = cur.fetchone()

            if result:
                document_id, existing_filename = result

                # Count existing chunks before deletion
                cur.execute("SELECT COUNT(*) FROM document_chunks WHERE document_id = %s;", (document_id,))
                count_result = cur.fetchone()
                chunk_count = count_result[0] if count_result else 0

                logger.info(
                    f"Found existing document '{existing_filename}' (ID: {document_id}) with {chunk_count} chunks - removing for reimport"
                )

                # Delete document (CASCADE will remove all related data)
                cur.execute("DELETE FROM documents WHERE id = %s;", (document_id,))
                deleted_rows = cur.rowcount

                if deleted_rows > 0:
                    logger.info(f"Successfully removed existing document '{existing_filename}' and {chunk_count} chunks")
                    return document_id
                else:
                    logger.warning(f"No rows deleted for document '{existing_filename}'")

            else:
                logger.debug(f"No existing document found for hash {file_hash[:8]}... - this is a new import")

        return None

    except Exception as e:
        logger.error(f"Failed to remove existing document with hash {file_hash[:8]}...: {e}")
        raise


def insert_document_comprehensive(
    conn,
    file_path: str,
    privacy_level: str,
    classification: Dict[str, Any],
    extracted_metadata: Dict[str, Any]
) -> int:
    """
    Insert comprehensive document record with full metadata using new pgvector schema.

    Args:
        conn: Database connection
        file_path: Full path to the document file
        privacy_level: 'public' or 'private' classification
        classification: AI classification results dictionary
        extracted_metadata: Document metadata from pattern extraction

    Returns:
        int: Document ID

    Raises:
        Exception: If document insertion fails
    """
    file_name = os.path.basename(file_path)
    file_hash = calculate_file_hash(file_path)
    file_size = os.path.getsize(file_path)

    logger.info(f"Creating comprehensive document record: {file_name}")
    logger.info(f"  Privacy: {privacy_level}")
    logger.info(f"  Type: {classification.get('document_type', 'unknown')}")
    logger.info(f"  Product: {classification.get('product_name', 'unknown')} {classification.get('product_version', 'unknown')}")
    logger.info(f"  Confidence: {classification.get('confidence', 0.0):.2f}")

    try:
        with conn.cursor() as cur:
            # Check if document already exists by hash
            cur.execute("SELECT id FROM documents WHERE file_hash = %s;", (file_hash,))
            result = cur.fetchone()

            if result:
                document_id = result[0]
                logger.info(f"Document with hash {file_hash[:8]}... already exists (ID: {document_id})")
                return document_id

            # Prepare comprehensive document data
            document_data = {
                'file_name': file_name,
                'original_path': file_path,
                'file_hash': file_hash,
                'file_size': file_size,
                'mime_type': 'application/pdf',
                'title': extracted_metadata.get('title'),
                'version': extracted_metadata.get('version') or classification.get('product_version'),
                'doc_number': extracted_metadata.get('doc_number'),
                'ga_date': extracted_metadata.get('ga_date'),
                'publisher': extracted_metadata.get('publisher'),
                'copyright_year': extracted_metadata.get('copyright_year'),
                'product_family': extracted_metadata.get('product_family', []),
                'product_name': classification.get('product_name', 'unknown'),
                'product_version': classification.get('product_version', 'unknown'),
                'document_type': classification.get('document_type', 'unknown'),
                'document_category': classification.get('document_category', 'documentation'),
                'service_lines': extracted_metadata.get('service_lines', []),
                'audiences': extracted_metadata.get('audiences', []),
                'privacy_level': privacy_level,
                'classification_confidence': classification.get('confidence', 0.0),
                'classification_method': classification.get('metadata', {}).get('classification_method', 'ai'),
                'processing_status': 'processing',
                'metadata': {
                    **classification.get('metadata', {}),
                    **extracted_metadata,
                    'extraction_timestamp': datetime.now().isoformat(),
                    'embedding_model': settings.embedding_model
                }
            }

            # Create new comprehensive document record
            cur.execute("""
                INSERT INTO documents (
                    file_name, original_path, file_hash, file_size, mime_type,
                    title, version, doc_number, ga_date, publisher, copyright_year,
                    product_family, product_name, product_version,
                    document_type, document_category, service_lines, audiences,
                    privacy_level, classification_confidence, classification_method,
                    processing_status, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                document_data['file_name'], document_data['original_path'],
                document_data['file_hash'], document_data['file_size'], document_data['mime_type'],
                document_data['title'], document_data['version'], document_data['doc_number'],
                document_data['ga_date'], document_data['publisher'], document_data['copyright_year'],
                document_data['product_family'], document_data['product_name'], document_data['product_version'],
                document_data['document_type'], document_data['document_category'],
                document_data['service_lines'], document_data['audiences'],
                document_data['privacy_level'], document_data['classification_confidence'],
                document_data['classification_method'], document_data['processing_status'],
                json.dumps(document_data['metadata'])
            ))

            result = cur.fetchone()
            document_id = result[0] if result else None
            if not document_id:
                raise Exception("Failed to get document_id after insertion")

            logger.info(f"Created comprehensive document with ID: {document_id}")
            logger.info(f"  Metadata fields populated: {len([k for k, v in document_data.items() if v])}")

            # Explicitly commit the transaction to ensure persistence
            conn.commit()
            logger.debug(f"Transaction committed for document {file_name}")

            return document_id

    except Exception as e:
        logger.error(f"Failed to insert comprehensive document '{file_name}': {e}")
        try:
            conn.rollback()
            logger.warning(f"Transaction rolled back for document '{file_name}'")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback transaction: {rollback_error}")
        raise


def insert_document_chunks_comprehensive(
    conn,
    chunks: List[Dict[str, Any]],
    document_id: int
) -> None:
    """
    Insert document chunks with enhanced metadata using new pgvector schema.

    Args:
        conn: Database connection
        chunks: List of chunk dictionaries from semantic chunking
        document_id: Document ID from documents table

    Raises:
        Exception: If chunk insertion fails
    """
    logger.info(f"Inserting {len(chunks)} chunks for document ID {document_id}")

    try:
        with conn.cursor() as cur:
            batch_data = []
            successful_chunks = 0

            for i, chunk in enumerate(chunks):
                try:
                    # Get required chunk fields
                    chunk_content = chunk.get('content', '')
                    content_hash = chunk.get('content_hash', hashlib.sha256(chunk_content.encode()).hexdigest()[:16])
                    chunk_index = chunk.get('chunk_index', i)
                    page_number = chunk.get('page_number', 1)
                    section_title = chunk.get('section_title')
                    chunk_type = chunk.get('chunk_type', 'text')

                    # Generate embedding for this chunk
                    chunk_embedding = get_embedding(chunk_content)
                    if not chunk_embedding:
                        logger.warning(f"Failed to generate embedding for chunk {i}, skipping")
                        continue

                    # Calculate content metrics
                    content_length = len(chunk_content)

                    # Prepare chunk metadata
                    chunk_metadata = {
                        **chunk.get('metadata', {}),
                        'content_length': content_length,
                        'embedding_model': settings.embedding_model,
                        'chunk_created_at': datetime.now().isoformat()
                    }

                    batch_data.append((
                        document_id,
                        chunk_index,
                        page_number,
                        section_title,
                        chunk_type,
                        chunk_content,
                        content_hash,
                        content_length,
                        chunk_embedding,
                        'en',  # Default language
                        len(chunk_content.split()),  # Token count approximation
                        json.dumps(chunk_metadata)
                    ))
                    successful_chunks += 1

                except Exception as e:
                    logger.error(f"Error processing chunk {i}: {e}")
                    continue

            if batch_data:
                # Batch insert for performance
                cur.executemany("""
                    INSERT INTO document_chunks (
                        document_id, chunk_index, page_number, section_title, chunk_type,
                        content, content_hash, content_length, embedding,
                        language, tokens, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, batch_data)

                logger.info(f"Successfully inserted {successful_chunks}/{len(chunks)} chunks")

                # Update document processing status
                cur.execute("""
                    UPDATE documents
                    SET processing_status = 'completed', processed_at = NOW()
                    WHERE id = %s;
                """, (document_id,))

                # Explicitly commit the transaction
                conn.commit()
                logger.debug(f"Chunks transaction committed for document {document_id}")
            else:
                logger.error("No valid chunks to insert")
                raise Exception("No valid chunks processed")

    except Exception as e:
        logger.error(f"Failed to insert chunks for document {document_id}: {e}")
        try:
            conn.rollback()
            logger.warning(f"Chunks transaction rolled back for document {document_id}")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback chunks transaction: {rollback_error}")
        raise


# Legacy functions for backward compatibility
def insert_document_with_categorization(conn, document_name: str, privacy_level: str, classification: Dict[str, Any]) -> int:
    """Legacy wrapper for comprehensive document insertion."""
    logger.warning("Using legacy insert_document_with_categorization - consider updating to insert_document_comprehensive")

    # Create minimal extracted metadata for compatibility
    extracted_metadata = {
        'title': None,
        'version': None,
        'doc_number': None,
        'ga_date': None,
        'publisher': None,
        'copyright_year': None,
        'product_family': [],
        'service_lines': [],
        'audiences': []
    }

    # Use document name as file path for legacy calls
    return insert_document_comprehensive(conn, document_name, privacy_level, classification, extracted_metadata)


def insert_document_chunks_with_categorization(
    conn,
    chunks: List[Dict[str, Any]],
    document_id: int,
    privacy_level: str,
    classification: Dict[str, Any],
    embedding_model: str
) -> None:
    """Legacy wrapper for comprehensive chunk insertion."""
    logger.warning("Using legacy insert_document_chunks_with_categorization - consider updating to insert_document_chunks_comprehensive")

    # Convert legacy chunk format to new format
    converted_chunks = []
    for i, chunk in enumerate(chunks):
        converted_chunk = {
            'content': chunk.get('text', ''),
            'chunk_index': chunk.get('chunk_index', i),
            'page_number': chunk.get('page_number', 1),
            'section_title': None,
            'chunk_type': chunk.get('metadata', {}).get('type', 'text'),
            'metadata': chunk.get('metadata', {})
        }
        converted_chunks.append(converted_chunk)

    return insert_document_chunks_comprehensive(conn, converted_chunks, document_id)


def insert_document_chunks_with_privacy(conn, document_name: str, privacy_level: str) -> int:
    """
    Insert or update document record with privacy classification.

    Args:
        conn: Database connection
        document_name: Name of the document file
        privacy_level: 'public' or 'private' classification

    Returns:
        int: Document ID

    Raises:
        Exception: If document insertion fails
    """
    logger.info(f"Creating document record: {document_name} (Privacy: {privacy_level})")

    try:
        with conn.cursor() as cur:
            # Check if document already exists from current session
            cur.execute("SELECT id FROM documents WHERE file_name = %s;", (document_name,))
            result = cur.fetchone()

            if result:
                document_id = result[0]
                # Update privacy level if document exists
                cur.execute(
                    "UPDATE documents SET privacy_level = %s WHERE id = %s;",
                    (privacy_level, document_id)
                )
                logger.info(f"Updated existing document ID {document_id} with privacy level: {privacy_level}")
            else:
                # Create minimal document record with privacy level (legacy support)
                file_hash = hashlib.sha256(document_name.encode()).hexdigest()
                cur.execute(
                    """
                    INSERT INTO documents (file_name, file_hash, privacy_level, processing_status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (document_name, file_hash, privacy_level, 'pending'),
                )
                result = cur.fetchone()
                document_id = result[0] if result else None
                if not document_id:
                    raise Exception("Failed to get document_id after insertion")
                logger.info(f"Created new document with ID: {document_id} (Privacy: {privacy_level})")

            return document_id

    except Exception as e:
        logger.error(f"Failed to insert/update document '{document_name}': {e}")
        raise


def insert_chunk_and_embedding(conn, chunk: Dict[str, Any], embedding: List[float], model_name: str, privacy_level: str = 'public'):
    """Insert chunk and embedding into unified schema with comprehensive logging."""
    start_time = time.time()
    document_name = chunk["metadata"]["document"]

    logger.info(f"Starting database insertion for document: {document_name}")
    logger.debug(
        f"Chunk details: index={chunk.get('chunk_index', 'unknown')}, text_length={len(chunk.get('text', ''))}, embedding_dims={len(embedding)}"
    )

    try:
        with conn.cursor() as cur:
            # Always create new document (old one should have been removed)
            document_name = chunk["metadata"]["document"]
            logger.debug(f"Creating document record: {document_name}")

            # Check if document was already created in this session
            cur.execute("SELECT id FROM documents WHERE file_name = %s;", (document_name,))
            result = cur.fetchone()

            if result:
                document_id = result[0]
                logger.debug(f"Using existing document ID from current session: {document_id}")
            else:
                # Create new document record (legacy format)
                file_hash = hashlib.sha256(document_name.encode()).hexdigest()
                cur.execute(
                    """
                    INSERT INTO documents (file_name, file_hash, privacy_level, processing_status)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """,
                    (document_name, file_hash, privacy_level, 'processing'),
                )
                result = cur.fetchone()
                document_id = result[0] if result else None
                if not document_id:
                    raise Exception("Failed to get document_id after insertion")
                logger.info(f"Created new document with ID: {document_id}")

            # Insert chunk with integrated embedding (unified schema)
            page_number = chunk.get("chunk_index", chunk.get("page_number", 0))
            chunk_type = chunk.get("metadata", {}).get("chunk_type", "text")
            content = chunk["text"]
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

            logger.debug(f"Inserting chunk: doc_id={document_id}, page={page_number}, type={chunk_type}")
            cur.execute(
                """
                INSERT INTO document_chunks (
                    document_id, chunk_index, page_number, chunk_type,
                    content, content_hash, content_length, embedding,
                    language, tokens, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """,
                (
                    document_id, page_number, page_number, chunk_type,
                    content, content_hash, len(content), embedding,
                    'en', len(content.split()),
                    json.dumps(chunk.get("metadata", {}))
                ),
            )

            result = cur.fetchone()
            chunk_id = result[0] if result else None
            if not chunk_id:
                raise Exception("Failed to get chunk_id after insertion")

            insertion_time = time.time() - start_time
            logger.info(
                f"Successfully inserted chunk {chunk_id} for document {document_id}. Time: {insertion_time:.3f}s"
            )

    except Exception as e:
        insertion_time = time.time() - start_time
        logger.error(f"Database insertion failed after {insertion_time:.3f}s: {e}")
        raise
