#!/usr/bin/env python3
"""Debug script to test document stats function."""

import asyncio
import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel
from typing import Dict, Optional

# Add current directory to path
sys.path.insert(0, '/home/kmccullor/Projects/Technical-Service-Assistant')

from config import get_settings

class DocumentStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    document_types: Dict[str, int]
    product_breakdown: Dict[str, int] 
    privacy_breakdown: Dict[str, int]
    avg_chunks_per_document: float
    last_processed: Optional[str]

def get_db_connection():
    """Get database connection."""
    settings = get_settings()
    return psycopg2.connect(
        host=settings.db_host,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        port=settings.db_port
    )

async def test_document_stats():
    """Test document stats function exactly as implemented in reranker."""
    try:
        print("Starting document stats test...")
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get basic counts - EXACT copy from reranker function
        print("Executing basic stats query...")
        cursor.execute("""
            SELECT 
                COUNT(*) as total_documents,
                MAX(processed_at) as last_processed
            FROM documents 
            WHERE processing_status = 'processed'
        """)
        basic_stats = cursor.fetchone()
        print(f"Basic stats result: {dict(basic_stats) if basic_stats else None}")
        
        # Get total chunks - EXACT copy from reranker function
        print("Executing chunk stats query...")
        cursor.execute("""
            SELECT COUNT(*) as total_chunks 
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id 
            WHERE d.processing_status = 'processed'
        """)
        chunk_stats = cursor.fetchone()
        print(f"Chunk stats result: {dict(chunk_stats) if chunk_stats else None}")
        
        # Get document type breakdown
        print("Executing document type query...")
        cursor.execute("""
            SELECT document_type, COUNT(*) as count 
            FROM documents 
            WHERE processing_status = 'processed' AND document_type IS NOT NULL
            GROUP BY document_type 
            ORDER BY count DESC
        """)
        type_breakdown = {row['document_type']: row['count'] for row in cursor.fetchall()}
        print(f"Type breakdown: {type_breakdown}")
        
        # Get product breakdown
        print("Executing product breakdown query...")
        cursor.execute("""
            SELECT product_name, COUNT(*) as count 
            FROM documents 
            WHERE processing_status = 'processed' AND product_name IS NOT NULL
            GROUP BY product_name 
            ORDER BY count DESC
        """)
        product_breakdown = {row['product_name']: row['count'] for row in cursor.fetchall()}
        print(f"Product breakdown: {product_breakdown}")
        
        # Get privacy breakdown
        print("Executing privacy breakdown query...")
        cursor.execute("""
            SELECT privacy_level, COUNT(*) as count 
            FROM documents 
            WHERE processing_status = 'processed'
            GROUP BY privacy_level 
            ORDER BY count DESC
        """)
        privacy_breakdown = {row['privacy_level']: row['count'] for row in cursor.fetchall()}
        print(f"Privacy breakdown: {privacy_breakdown}")
        
        cursor.close()
        conn.close()
        
        # Calculate results - EXACT copy from reranker function
        total_docs = basic_stats['total_documents'] if basic_stats else 0
        total_chunks = chunk_stats['total_chunks'] if chunk_stats else 0
        avg_chunks = total_chunks / max(total_docs, 1)
        
        last_processed = None
        if basic_stats and basic_stats['last_processed']:
            last_processed = basic_stats['last_processed'].isoformat()
        
        print(f"\nFinal calculated values:")
        print(f"total_docs: {total_docs}")
        print(f"total_chunks: {total_chunks}")
        print(f"avg_chunks: {avg_chunks}")
        print(f"last_processed: {last_processed}")
        
        result = DocumentStatsResponse(
            total_documents=total_docs,
            total_chunks=total_chunks,
            document_types=type_breakdown,
            product_breakdown=product_breakdown,
            privacy_breakdown=privacy_breakdown,
            avg_chunks_per_document=round(avg_chunks, 1),
            last_processed=last_processed
        )
        
        print(f"\nFinal result: {result.model_dump()}")
        return result
        
    except Exception as e:
        print(f"Error in test function: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_document_stats())