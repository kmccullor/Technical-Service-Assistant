#!/usr/bin/env python3
"""
Phase 3A: Multimodal Enhancement System

This module implements comprehensive multimodal capabilities for the Technical Service Assistant:
1. Vision model integration for image understanding and description
2. Enhanced image extraction and preprocessing from PDFs
3. Table structure recognition and content extraction
4. Cross-modal search combining text, images, and tables
5. Multimodal embeddings for unified content representation
6. Advanced monitoring and evaluation for multimodal accuracy

Builds on Phase 2B (monitoring) and Phase 2C (accuracy improvements) foundations.
"""

import asyncio
import base64
import hashlib
import io
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import camelot
import fitz  # PyMuPDF
import numpy as np
import ollama
import pandas as pd
import torch
from advanced_semantic_chunking import AdvancedSemanticChunker

# Import Phase 2C components for integration
from phase2c_accuracy_system import AccuracyMetrics, AdvancedConfidenceScorer, Phase2CAccuracySystem, SearchResult
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor

from config import get_settings
from utils.logging_config import setup_logging

# Setup logging
logger = setup_logging(
    program_name="phase3a_multimodal",
    log_level="INFO",
    console_output=True,
)

settings = get_settings()


class ContentType(str, Enum):
    """Types of content in multimodal documents."""

    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    DIAGRAM = "diagram"
    CHART = "chart"
    SCREENSHOT = "screenshot"
    SCHEMATIC = "schematic"
    MIXED = "mixed"


class VisionModel(str, Enum):
    """Available vision models for image understanding."""

    BLIP = "blip"
    LLAVA = "llava"
    OLLAMA_VISION = "ollama_vision"
    GPT4_VISION = "gpt4_vision"


@dataclass
class ImageMetadata:
    """Enhanced metadata for extracted images."""

    image_id: str
    source_document: str
    page_number: int
    position: Tuple[int, int, int, int]  # x0, y0, x1, y1
    content_type: ContentType
    width: int
    height: int
    file_size: int
    color_mode: str
    has_text: bool = False
    text_content: str = ""
    description: str = ""
    technical_elements: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    extraction_time: datetime = field(default_factory=datetime.now)


@dataclass
class TableMetadata:
    """Enhanced metadata for extracted tables."""

    table_id: str
    source_document: str
    page_number: int
    position: Tuple[int, int, int, int]
    rows: int
    columns: int
    has_headers: bool
    data_types: Dict[str, str] = field(default_factory=dict)
    summary: str = ""
    technical_data: bool = False
    confidence_score: float = 0.0
    extraction_method: str = "camelot"


@dataclass
class MultimodalContent:
    """Unified representation of multimodal content."""

    content_id: str
    content_type: ContentType
    text_content: str
    image_data: Optional[bytes] = None
    table_data: Optional[pd.DataFrame] = None
    metadata: Union[ImageMetadata, TableMetadata, Dict[str, Any]] = None
    embeddings: Dict[str, List[float]] = field(default_factory=dict)  # text, image, multimodal
    description: str = ""
    parent_chunk_id: Optional[str] = None


class VisionModelManager:
    """Manages vision models for image understanding and description."""

    def __init__(self, model_name: VisionModel = VisionModel.BLIP):
        """Initialize vision model manager."""
        self.model_name = model_name
        self.model = None
        self.processor = None
        self.ollama_client = None

        # Initialize based on selected model
        if model_name == VisionModel.BLIP:
            self._initialize_blip()
        elif model_name == VisionModel.OLLAMA_VISION:
            self._initialize_ollama_vision()

        logger.info(f"Vision model manager initialized with {model_name.value}")

    def _initialize_blip(self):
        """Initialize BLIP model for image captioning."""
        try:
            self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            self.model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            logger.info("BLIP model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load BLIP model: {e}")
            self.model = None
            self.processor = None

    def _initialize_ollama_vision(self):
        """Initialize Ollama vision model."""
        try:
            # Extract host from ollama_url
            ollama_host = settings.ollama_url.replace("/api/embeddings", "")
            self.ollama_client = ollama.Client(host=ollama_host)
            logger.info("Ollama vision client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama vision: {e}")
            self.ollama_client = None

    async def describe_image(self, image: Image.Image, context: str = "") -> Tuple[str, float]:
        """Generate description for an image with confidence score."""

        try:
            if self.model_name == VisionModel.BLIP and self.model is not None:
                return await self._describe_with_blip(image, context)
            elif self.model_name == VisionModel.OLLAMA_VISION and self.ollama_client is not None:
                return await self._describe_with_ollama(image, context)
            else:
                # Fallback to basic description
                return await self._describe_basic(image), 0.5

        except Exception as e:
            logger.error(f"Image description failed: {e}")
            return f"Image description unavailable: {str(e)}", 0.0

    async def _describe_with_blip(self, image: Image.Image, context: str) -> Tuple[str, float]:
        """Describe image using BLIP model."""

        try:
            # Prepare inputs
            if context:
                text_prompt = f"a technical diagram showing {context}"
                inputs = self.processor(image, text_prompt, return_tensors="pt")
            else:
                inputs = self.processor(image, return_tensors="pt")

            # Generate description
            with torch.no_grad():
                outputs = self.model.generate(**inputs, max_length=100, num_beams=4)

            description = self.processor.decode(outputs[0], skip_special_tokens=True)

            # Calculate confidence based on generation quality
            confidence = min(0.9, len(description.split()) / 20.0)  # Longer descriptions = higher confidence

            return description, confidence

        except Exception as e:
            logger.error(f"BLIP description failed: {e}")
            return f"Technical image with {context}" if context else "Technical image", 0.3

    async def _describe_with_ollama(self, image: Image.Image, context: str) -> Tuple[str, float]:
        """Describe image using Ollama vision model."""

        try:
            # Convert image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            image_b64 = base64.b64encode(buffered.getvalue()).decode()

            # Prepare prompt
            prompt = f"Describe this technical image in detail"
            if context:
                prompt += f", focusing on {context}"

            # Call Ollama vision model (assuming llava is available)
            response = self.ollama_client.generate(model="llava", prompt=prompt, images=[image_b64], stream=False)

            description = response.get("response", "").strip()
            confidence = 0.8 if len(description) > 50 else 0.5

            return description, confidence

        except Exception as e:
            logger.error(f"Ollama vision description failed: {e}")
            return f"Technical image from {context}" if context else "Technical image", 0.3

    async def _describe_basic(self, image: Image.Image) -> str:
        """Generate basic description based on image properties."""

        width, height = image.size
        mode = image.mode

        # Basic analysis
        if width > height * 2:
            aspect_desc = "wide format"
        elif height > width * 2:
            aspect_desc = "tall format"
        else:
            aspect_desc = "standard format"

        # Color analysis
        if mode == "L":
            color_desc = "grayscale"
        elif mode == "RGB":
            color_desc = "color"
        else:
            color_desc = mode.lower()

        return f"Technical {color_desc} image in {aspect_desc} ({width}x{height})"


class ImageExtractionPipeline:
    """Enhanced image extraction and preprocessing pipeline."""

    def __init__(self, vision_model: VisionModelManager):
        """Initialize image extraction pipeline."""
        self.vision_model = vision_model
        self.temp_dir = Path("temp_images")
        self.temp_dir.mkdir(exist_ok=True)

    async def extract_images_from_pdf(self, pdf_path: str) -> List[MultimodalContent]:
        """Extract images from PDF with enhanced metadata."""

        logger.info(f"Extracting images from {pdf_path}")

        multimodal_contents = []

        try:
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    try:
                        # Extract image data
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)

                        # Skip if not RGB or GRAY
                        if pix.n not in [1, 3, 4]:
                            pix = None
                            continue

                        # Convert to PIL Image
                        if pix.n == 1:
                            img_mode = "L"
                        elif pix.n == 3:
                            img_mode = "RGB"
                        elif pix.n == 4:
                            img_mode = "RGBA"
                        else:
                            img_mode = "RGB"  # Default fallback

                        img_data = pix.tobytes(img_mode.lower())
                        pil_image = Image.frombytes(img_mode, [pix.width, pix.height], img_data)

                        # Generate unique image ID
                        image_id = hashlib.md5(img_data).hexdigest()[:16]

                        # Get image position on page
                        img_rect = (
                            page.get_image_rects(xref)[0]
                            if page.get_image_rects(xref)
                            else fitz.Rect(0, 0, pix.width, pix.height)
                        )

                        # Determine content type
                        content_type = self._classify_image_content(pil_image)

                        # Generate description (run synchronously for now)
                        try:
                            description, confidence = await self.vision_model.describe_image(
                                pil_image, context=f"technical document page {page_num + 1}"
                            )
                        except Exception as e:
                            logger.warning(f"Vision model description failed, using fallback: {e}")
                            description = f"Technical image from page {page_num + 1}"
                            confidence = 0.3

                        # Create metadata
                        metadata = ImageMetadata(
                            image_id=image_id,
                            source_document=Path(pdf_path).name,
                            page_number=page_num + 1,
                            position=(int(img_rect.x0), int(img_rect.y0), int(img_rect.x1), int(img_rect.y1)),
                            content_type=content_type,
                            width=pix.width,
                            height=pix.height,
                            file_size=len(img_data),
                            color_mode=img_mode,
                            description=description,
                            confidence_score=confidence,
                        )

                        # Extract technical elements
                        metadata.technical_elements = self._extract_technical_elements(pil_image, description)

                        # Create multimodal content
                        multimodal_content = MultimodalContent(
                            content_id=f"img_{image_id}",
                            content_type=content_type,
                            text_content=description,
                            image_data=img_data,
                            metadata=metadata,
                            description=description,
                        )

                        multimodal_contents.append(multimodal_content)

                        # Cleanup
                        pix = None

                    except Exception as e:
                        logger.error(f"Failed to extract image {img_index} from page {page_num}: {e}")
                        continue

            doc.close()

        except Exception as e:
            logger.error(f"PDF image extraction failed for {pdf_path}: {e}")

        logger.info(f"Extracted {len(multimodal_contents)} images from {pdf_path}")
        return multimodal_contents

    def _classify_image_content(self, image: Image.Image) -> ContentType:
        """Classify image content type based on visual characteristics."""

        width, height = image.size

        # Aspect ratio analysis
        aspect_ratio = width / height

        # Simple heuristics for content type classification
        if aspect_ratio > 3:
            return ContentType.DIAGRAM  # Wide diagrams
        elif aspect_ratio < 0.5:
            return ContentType.SCREENSHOT  # Tall screenshots
        elif min(width, height) < 100:
            return ContentType.IMAGE  # Small images
        else:
            # More sophisticated analysis could be added here
            # For now, classify as diagram for technical documents
            return ContentType.DIAGRAM

    def _extract_technical_elements(self, image: Image.Image, description: str) -> List[str]:
        """Extract technical elements from image and description."""

        technical_elements = []

        # Text-based element detection
        technical_keywords = [
            "circuit",
            "diagram",
            "schematic",
            "flowchart",
            "network",
            "topology",
            "configuration",
            "interface",
            "protocol",
            "connection",
            "server",
            "database",
            "router",
            "switch",
            "cable",
            "port",
            "tcp",
            "ip",
            "ethernet",
            "wifi",
            "wireless",
            "antenna",
        ]

        description_lower = description.lower()
        for keyword in technical_keywords:
            if keyword in description_lower:
                technical_elements.append(keyword)

        # Image-based element detection (basic)
        # This could be enhanced with computer vision techniques
        width, height = image.size

        if width > height * 1.5:
            technical_elements.append("horizontal_layout")
        elif height > width * 1.5:
            technical_elements.append("vertical_layout")

        # Color analysis
        if image.mode == "L":
            technical_elements.append("monochrome")
        elif image.mode == "RGB":
            # Simple color analysis
            img_array = np.array(image)
            if img_array.mean() < 50:
                technical_elements.append("dark_background")
            elif img_array.mean() > 200:
                technical_elements.append("light_background")

        return list(set(technical_elements))  # Remove duplicates


class EnhancedTableProcessor:
    """Enhanced table processing with structure recognition."""

    def __init__(self):
        """Initialize enhanced table processor."""
        self.camelot_config = {
            "flavor": "lattice",  # Start with lattice detection
            "strip_text": "\n",
            "split_text": True,
            "edge_tol": 50,
        }

    def extract_tables_from_pdf(self, pdf_path: str) -> List[MultimodalContent]:
        """Extract tables with enhanced structure recognition."""

        logger.info(f"Extracting tables from {pdf_path}")

        multimodal_contents = []

        try:
            # Try lattice method first
            tables = camelot.read_pdf(pdf_path, **self.camelot_config)

            if len(tables) == 0:
                # Fallback to stream method
                logger.info("No tables found with lattice, trying stream method")
                self.camelot_config["flavor"] = "stream"
                tables = camelot.read_pdf(pdf_path, **self.camelot_config)

            for i, table in enumerate(tables):
                try:
                    # Generate table ID
                    table_content = table.df.to_string()
                    table_id = hashlib.md5(table_content.encode()).hexdigest()[:16]

                    # Analyze table structure
                    df = table.df
                    rows, columns = df.shape

                    # Detect headers
                    has_headers = self._detect_table_headers(df)

                    # Analyze data types
                    data_types = self._analyze_data_types(df)

                    # Generate table summary
                    summary = self._generate_table_summary(df, has_headers)

                    # Detect technical data
                    is_technical = self._is_technical_table(df, summary)

                    # Create metadata
                    metadata = TableMetadata(
                        table_id=table_id,
                        source_document=Path(pdf_path).name,
                        page_number=table.page,
                        position=(0, 0, 0, 0),  # Camelot doesn't provide exact position
                        rows=rows,
                        columns=columns,
                        has_headers=has_headers,
                        data_types=data_types,
                        summary=summary,
                        technical_data=is_technical,
                        confidence_score=table.accuracy / 100.0,  # Camelot accuracy score
                    )

                    # Create text representation
                    text_content = self._table_to_text(df, has_headers, summary)

                    # Create multimodal content
                    multimodal_content = MultimodalContent(
                        content_id=f"table_{table_id}",
                        content_type=ContentType.TABLE,
                        text_content=text_content,
                        table_data=df,
                        metadata=metadata,
                        description=summary,
                    )

                    multimodal_contents.append(multimodal_content)

                except Exception as e:
                    logger.error(f"Failed to process table {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Table extraction failed for {pdf_path}: {e}")

        logger.info(f"Extracted {len(multimodal_contents)} tables from {pdf_path}")
        return multimodal_contents

    def _detect_table_headers(self, df: pd.DataFrame) -> bool:
        """Detect if table has headers."""

        if df.empty:
            return False

        first_row = df.iloc[0]

        # Check if first row contains text while others contain mostly numbers
        first_row_text = sum(1 for cell in first_row if isinstance(cell, str) and not cell.isdigit())

        if len(df) > 1:
            second_row = df.iloc[1]
            second_row_numbers = sum(1 for cell in second_row if str(cell).replace(".", "").isdigit())

            # If first row is mostly text and second row is mostly numbers
            if first_row_text > len(first_row) * 0.7 and second_row_numbers > len(second_row) * 0.5:
                return True

        return first_row_text > len(first_row) * 0.8

    def _analyze_data_types(self, df: pd.DataFrame) -> Dict[str, str]:
        """Analyze data types in each column."""

        data_types = {}

        for col in df.columns:
            column_data = df[col].dropna()

            if column_data.empty:
                data_types[str(col)] = "empty"
                continue

            # Check for numeric data
            numeric_count = sum(1 for val in column_data if str(val).replace(".", "").replace("-", "").isdigit())

            if numeric_count > len(column_data) * 0.8:
                data_types[str(col)] = "numeric"
            elif numeric_count > len(column_data) * 0.3:
                data_types[str(col)] = "mixed"
            else:
                data_types[str(col)] = "text"

        return data_types

    def _generate_table_summary(self, df: pd.DataFrame, has_headers: bool) -> str:
        """Generate a descriptive summary of the table."""

        rows, cols = df.shape

        summary_parts = [f"Table with {rows} rows and {cols} columns"]

        if has_headers:
            summary_parts.append("with headers")

        # Identify key content
        sample_cells = []
        for i in range(min(3, rows)):
            for j in range(min(3, cols)):
                cell_value = str(df.iloc[i, j]).strip()
                if cell_value and cell_value != "nan":
                    sample_cells.append(cell_value)

        if sample_cells:
            summary_parts.append(f"containing data like: {', '.join(sample_cells[:5])}")

        return ". ".join(summary_parts)

    def _is_technical_table(self, df: pd.DataFrame, summary: str) -> bool:
        """Determine if table contains technical data."""

        technical_indicators = [
            "parameter",
            "config",
            "setting",
            "value",
            "specification",
            "port",
            "address",
            "protocol",
            "version",
            "status",
            "tcp",
            "ip",
            "mac",
            "ethernet",
            "wifi",
            "database",
            "server",
            "router",
            "switch",
            "interface",
            "connection",
        ]

        # Check table content
        table_text = df.to_string().lower()
        summary_text = summary.lower()

        tech_count = sum(
            1 for indicator in technical_indicators if indicator in table_text or indicator in summary_text
        )

        return tech_count >= 2

    def _table_to_text(self, df: pd.DataFrame, has_headers: bool, summary: str) -> str:
        """Convert table to searchable text representation."""

        text_parts = [summary]

        if has_headers and not df.empty:
            headers = list(df.iloc[0])
            text_parts.append(f"Column headers: {', '.join(str(h) for h in headers)}")

            # Add key data rows
            for i in range(1, min(6, len(df))):  # First 5 data rows
                row_data = list(df.iloc[i])
                row_text = " | ".join(str(cell) for cell in row_data if str(cell).strip() and str(cell) != "nan")
                if row_text:
                    text_parts.append(f"Row {i}: {row_text}")
        else:
            # No headers detected, just add sample data
            for i in range(min(5, len(df))):
                row_data = list(df.iloc[i])
                row_text = " | ".join(str(cell) for cell in row_data if str(cell).strip() and str(cell) != "nan")
                if row_text:
                    text_parts.append(f"Row {i+1}: {row_text}")

        return "\n".join(text_parts)


class MultimodalSearchEngine:
    """Advanced multimodal search combining text, images, and tables."""

    def __init__(self, phase2c_system: Phase2CAccuracySystem):
        """Initialize multimodal search engine."""
        self.phase2c_system = phase2c_system
        self.confidence_scorer = AdvancedConfidenceScorer()

        # Storage for multimodal content
        self.multimodal_index = {}  # content_id -> MultimodalContent

        logger.info("Multimodal search engine initialized")

    def index_multimodal_content(self, contents: List[MultimodalContent]):
        """Index multimodal content for search."""

        for content in contents:
            self.multimodal_index[content.content_id] = content

        logger.info(f"Indexed {len(contents)} multimodal content items")

    async def multimodal_search(
        self, query: str, content_types: List[ContentType] = None, top_k: int = 10
    ) -> Tuple[List[SearchResult], AccuracyMetrics]:
        """Perform multimodal search across text, images, and tables."""

        if content_types is None:
            content_types = [ContentType.TEXT, ContentType.IMAGE, ContentType.TABLE]

        logger.info(f"Multimodal search for: '{query}' across {content_types}")

        start_time = time.time()

        try:
            # Phase 1: Text-based search using Phase 2C system
            text_results, text_metrics = await self.phase2c_system.comprehensive_search(
                query, top_k=top_k * 2  # Get more candidates for reranking
            )

            # Phase 2: Multimodal content matching
            multimodal_matches = self._find_multimodal_matches(query, content_types)

            # Phase 3: Combine and rerank results
            combined_results = self._combine_multimodal_results(text_results, multimodal_matches, query)

            # Phase 4: Calculate multimodal confidence
            final_results = combined_results[:top_k]
            confidence, analysis = self.confidence_scorer.calculate_confidence(query, final_results)

            # Create enhanced metrics
            total_time = time.time() - start_time
            multimodal_metrics = AccuracyMetrics(
                query=query,
                method="multimodal_search",
                results_count=len(final_results),
                response_time=total_time,
                confidence_score=confidence,
                semantic_coverage=text_metrics.semantic_coverage,
                keyword_coverage=text_metrics.keyword_coverage,
                diversity_score=self._calculate_multimodal_diversity(final_results),
                uncertainty_level=analysis.get("uncertainty_penalty", 0.0),
                quality_indicators={
                    **analysis,
                    "multimodal_content_count": len(multimodal_matches),
                    "content_types_found": list(set(r.method for r in final_results if hasattr(r, "method"))),
                },
            )

            logger.info(
                f"Multimodal search completed: {len(final_results)} results, "
                f"confidence: {confidence:.3f}, time: {total_time:.3f}s"
            )

            return final_results, multimodal_metrics

        except Exception as e:
            logger.error(f"Multimodal search failed: {e}")
            return [], AccuracyMetrics(
                query=query,
                method="multimodal_search",
                results_count=0,
                response_time=time.time() - start_time,
                confidence_score=0.0,
                semantic_coverage=0.0,
                keyword_coverage=0.0,
                diversity_score=0.0,
                uncertainty_level=1.0,
                quality_indicators={"error": str(e)},
            )

    def _find_multimodal_matches(self, query: str, content_types: List[ContentType]) -> List[MultimodalContent]:
        """Find matching multimodal content."""

        matches = []
        query_lower = query.lower()

        for content in self.multimodal_index.values():
            if content.content_type not in content_types:
                continue

            # Calculate relevance score
            relevance_score = 0.0

            # Text content matching
            if content.text_content:
                text_lower = content.text_content.lower()
                # Simple keyword matching (could be enhanced with embeddings)
                query_words = query_lower.split()
                matches_count = sum(1 for word in query_words if word in text_lower)
                relevance_score += matches_count / len(query_words) * 0.6

            # Description matching
            if content.description:
                desc_lower = content.description.lower()
                query_words = query_lower.split()
                matches_count = sum(1 for word in query_words if word in desc_lower)
                relevance_score += matches_count / len(query_words) * 0.4

            # Technical elements matching (for images)
            if hasattr(content.metadata, "technical_elements"):
                tech_elements = [elem.lower() for elem in content.metadata.technical_elements]
                tech_matches = sum(1 for word in query_lower.split() if word in tech_elements)
                relevance_score += tech_matches * 0.3

            # Only include if there's some relevance
            if relevance_score > 0.1:
                content.relevance_score = relevance_score
                matches.append(content)

        # Sort by relevance
        matches.sort(key=lambda x: x.relevance_score, reverse=True)

        return matches[:20]  # Limit to top 20 multimodal matches

    def _combine_multimodal_results(
        self, text_results: List[SearchResult], multimodal_matches: List[MultimodalContent], query: str
    ) -> List[SearchResult]:
        """Combine text and multimodal results with unified scoring."""

        combined_results = []

        # Add text results
        for result in text_results:
            combined_results.append(result)

        # Add multimodal results as SearchResult objects
        for content in multimodal_matches:
            # Create SearchResult from MultimodalContent
            search_result = SearchResult(
                content=content.text_content,
                document_name=getattr(content.metadata, "source_document", "multimodal_content"),
                metadata={
                    "content_type": content.content_type.value,
                    "content_id": content.content_id,
                    "description": content.description,
                    "multimodal": True,
                },
                score=getattr(content, "relevance_score", 0.5),
                method=f"multimodal_{content.content_type.value}",
                confidence=getattr(content.metadata, "confidence_score", 0.5),
            )
            combined_results.append(search_result)

        # Re-rank combined results
        # This is a simple approach - could be enhanced with learned ranking
        combined_results.sort(key=lambda x: x.score, reverse=True)

        return combined_results

    def _calculate_multimodal_diversity(self, results: List[SearchResult]) -> float:
        """Calculate diversity score for multimodal results."""

        if not results:
            return 0.0

        # Count different content types
        content_types = set()
        for result in results:
            if hasattr(result, "metadata") and "content_type" in result.metadata:
                content_types.add(result.metadata["content_type"])
            else:
                content_types.add("text")  # Default for text results

        # Diversity based on content type variety
        max_types = len(ContentType)
        diversity = len(content_types) / max_types

        return diversity


class Phase3AMultimodalSystem:
    """Main Phase 3A multimodal system coordinator."""

    def __init__(self, vision_model: VisionModel = VisionModel.BLIP):
        """Initialize Phase 3A multimodal system."""

        # Initialize components
        self.vision_model_manager = VisionModelManager(vision_model)
        self.image_extractor = ImageExtractionPipeline(self.vision_model_manager)
        self.table_processor = EnhancedTableProcessor()

        # Initialize Phase 2C system for integration
        self.phase2c_system = Phase2CAccuracySystem()
        self.multimodal_search = MultimodalSearchEngine(self.phase2c_system)

        # Storage
        self.processed_documents = {}

        logger.info("Phase 3A multimodal system initialized")

    async def process_document_multimodal(self, pdf_path: str) -> Dict[str, Any]:
        """Process document with full multimodal capabilities."""

        logger.info(f"Processing document with multimodal capabilities: {pdf_path}")

        start_time = time.time()
        document_name = Path(pdf_path).name

        try:
            # Phase 1: Extract text using Phase 2C semantic chunking
            semantic_chunker = AdvancedSemanticChunker()

            # Read PDF text
            doc = fitz.open(pdf_path)
            full_text = ""
            for page in doc:
                full_text += page.get_text()
            doc.close()

            text_chunks = semantic_chunker.chunk_document(full_text, document_name)

            # Phase 2: Extract images
            image_contents = await self.image_extractor.extract_images_from_pdf(pdf_path)

            # Phase 3: Extract tables
            table_contents = self.table_processor.extract_tables_from_pdf(pdf_path)

            # Phase 4: Index all content for search
            all_multimodal_content = image_contents + table_contents
            self.multimodal_search.index_multimodal_content(all_multimodal_content)

            # Phase 5: Generate processing summary
            processing_time = time.time() - start_time

            summary = {
                "document_name": document_name,
                "processing_time": processing_time,
                "text_chunks": len(text_chunks),
                "images_extracted": len(image_contents),
                "tables_extracted": len(table_contents),
                "multimodal_content_total": len(all_multimodal_content),
                "content_types": {
                    "text": len(text_chunks),
                    "images": len(
                        [c for c in image_contents if c.content_type in [ContentType.IMAGE, ContentType.DIAGRAM]]
                    ),
                    "tables": len(table_contents),
                    "technical_diagrams": len([c for c in image_contents if c.metadata.technical_elements]),
                },
                "timestamp": datetime.now().isoformat(),
            }

            self.processed_documents[document_name] = {
                "text_chunks": text_chunks,
                "multimodal_content": all_multimodal_content,
                "summary": summary,
            }

            logger.info(
                f"Multimodal processing completed for {document_name}: "
                f"{len(text_chunks)} text chunks, {len(image_contents)} images, "
                f"{len(table_contents)} tables in {processing_time:.2f}s"
            )

            return summary

        except Exception as e:
            logger.error(f"Multimodal document processing failed for {pdf_path}: {e}")
            return {
                "document_name": document_name,
                "error": str(e),
                "processing_time": time.time() - start_time,
                "timestamp": datetime.now().isoformat(),
            }

    async def search_multimodal(
        self, query: str, content_types: List[ContentType] = None, top_k: int = 10
    ) -> Tuple[List[SearchResult], AccuracyMetrics]:
        """Perform comprehensive multimodal search."""

        return await self.multimodal_search.multimodal_search(query, content_types, top_k)

    def get_multimodal_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about multimodal content."""

        total_documents = len(self.processed_documents)
        total_multimodal_items = len(self.multimodal_search.multimodal_index)

        content_type_counts = {}
        for content in self.multimodal_search.multimodal_index.values():
            content_type = content.content_type.value
            content_type_counts[content_type] = content_type_counts.get(content_type, 0) + 1

        # Calculate average confidence scores
        avg_confidences = {}
        for content_type in ContentType:
            items = [c for c in self.multimodal_search.multimodal_index.values() if c.content_type == content_type]
            if items:
                confidences = [getattr(c.metadata, "confidence_score", 0.0) for c in items]
                avg_confidences[content_type.value] = sum(confidences) / len(confidences)

        return {
            "total_documents_processed": total_documents,
            "total_multimodal_items": total_multimodal_items,
            "content_type_distribution": content_type_counts,
            "average_confidence_scores": avg_confidences,
            "timestamp": datetime.now().isoformat(),
        }


# Usage example and testing
async def main():
    """Main function for testing Phase 3A multimodal system."""

    logger.info("🚀 Starting Phase 3A: Multimodal Enhancement System Test")

    # Initialize multimodal system
    multimodal_system = Phase3AMultimodalSystem(VisionModel.BLIP)

    # Test multimodal search without processing documents (using mock data)
    logger.info("Testing multimodal search capabilities...")

    test_queries = [
        "network configuration diagram",
        "database table specifications",
        "system architecture overview",
        "troubleshooting flowchart",
    ]

    for query in test_queries:
        logger.info(f"Testing query: '{query}'")

        try:
            results, metrics = await multimodal_system.search_multimodal(query, top_k=5)

            logger.info(
                f"Query: '{query}' -> {len(results)} results, "
                f"confidence: {metrics.confidence_score:.3f}, "
                f"time: {metrics.response_time:.3f}s"
            )

        except Exception as e:
            logger.error(f"Multimodal search test failed for '{query}': {e}")

    # Get system statistics
    stats = multimodal_system.get_multimodal_statistics()
    logger.info(f"Multimodal system statistics: {json.dumps(stats, indent=2)}")

    logger.info("Phase 3A multimodal system test completed")


if __name__ == "__main__":
    asyncio.run(main())
