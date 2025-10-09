from datetime import datetime

from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name="semantic_chunking",
    log_level="INFO",
    console_output=True,
)

#!/usr/bin/env python3
"""
Semantic Chunking Implementation

Advanced chunking strategies that preserve document structure and context
for improved retrieval accuracy in technical documents.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.tokenize import sent_tokenize

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("NLTK not available, using basic tokenization")


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""

    document_name: str
    chunk_index: int
    chunk_type: str  # 'title', 'section', 'paragraph', 'list', 'table'
    section_title: Optional[str] = None
    parent_section: Optional[str] = None
    paragraph_index: Optional[int] = None
    has_technical_terms: bool = False
    word_count: int = 0
    sentence_count: int = 0


class SemanticChunker:
    """Advanced chunking with document structure awareness."""

    def __init__(self, max_chunk_size: int = 512, overlap_size: int = 50, preserve_sections: bool = True):
        """
        Initialize semantic chunker.

        Args:
            max_chunk_size: Maximum chunk size in characters
            overlap_size: Overlap between chunks in characters
            preserve_sections: Whether to preserve document section boundaries
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.preserve_sections = preserve_sections

        # Technical term patterns for RNI documentation
        self.technical_patterns = [
            r"\bRNI\s+\d+\.\d+",  # RNI version numbers
            r"\b[A-Z]{2,}\b",  # Acronyms (2+ capital letters)
            r"\b\d+\.\d+\.\d+",  # Version numbers
            r"\b[A-Z][a-z]*[A-Z][a-z]*",  # CamelCase
            r"\b\w+\(\)\b",  # Function calls
            r"\b\w+\.\w+",  # Dot notation
        ]

        self.technical_regex = re.compile("|".join(self.technical_patterns))

        if NLTK_AVAILABLE:
            try:
                # Ensure NLTK data is available
                nltk.data.find("tokenizers/punkt")
                nltk.data.find("corpora/stopwords")
                self.stop_words = set(stopwords.words("english"))
            except LookupError:
                logger.warning("NLTK data not found, downloading...")
                nltk.download("punkt", quiet=True)
                nltk.download("stopwords", quiet=True)
                self.stop_words = set(stopwords.words("english"))
        else:
            self.stop_words = set()

    def chunk_document(self, text: str, document_name: str = "") -> List[Dict[str, Any]]:
        """
        Chunk document using semantic awareness.

        Args:
            text: Document text
            document_name: Name of the document

        Returns:
            List of chunks with metadata
        """
        if self.preserve_sections:
            return self._hierarchical_chunking(text, document_name)
        else:
            return self._sliding_window_chunking(text, document_name)

    def _hierarchical_chunking(self, text: str, document_name: str) -> List[Dict[str, Any]]:
        """Chunk document preserving hierarchical structure."""
        chunks = []

        # First, identify document structure
        sections = self._identify_sections(text)

        current_chunk_index = 0

        for section in sections:
            section_chunks = self._chunk_section(section, document_name, current_chunk_index)
            chunks.extend(section_chunks)
            current_chunk_index += len(section_chunks)

        return chunks

    def _identify_sections(self, text: str) -> List[Dict[str, Any]]:
        """Identify document sections and their hierarchy."""
        lines = text.split("\n")
        sections = []
        current_section = {"title": None, "content": [], "type": "content", "level": 0}

        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Check if this is a section header
            header_level = self._detect_header_level(stripped)

            if header_level > 0:
                # Save previous section if it has content
                if current_section["content"]:
                    current_section["content"] = "\n".join(current_section["content"])
                    sections.append(current_section)

                # Start new section
                current_section = {"title": stripped, "content": [], "type": "section", "level": header_level}
            else:
                # Add content to current section
                current_section["content"].append(line)

        # Add final section
        if current_section["content"]:
            current_section["content"] = "\n".join(current_section["content"])
            sections.append(current_section)

        return sections

    def _detect_header_level(self, line: str) -> int:
        """Detect if line is a header and return its level."""
        # Common header patterns
        patterns = [
            r"^#{1,6}\s",  # Markdown headers
            r"^\d+\.(\d+\.)*\s",  # Numbered sections (1.1.1)
            r"^[A-Z][A-Z\s]{2,}$",  # ALL CAPS headers
            r"^[A-Z][a-zA-Z\s]{5,}$",  # Title case headers
            r"^\d+\.\s+[A-Z]",  # Numbered items with titles
        ]

        for i, pattern in enumerate(patterns):
            if re.match(pattern, line):
                return i + 1

        return 0

    def _chunk_section(self, section: Dict[str, Any], document_name: str, start_index: int) -> List[Dict[str, Any]]:
        """Chunk a single section while preserving context."""
        content = section["content"]
        section_title = section.get("title", "")

        # If section is small enough, keep as single chunk
        if len(content) <= self.max_chunk_size:
            chunk_metadata = ChunkMetadata(
                document_name=document_name,
                chunk_index=start_index,
                chunk_type=section["type"],
                section_title=section_title,
                has_technical_terms=bool(self.technical_regex.search(content)),
                word_count=len(content.split()),
                sentence_count=len(self._split_sentences(content)),
            )

            return [
                {
                    "text": self._add_context(content, section_title),
                    "metadata": chunk_metadata.__dict__,
                    "paragraph_index": start_index,
                }
            ]

        # Split large sections into semantic chunks
        return self._semantic_split_section(section, document_name, start_index)

    def _semantic_split_section(
        self, section: Dict[str, Any], document_name: str, start_index: int
    ) -> List[Dict[str, Any]]:
        """Split large section into semantically coherent chunks."""
        content = section["content"]
        section_title = section.get("title", "")

        # Split into sentences
        sentences = self._split_sentences(content)
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_index = start_index

        # Add section title context if available
        context_prefix = f"Section: {section_title}\n\n" if section_title else ""
        context_length = len(context_prefix)

        for sentence in sentences:
            sentence_length = len(sentence)

            # Check if adding this sentence would exceed max size
            if current_length + sentence_length + context_length > self.max_chunk_size and current_chunk:

                # Create chunk from current sentences
                chunk_text = context_prefix + " ".join(current_chunk)

                chunk_metadata = ChunkMetadata(
                    document_name=document_name,
                    chunk_index=chunk_index,
                    chunk_type="paragraph",
                    section_title=section_title,
                    has_technical_terms=bool(self.technical_regex.search(chunk_text)),
                    word_count=len(chunk_text.split()),
                    sentence_count=len(current_chunk),
                )

                chunks.append({"text": chunk_text, "metadata": chunk_metadata.__dict__, "paragraph_index": chunk_index})

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_chunk)
                current_chunk = overlap_sentences + [sentence]
                current_length = sum(len(s) for s in current_chunk)
                chunk_index += 1
            else:
                current_chunk.append(sentence)
                current_length += sentence_length

        # Add final chunk
        if current_chunk:
            chunk_text = context_prefix + " ".join(current_chunk)

            chunk_metadata = ChunkMetadata(
                document_name=document_name,
                chunk_index=chunk_index,
                chunk_type="paragraph",
                section_title=section_title,
                has_technical_terms=bool(self.technical_regex.search(chunk_text)),
                word_count=len(chunk_text.split()),
                sentence_count=len(current_chunk),
            )

            chunks.append({"text": chunk_text, "metadata": chunk_metadata.__dict__, "paragraph_index": chunk_index})

        return chunks

    def _get_overlap_sentences(self, sentences: List[str]) -> List[str]:
        """Get sentences for overlap based on overlap_size."""
        if not sentences:
            return []

        # Calculate how many sentences to include in overlap
        total_length = sum(len(s) for s in sentences)
        target_overlap = min(self.overlap_size, total_length // 2)

        overlap_sentences = []
        current_length = 0

        # Start from the end and work backwards
        for sentence in reversed(sentences):
            if current_length + len(sentence) <= target_overlap:
                overlap_sentences.insert(0, sentence)
                current_length += len(sentence)
            else:
                break

        return overlap_sentences

    def _sliding_window_chunking(self, text: str, document_name: str) -> List[Dict[str, Any]]:
        """Fallback sliding window chunking."""
        chunks = []
        sentences = self._split_sentences(text)

        current_chunk = []
        current_length = 0
        chunk_index = 0

        for sentence in sentences:
            if current_length + len(sentence) > self.max_chunk_size and current_chunk:
                # Create chunk
                chunk_text = " ".join(current_chunk)
                chunk_metadata = ChunkMetadata(
                    document_name=document_name,
                    chunk_index=chunk_index,
                    chunk_type="sliding_window",
                    has_technical_terms=bool(self.technical_regex.search(chunk_text)),
                    word_count=len(chunk_text.split()),
                    sentence_count=len(current_chunk),
                )

                chunks.append({"text": chunk_text, "metadata": chunk_metadata.__dict__, "paragraph_index": chunk_index})

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_chunk)
                current_chunk = overlap_sentences + [sentence]
                current_length = sum(len(s) for s in current_chunk)
                chunk_index += 1
            else:
                current_chunk.append(sentence)
                current_length += len(sentence)

        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunk_metadata = ChunkMetadata(
                document_name=document_name,
                chunk_index=chunk_index,
                chunk_type="sliding_window",
                has_technical_terms=bool(self.technical_regex.search(chunk_text)),
                word_count=len(chunk_text.split()),
                sentence_count=len(current_chunk),
            )

            chunks.append({"text": chunk_text, "metadata": chunk_metadata.__dict__, "paragraph_index": chunk_index})

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        if NLTK_AVAILABLE:
            return sent_tokenize(text)
        else:
            # Basic sentence splitting
            sentences = re.split(r"[.!?]+", text)
            return [s.strip() for s in sentences if s.strip()]

    def _add_context(self, content: str, section_title: str) -> str:
        """Add contextual information to chunk."""
        if section_title and section_title not in content:
            return f"Section: {section_title}\n\n{content}"
        return content

    def analyze_chunking_strategy(self, text: str, document_name: str = "") -> Dict[str, Any]:
        """Analyze different chunking strategies and their results."""
        strategies = {
            "hierarchical": self._hierarchical_chunking(text, document_name),
            "sliding_window": self._sliding_window_chunking(text, document_name),
        }

        analysis = {
            "document_stats": {
                "total_length": len(text),
                "word_count": len(text.split()),
                "sentence_count": len(self._split_sentences(text)),
            },
            "strategies": {},
        }

        for strategy_name, chunks in strategies.items():
            strategy_stats = {
                "chunk_count": len(chunks),
                "avg_chunk_length": sum(len(c["text"]) for c in chunks) / len(chunks) if chunks else 0,
                "avg_word_count": sum(c["metadata"]["word_count"] for c in chunks) / len(chunks) if chunks else 0,
                "technical_chunks": sum(1 for c in chunks if c["metadata"]["has_technical_terms"]),
                "chunk_types": {},
            }

            # Count chunk types
            for chunk in chunks:
                chunk_type = chunk["metadata"]["chunk_type"]
                strategy_stats["chunk_types"][chunk_type] = strategy_stats["chunk_types"].get(chunk_type, 0) + 1

            analysis["strategies"][strategy_name] = strategy_stats

        return analysis


def main():
    """Test semantic chunking implementation."""
    print("📄 Testing Semantic Chunking Implementation")
    print("=" * 50)

    # Sample technical document text
    sample_text = """
RNI 4.16 System Security User Guide

1. Introduction

This document provides comprehensive security configuration guidelines for RNI 4.16 systems. The Radio Network Interface (RNI) requires specific security measures to ensure proper operation.

1.1 System Requirements

The following system requirements must be met:
- RNI version 4.16 or higher
- Active Directory integration
- Hardware Security Module (HSM) support
- TLS 1.2 encryption

1.2 Security Architecture

The RNI security architecture consists of multiple layers:

Authentication Layer: Handles user authentication through Active Directory integration. Users must provide valid credentials to access the system.

Authorization Layer: Controls access to system resources based on user roles and permissions. Administrative functions require elevated privileges.

Encryption Layer: Provides end-to-end encryption using AES-256 algorithms. All data transmission is encrypted using TLS 1.2 protocols.

2. Configuration Procedures

2.1 Active Directory Setup

Configure Active Directory integration following these steps:

1. Install the RNI Active Directory connector
2. Configure LDAP connection settings
3. Map user groups to RNI roles
4. Test authentication workflow

2.2 HSM Configuration

Hardware Security Module configuration requires:
- HSM device initialization
- Key generation and storage
- Certificate management
- Backup procedures
"""

    # Test different chunking strategies
    chunker = SemanticChunker(max_chunk_size=300, overlap_size=50)

    print("🧩 Analyzing Chunking Strategies")
    analysis = chunker.analyze_chunking_strategy(sample_text, "Sample RNI Guide")

    print(f"Document Stats:")
    print(f"  Total Length: {analysis['document_stats']['total_length']} chars")
    print(f"  Word Count: {analysis['document_stats']['word_count']}")
    print(f"  Sentences: {analysis['document_stats']['sentence_count']}")

    for strategy, stats in analysis["strategies"].items():
        print(f"\n{strategy.upper()} Strategy:")
        print(f"  Chunks: {stats['chunk_count']}")
        print(f"  Avg Length: {stats['avg_chunk_length']:.1f} chars")
        print(f"  Avg Words: {stats['avg_word_count']:.1f}")
        print(f"  Technical Chunks: {stats['technical_chunks']}")
        print(f"  Chunk Types: {stats['chunk_types']}")

    # Show sample chunks
    print(f"\n📖 Sample Hierarchical Chunks:")
    hierarchical_chunks = chunker._hierarchical_chunking(sample_text, "Sample RNI Guide")

    for i, chunk in enumerate(hierarchical_chunks[:3]):
        print(f"\nChunk {i+1} ({chunk['metadata']['chunk_type']}):")
        print(f"  Section: {chunk['metadata'].get('section_title', 'N/A')}")
        print(f"  Technical Terms: {chunk['metadata']['has_technical_terms']}")
        print(f"  Text: {chunk['text'][:100]}...")

    print(f"\n✅ Semantic chunking system ready for integration!")


if __name__ == "__main__":
    main()
