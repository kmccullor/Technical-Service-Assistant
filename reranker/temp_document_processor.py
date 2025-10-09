import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import uuid

import fitz  # PyMuPDF for PDF processing
from PIL import Image
import pytesseract
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

@dataclass
class TempDocument:
    session_id: str
    file_name: str
    content: str
    file_type: str
    upload_time: datetime
    chunks: List[str]
    embeddings: Optional[List[List[float]]] = None

class TempDocumentProcessor:
    """
    Processes temporarily uploaded documents for immediate analysis.
    Documents are not stored permanently and are cleaned up after session expires.
    """
    
    def __init__(self):
        self.sessions: Dict[str, TempDocument] = {}
        self.session_timeout = timedelta(hours=2)  # 2-hour session timeout
        
    def process_file(self, file_path: str, file_name: str, session_id: str) -> TempDocument:
        """Process uploaded file and extract text content."""
        try:
            file_extension = os.path.splitext(file_name)[1].lower()
            
            if file_extension == '.pdf':
                content = self._extract_pdf_content(file_path)
            elif file_extension in ['.txt', '.log', '.sql', '.conf', '.config', '.ini', '.properties', '.out', '.err', '.trace']:
                content = self._extract_text_content(file_path)
            elif file_extension in ['.json']:
                content = self._extract_json_content(file_path)
            elif file_extension in ['.csv']:
                content = self._extract_csv_content(file_path)
            elif file_extension in ['.xml']:
                content = self._extract_xml_content(file_path)
            elif file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp']:
                content = self._extract_image_content(file_path, file_name)
            else:
                # Fallback to text extraction
                content = self._extract_text_content(file_path)
            
            # Create chunks for better analysis
            chunks = self._create_chunks(content)
            
            temp_doc = TempDocument(
                session_id=session_id,
                file_name=file_name,
                content=content,
                file_type=file_extension,
                upload_time=datetime.now(),
                chunks=chunks
            )
            
            # Store in session
            self.sessions[session_id] = temp_doc
            
            logger.info(f"Processed temporary document: {file_name} ({len(content)} chars, {len(chunks)} chunks)")
            return temp_doc
            
        except Exception as e:
            logger.error(f"Failed to process file {file_name}: {e}")
            raise
    
    def _extract_pdf_content(self, file_path: str) -> str:
        """Extract text from PDF files."""
        content = []
        try:
            doc = fitz.open(file_path)
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    content.append(f"Page {page_num + 1}:\\n{text}")
            doc.close()
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise
        
        return "\\n\\n".join(content)
    
    def _extract_text_content(self, file_path: str) -> str:
        """Extract content from text-based files."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception:
                raise e
    
    def _extract_json_content(self, file_path: str) -> str:
        """Extract and format JSON content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Pretty print JSON for better readability
                formatted = json.dumps(data, indent=2, ensure_ascii=False)
                return f"JSON Content:\\n{formatted}"
        except Exception as e:
            logger.error(f"JSON extraction failed: {e}")
            # Fallback to text extraction
            return self._extract_text_content(file_path)
    
    def _extract_csv_content(self, file_path: str) -> str:
        """Extract CSV content with basic formatting."""
        try:
            import csv
            content = []
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.reader(f)
                for i, row in enumerate(csv_reader):
                    if i == 0:
                        content.append("CSV Headers: " + " | ".join(row))
                    elif i < 100:  # Limit to first 100 rows for analysis
                        content.append(" | ".join(row))
                    elif i == 100:
                        content.append("... (truncated after 100 rows)")
                        break
                        
            return "\\n".join(content)
        except Exception as e:
            logger.error(f"CSV extraction failed: {e}")
            return self._extract_text_content(file_path)
    
    def _extract_xml_content(self, file_path: str) -> str:
        """Extract XML content with basic formatting."""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            def xml_to_text(element, level=0):
                indent = "  " * level
                text_parts = []
                if element.text and element.text.strip():
                    text_parts.append(f"{indent}{element.tag}: {element.text.strip()}")
                else:
                    text_parts.append(f"{indent}{element.tag}")
                
                for child in element:
                    text_parts.extend(xml_to_text(child, level + 1))
                
                return text_parts
            
            formatted = xml_to_text(root)
            return "\\n".join(formatted)
            
        except Exception as e:
            logger.error(f"XML extraction failed: {e}")
            return self._extract_text_content(file_path)
    
    def _extract_image_content(self, file_path: str, file_name: str) -> str:
        """Extract text from images using OCR and describe image content."""
        try:
            # Load image
            image = Image.open(file_path)
            
            # Basic image information
            width, height = image.size
            mode = image.mode
            format_name = image.format or "Unknown"
            
            content_parts = [
                f"Image Analysis Report for: {file_name}",
                f"Dimensions: {width}x{height} pixels",
                f"Format: {format_name}",
                f"Color Mode: {mode}",
                ""
            ]
            
            # Try OCR text extraction
            try:
                ocr_text = pytesseract.image_to_string(image)
                if ocr_text.strip():
                    content_parts.extend([
                        "Extracted Text (OCR):",
                        "=" * 30,
                        ocr_text.strip(),
                        ""
                    ])
                else:
                    content_parts.append("No readable text found in image.")
            except Exception as ocr_error:
                logger.warning(f"OCR extraction failed for {file_name}: {ocr_error}")
                content_parts.append("OCR text extraction unavailable - image content analysis only.")
            
            # Add technical context for troubleshooting images
            content_parts.extend([
                "",
                "Technical Analysis Context:",
                "=" * 30,
                "This appears to be an image file that may contain:",
                "- Screenshots of system interfaces or error messages",
                "- Diagrams of network topology or system architecture", 
                "- Photos of physical equipment or hardware components",
                "- Graphs or charts showing system metrics or performance data",
                "- Configuration screens or status displays",
                "",
                "If this image contains error messages, system screenshots, or technical diagrams,",
                "please describe what you're seeing or ask specific questions about the content."
            ])
            
            return "\\n".join(content_parts)
            
        except Exception as e:
            logger.error(f"Image extraction failed for {file_name}: {e}")
            # Fallback to basic file info
            return f"Image file uploaded: {file_name}\\nUnable to process image content. Please describe what the image shows or ask specific questions about it."
    
    def _create_chunks(self, content: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Create overlapping chunks from content for better analysis."""
        if not content:
            return []
        
        chunks = []
        words = content.split()
        
        if len(words) <= chunk_size:
            return [content]
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            chunks.append(chunk_text)
            
            if i + chunk_size >= len(words):
                break
        
        return chunks
    
    def generate_embeddings(self, session_id: str) -> bool:
        """Generate embeddings for temporary document chunks."""
        if session_id not in self.sessions:
            return False
        
        try:
            from app import ollama_client  # Import from main app
            temp_doc = self.sessions[session_id]
            
            embeddings = []
            for chunk in temp_doc.chunks:
                if chunk.strip():
                    embedding_response = ollama_client.embeddings(
                        model=settings.embedding_model.split(":")[0], 
                        prompt=chunk
                    )
                    embeddings.append(embedding_response["embedding"])
            
            temp_doc.embeddings = embeddings
            logger.info(f"Generated {len(embeddings)} embeddings for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings for session {session_id}: {e}")
            return False
    
    def search_temp_documents(self, query: str, session_id: str, limit: int = 5) -> List[Tuple[str, float]]:
        """Search temporary document chunks using embeddings."""
        if session_id not in self.sessions:
            return []
        
        temp_doc = self.sessions[session_id]
        if not temp_doc.embeddings:
            return []
        
        try:
            from app import ollama_client
            import numpy as np
            
            # Generate query embedding
            query_response = ollama_client.embeddings(
                model=settings.embedding_model.split(":")[0], 
                prompt=query
            )
            query_embedding = np.array(query_response["embedding"])
            
            # Calculate similarities
            similarities = []
            for i, chunk_embedding in enumerate(temp_doc.embeddings):
                chunk_emb = np.array(chunk_embedding)
                # Cosine similarity
                similarity = np.dot(query_embedding, chunk_emb) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb)
                )
                similarities.append((temp_doc.chunks[i], float(similarity)))
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:limit]
            
        except Exception as e:
            logger.error(f"Search failed for session {session_id}: {e}")
            return []
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get information about a temporary session."""
        if session_id not in self.sessions:
            return None
        
        temp_doc = self.sessions[session_id]
        return {
            "session_id": session_id,
            "file_name": temp_doc.file_name,
            "file_type": temp_doc.file_type,
            "upload_time": temp_doc.upload_time.isoformat(),
            "content_length": len(temp_doc.content),
            "chunk_count": len(temp_doc.chunks),
            "has_embeddings": temp_doc.embeddings is not None
        }
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        now = datetime.now()
        expired_sessions = [
            session_id for session_id, doc in self.sessions.items()
            if now - doc.upload_time > self.session_timeout
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up expired session: {session_id}")
        
        return len(expired_sessions)
    
    def cleanup_session(self, session_id: str) -> bool:
        """Manually clean up a specific session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Manually cleaned up session: {session_id}")
            return True
        return False

# Global instance
temp_processor = TempDocumentProcessor()