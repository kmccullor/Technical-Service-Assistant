import json
import hashlib
import os
import random
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import Counter
from datetime import datetime

import psycopg2
import requests

from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="pdf_processor_utils",
    log_level="INFO",
    console_output=True,
)

sys.path.append("/app")
from typing import Any, Dict, List, Optional, Tuple

from config import get_settings

# Get settings instance
settings = get_settings()


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


def classify_document_with_ai(text: str, filename: str = "") -> Dict[str, Any]:
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
    from config import get_settings
    settings = get_settings()
    
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
    # Pattern: Product 1.2.3 Document Type.pdf or RNI 4.16 Document Type.pdf
    product_match = re.search(r'\b(product|rni|flexnet|esm|multispeak|ppa)\s+(\d+\.\d+(?:\.\d+)?)\b', filename_lower)
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
    
    logger.info(f"Fallback classification: {result['document_type']} for {result['product_name']} {result['product_version']}")
    return result


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


def perform_image_ocr(image_paths: List[str]) -> List[Dict[str, Any]]:
    """Run OCR over extracted images and return list of OCR chunk dicts with basic noise filtering.

    Enhancements (Option A):
      * Derive page_number from filename pattern `<doc>_page{N}_img{M}.<ext>` when available.
      * Apply line-level noise filtering (symbol-heavy or low alphanumeric density lines removed).
      * Discard overall OCR blocks that become too small (< 8 chars) after cleaning.

    Returns list of dicts:
      { 'text': str, 'metadata': {...}, 'page_number': int, 'chunk_type': 'image_ocr' }
    """
    ocr_chunks: List[Dict[str, Any]] = []
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as e:  # pragma: no cover - dependency import issues
        logger.warning(f"OCR dependencies not available, skipping OCR: {e}")
        return ocr_chunks

    page_pattern = re.compile(r"_page(\d+)_img", re.IGNORECASE)

    def _clean_ocr(text: str) -> str:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        cleaned_lines: List[str] = []
        for line in lines:
            # Drop lines that are just repeated symbols
            if re.fullmatch(r"[+\-=_]{4,}", line):
                continue
            # Compute alphanumeric density
            alnum = sum(ch.isalnum() for ch in line)
            if len(line) > 30:
                ratio = alnum / max(len(line), 1)
                if ratio < 0.25:  # Mostly noise/symbols
                    continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    for idx, img_path in enumerate(image_paths):
        try:
            with Image.open(img_path) as im:
                raw_txt = pytesseract.image_to_string(im)
            if not raw_txt:
                continue
            cleaned = _clean_ocr(raw_txt)
            if len(cleaned) < 8:  # ignore very small / noise blocks
                continue
            # Derive page number if possible
            page_number = 0
            m = page_pattern.search(os.path.basename(img_path))
            if m:
                try:
                    page_number = int(m.group(1))
                except ValueError:
                    page_number = 0
            ocr_chunks.append({
                'text': cleaned,
                'metadata': {
                    'type': 'image_ocr',
                    'source_image': img_path,
                    'ocr_engine': 'tesseract',
                    'raw_length': len(raw_txt),
                    'clean_length': len(cleaned)
                },
                'page_number': page_number,
                'chunk_type': 'image_ocr'
            })
        except Exception as e:
            logger.warning(f"OCR failed for image {img_path}: {e}")
            continue
    if ocr_chunks:
        logger.info(f"Generated {len(ocr_chunks)} OCR chunks from images (after noise filtering)")
    return ocr_chunks


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


def remove_existing_document(conn, document_name: str) -> Optional[int]:
    """
    Remove existing document and all its chunks before importing new version.
    Returns the document_id if it existed, None otherwise.
    """
    logger.info(f"Checking for existing document to remove: {document_name}")

    try:
        with conn.cursor() as cur:
            # First check if document exists
            cur.execute("SELECT id FROM documents WHERE file_name = %s;", (document_name,))
            result = cur.fetchone()

            if result:
                document_id = result[0]

                # Count existing chunks before deletion
                cur.execute("SELECT COUNT(*) FROM document_chunks WHERE document_id = %s;", (document_id,))
                count_result = cur.fetchone()
                chunk_count = count_result[0] if count_result else 0

                logger.info(
                    f"Found existing document '{document_name}' (ID: {document_id}) with {chunk_count} chunks - removing for reimport"
                )

                # Delete document (CASCADE will remove all related chunks)
                cur.execute("DELETE FROM documents WHERE id = %s;", (document_id,))
                deleted_rows = cur.rowcount

                if deleted_rows > 0:
                    logger.info(f"Successfully removed existing document '{document_name}' and {chunk_count} chunks")
                    return document_id
                else:
                    logger.warning(f"No rows deleted for document '{document_name}'")

            else:
                logger.debug(f"No existing document found for '{document_name}' - this is a new import")

        return None

    except Exception as e:
        logger.error(f"Failed to remove existing document '{document_name}': {e}")
        raise


def insert_document_with_categorization(conn, document_name: str, privacy_level: str, classification: Dict[str, Any]) -> int:
    """
    Insert or update document record with privacy classification and AI categorization.
    
    Args:
        conn: Database connection
        document_name: Name of the document file
        privacy_level: 'public' or 'private' classification
        classification: AI classification results dictionary
        
    Returns:
        int: Document ID
        
    Raises:
        Exception: If document insertion fails
    """
    logger.info(f"Creating document record: {document_name}")
    logger.info(f"  Privacy: {privacy_level}")
    logger.info(f"  Type: {classification.get('document_type', 'unknown')}")
    logger.info(f"  Product: {classification.get('product_name', 'unknown')} {classification.get('product_version', 'unknown')}")
    logger.info(f"  Confidence: {classification.get('confidence', 0.0):.2f}")
    
    try:
        with conn.cursor() as cur:
            # Check if document already exists from current session
            cur.execute("SELECT id FROM documents WHERE file_name = %s;", (document_name,))
            result = cur.fetchone()
            
            if result:
                document_id = result[0]
                # Update with new classification data
                cur.execute("""
                    UPDATE documents SET 
                        privacy_level = %s,
                        document_type = %s,
                        product_name = %s,
                        product_version = %s,
                        metadata = metadata || %s::jsonb,
                        updated_at = now(),
                        processing_status = 'processed',
                        processed_at = now()
                    WHERE id = %s;
                """, (
                    privacy_level,
                    classification.get('document_type', 'unknown'),
                    classification.get('product_name', 'unknown'),
                    classification.get('product_version', 'unknown'),
                    classification.get('document_category', 'documentation'),
                    classification.get('confidence', 0.0),
                    json.dumps(classification.get('metadata', {})),
                    document_id
                ))
                logger.info(f"Updated existing document ID {document_id} with AI classification")
            else:
                # Create new document record with full classification
                cur.execute("""
                    INSERT INTO documents (
                        file_name, file_hash, file_size, mime_type, privacy_level, document_type, product_name, 
                        product_version, metadata, processing_status, processed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'processed', now())
                    RETURNING id;
                """, (
                    document_name,
                    classification.get('file_hash', document_name),
                    classification.get('file_size'),
                    classification.get('mime_type'),
                    privacy_level,
                    classification.get('document_type', 'unknown'),
                    classification.get('product_name', 'unknown'),
                    classification.get('product_version', 'unknown'),
                    json.dumps(classification.get('metadata', {})),
                ))
                result = cur.fetchone()
                document_id = result[0] if result else None
                if not document_id:
                    raise Exception("Failed to get document_id after insertion")
                logger.info(f"Created new document with ID: {document_id}")
                logger.info(f"  Full classification applied successfully")
            
            # Explicitly commit the transaction to ensure persistence
            conn.commit()
            logger.debug(f"Transaction committed for document {document_name}")
            
            return document_id
            
    except Exception as e:
        logger.error(f"Failed to insert/update document '{document_name}': {e}")
        try:
            conn.rollback()
            logger.warning(f"Transaction rolled back for document '{document_name}'")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback transaction: {rollback_error}")
        raise


def insert_document_chunks_with_categorization(
    conn,
    chunks: List[Dict[str, Any]],
    document_id: int,
    privacy_level: str,
    classification: Dict[str, Any],
    embedding_model: str
) -> Dict[str, Any]:
    """
    Insert document chunks with enhanced categorization metadata.
    
    Args:
        conn: Database connection
        chunks: List of chunk dictionaries with 'text', 'metadata', etc.
    document_id: Document ID from documents table
        privacy_level: Privacy classification ('public' or 'private')
        classification: AI classification results dictionary
        embedding_model: Name of the embedding model used
        
    Raises:
        Exception: If chunk insertion fails
    """
    start_time = time.time()
    metrics: Dict[str, Any] = {
        'document_id': document_id,
        'total_input_chunks': len(chunks),
        'inserted_chunks': 0,
        'skipped_duplicates': 0,
        'failed_embeddings': 0,
        'by_type': {},
        'elapsed_seconds': None
    }
    try:
        with conn.cursor() as cur:
            batch_data = []
            seen_hashes: Set[str] = set()
            type_counter: Counter = Counter()
            for i, chunk in enumerate(chunks):
                chunk_text = chunk.get('text', '')
                if not chunk_text.strip():
                    continue
                page_number = chunk.get('page_number', 1)
                chunk_type = chunk.get('chunk_type', chunk.get('metadata', {}).get('type', 'text'))
                try:
                    chunk_embedding = get_embedding(chunk_text)
                    if not chunk_embedding:
                        metrics['failed_embeddings'] += 1
                        continue
                except Exception as e:
                    logger.error(f"Error generating embedding for chunk {i}: {e}")
                    metrics['failed_embeddings'] += 1
                    continue
                content_hash = hashlib.md5(chunk_text.encode()).hexdigest()
                if content_hash in seen_hashes:
                    metrics['skipped_duplicates'] += 1
                    continue
                seen_hashes.add(content_hash)
                batch_data.append((
                    document_id,
                    i,
                    page_number,
                    chunk_type,
                    chunk_text,
                    content_hash,
                    chunk_embedding,
                    privacy_level,
                    classification.get('document_type', 'unknown'),
                    classification.get('product_name', 'unknown')
                ))
                type_counter[chunk_type] += 1
            if batch_data:
                cur.executemany(
                    """
                    INSERT INTO document_chunks (
                        document_id, chunk_index, page_number, chunk_type, content, content_hash, embedding, privacy_level, document_type, product_name
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id, content_hash) DO NOTHING;
                    """,
                    batch_data,
                )
            metrics['inserted_chunks'] = len(batch_data)
            metrics['by_type'] = dict(type_counter)
            conn.commit()
            metrics['elapsed_seconds'] = round(time.time() - start_time, 3)
            logger.info(
                f"Inserted {metrics['inserted_chunks']} chunks (skipped dup={metrics['skipped_duplicates']}, failed_embed={metrics['failed_embeddings']})"
            )
            if type_counter:
                logger.info(f"Chunk type distribution: {dict(type_counter)}")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Failed to insert chunks with categorization: {e}")
        raise
    return metrics


def insert_ingestion_metrics(
    conn,
    document_id: int,
    file_name: str,
    file_size_bytes: Optional[int],
    page_count: Optional[int],
    processing_start_time: datetime,
    processing_end_time: datetime,
    metrics: Dict[str, Any],
    embedding_model: str
) -> None:
    """
    Insert document ingestion metrics into the metrics table for monitoring and analysis.
    
    Args:
        conn: Database connection
        document_id: ID of the processed document
        file_name: Name of the processed file
        file_size_bytes: Size of the original file
        page_count: Number of pages in the document
        processing_start_time: When processing began
        processing_end_time: When processing completed
        metrics: Processing metrics dictionary from insert_document_chunks_with_categorization
        embedding_model: Name of the embedding model used
    """
    try:
        with conn.cursor() as cur:
            # Calculate derived metrics
            by_type = metrics.get('by_type', {})
            text_chunks = by_type.get('text', 0)
            table_chunks = by_type.get('table', 0)
            image_chunks = by_type.get('image', 0)
            ocr_chunks = by_type.get('image_ocr', 0)
            
            duration = (processing_end_time - processing_start_time).total_seconds()
            
            # Calculate ratios
            ocr_yield_ratio = (ocr_chunks / image_chunks) if image_chunks > 0 else None
            success_rate = (metrics.get('inserted_chunks', 0) / metrics.get('total_input_chunks', 1))
            
            # Estimate embedding performance
            embedding_time = metrics.get('elapsed_seconds', 0)
            avg_embedding_time_ms = None
            if embedding_time and metrics.get('inserted_chunks', 0) > 0:
                avg_embedding_time_ms = (embedding_time * 1000) / metrics.get('inserted_chunks', 1)
            
            cur.execute(
                """
                INSERT INTO document_ingestion_metrics (
                    document_id, file_name, processing_start_time, processing_end_time,
                    processing_duration_seconds, total_input_chunks, file_size_bytes, page_count,
                    text_chunks, table_chunks, image_chunks, ocr_chunks,
                    inserted_chunks, failed_chunks, skipped_duplicates, failed_embeddings,
                    embedding_time_seconds, avg_embedding_time_ms,
                    ocr_yield_ratio, success_rate, embedding_model
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    document_id, file_name, processing_start_time, processing_end_time,
                    duration, metrics.get('total_input_chunks', 0), file_size_bytes, page_count,
                    text_chunks, table_chunks, image_chunks, ocr_chunks,
                    metrics.get('inserted_chunks', 0), metrics.get('failed_embeddings', 0),
                    metrics.get('skipped_duplicates', 0), metrics.get('failed_embeddings', 0),
                    embedding_time, avg_embedding_time_ms,
                    ocr_yield_ratio, success_rate, embedding_model
                )
            )
            
            conn.commit()
            # Safely format optional ocr_yield_ratio (cannot embed conditional with format specifier inside single f-string expression)
            if ocr_yield_ratio is not None:
                ocr_yield_str = f"{ocr_yield_ratio:.3f}"
            else:
                ocr_yield_str = "N/A"
            logger.info(
                f"Stored ingestion metrics for {file_name}: duration={duration:.2f}s, "
                f"success_rate={success_rate:.3f}, ocr_yield={ocr_yield_str}"
            )
    except Exception as e:
        logger.error(f"Failed to insert ingestion metrics for {file_name}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass

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
                    "UPDATE documents SET privacy_level = %s, updated_at = now() WHERE id = %s;",
                    (privacy_level, document_id)
                )
                logger.info(f"Updated existing document ID {document_id} with privacy level: {privacy_level}")
            else:
                # Create new document record with privacy level
                cur.execute(
                    """
                    INSERT INTO documents (file_name, file_hash, privacy_level, processing_status)
                    VALUES (%s, %s)
                    RETURNING id;
                    """,
                    (document_name, privacy_level),
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
                # Create new document record
                cur.execute(
                    """
                    INSERT INTO documents (file_name, file_hash, processing_status)
                    VALUES (%s)
                    RETURNING id;
                """,
                    (document_name,),
                )
                result = cur.fetchone()
                document_id = result[0] if result else None
                if not document_id:
                    raise Exception("Failed to get document_id after insertion")
                logger.info(f"Created new document with ID: {document_id}")

            # Insert chunk with integrated embedding (unified schema)
            chunk_index = chunk.get("chunk_index", 0)
            page_number = chunk.get("page_number", 0)
            chunk_type = chunk.get("metadata", {}).get("chunk_type", "text")
            content = chunk["text"]
            
            # Generate content hash
            import hashlib
            content_hash = hashlib.md5(content.encode()).hexdigest()

            logger.debug(f"Inserting chunk: doc_id={document_id}, chunk_index={chunk_index}, page={page_number}, type={chunk_type}")
            cur.execute(
                """
                INSERT INTO document_chunks (document_id, chunk_index, page_number, chunk_type, content, content_hash, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """,
                (document_id, chunk_index, page_number, chunk_type, content, content_hash, embedding),
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
