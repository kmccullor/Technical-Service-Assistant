#!/usr/bin/env python3
"""
Reprocess existing documents to extract acronyms and update ACRONYM_INDEX.md.
This script can be run independently to update acronyms from all processed documents.
"""

import os
import sys
import psycopg2
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from docling_processor.acronym_extractor import AcronymExtractor, load_existing_acronyms, save_acronyms_to_file
from utils.logging_config import setup_logging

def reprocess_documents_for_acronyms():
    """Reprocess all documents in the database to extract acronyms."""
    
    settings = get_settings()
    
    logger = setup_logging(
        program_name='acronym_reprocessor',
        log_level=getattr(settings, 'log_level', 'INFO'),
        log_file=f'/app/logs/acronym_reprocessor_{datetime.now().strftime("%Y%m%d")}.log',
        console_output=True
    )
    
    logger.info("Starting acronym reprocessing for all documents")
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port,
        )
        cur = conn.cursor()
        
        # Get all documents with their chunks
        cur.execute("""
            SELECT DISTINCT d.file_name, string_agg(c.content, ' ') as full_text
            FROM documents d 
            JOIN document_chunks c ON d.id = c.document_id 
            WHERE d.file_name LIKE '%.pdf' 
            GROUP BY d.file_name
            ORDER BY d.file_name
        """)
        
        documents = cur.fetchall()
        logger.info(f"Found {len(documents)} documents to process for acronyms")
        
        # Initialize acronym extractor
        extractor = AcronymExtractor()
        all_acronyms = {}
        source_docs = set()
        
        # Load existing acronyms
        acronym_file_path = os.path.join(settings.uploads_dir, "ACRONYM_INDEX.md")
        existing_acronyms = load_existing_acronyms(acronym_file_path)
        logger.info(f"Loaded {len(existing_acronyms)} existing acronyms")
        
        # Process each document
        for doc_name, full_text in documents:
            if not full_text:
                continue
                
            try:
                # Extract acronyms from document
                doc_acronyms = extractor.extract_from_text(full_text, doc_name)
                
                if doc_acronyms:
                    logger.info(f"Extracted {len(doc_acronyms)} acronyms from {doc_name}")
                    source_docs.add(doc_name)
                    
                    # Merge with existing
                    all_acronyms = extractor.merge_acronyms(all_acronyms, doc_acronyms)
                    
            except Exception as e:
                logger.error(f"Failed to extract acronyms from {doc_name}: {e}")
        
        # Merge with existing acronyms
        final_acronyms = extractor.merge_acronyms(existing_acronyms, all_acronyms)
        
        # Save updated acronyms
        if final_acronyms:
            save_acronyms_to_file(final_acronyms, acronym_file_path, source_docs)
            logger.info(f"Updated ACRONYM_INDEX.md with {len(final_acronyms)} total acronyms from {len(source_docs)} documents")
            
            # Log some examples
            logger.info("Sample extracted acronyms:")
            for i, (acronym, definition) in enumerate(sorted(final_acronyms.items())[:10]):
                logger.info(f"  {acronym}: {definition}")
                
        else:
            logger.warning("No acronyms extracted from any documents")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Acronym reprocessing failed: {e}")
        return False
    
    logger.info("Acronym reprocessing completed successfully")
    return True


if __name__ == "__main__":
    success = reprocess_documents_for_acronyms()
    sys.exit(0 if success else 1)