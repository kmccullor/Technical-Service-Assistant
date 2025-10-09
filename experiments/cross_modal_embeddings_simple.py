#!/usr/bin/env python3
"""
Cross-Modal Embeddings System for Phase 3A (Simplified)

This module implements a simplified unified embedding space for text, image, and table content.
Focus on core functionality using available dependencies while maintaining the architecture.

Key Features:
1. Unified embedding generation for text, image, and table content
2. Cross-modal similarity scoring using available libraries
3. Integration with existing Phase 3A multimodal system
4. Vector storage and efficient retrieval
5. Fallback mechanisms for missing dependencies
"""

import asyncio
import json
import time
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import warnings

import numpy as np
import pandas as pd
import requests

from config import get_settings
from utils.logging_config import setup_logging

# Setup logging first
logger = setup_logging(
    program_name="cross_modal_embeddings_simple",
    log_level="INFO",
    console_output=True,
)

settings = get_settings()

# Import Phase 3A components
try:
    from phase3a_multimodal_simple import (
        MultimodalContent, ContentType, Phase3AMultimodalSystem,
        VisionModel, ImageMetadata, TableMetadata
    )
    PHASE3A_AVAILABLE = True
    logger.info("Phase 3A components loaded successfully")
except ImportError:
    logger.warning("Phase 3A system not available, using basic types")
    PHASE3A_AVAILABLE = False
    
    # Basic fallback types
    class ContentType(str, Enum):
        TEXT = "text"
        IMAGE = "image"
        TABLE = "table"
        DIAGRAM = "diagram"

# Import Phase 2C components
try:
    from phase2c_accuracy_system import SearchResult, AccuracyMetrics
    PHASE2C_AVAILABLE = True
    logger.info("Phase 2C components loaded successfully")
except ImportError:
    logger.warning("Phase 2C system not available, using mock types")
    PHASE2C_AVAILABLE = False
    
    @dataclass
    class SearchResult:
        content: str
        document_name: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        score: float = 0.0
        method: str = "mock"
        confidence: float = 0.5

class EmbeddingModel(str, Enum):
    """Available embedding models for different modalities."""
    OLLAMA_EMBED = "ollama_embed"   # Use existing Ollama embeddings
    BASIC_TEXT = "basic_text"       # Simple text embeddings
    BASIC_PROPERTIES = "basic_properties"  # Property-based embeddings

@dataclass
class EmbeddingVector:
    """Represents an embedding vector with metadata."""
    content_id: str
    content_type: ContentType
    embedding: np.ndarray
    model_name: str
    embedding_dim: int
    confidence: float = 1.0
    generation_time: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CrossModalSimilarity:
    """Represents similarity between content across modalities."""
    content_id_1: str
    content_id_2: str
    content_type_1: ContentType
    content_type_2: ContentType
    similarity_score: float
    method: str
    is_cross_modal: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

class SimpleCrossModalEmbeddingGenerator:
    """Simplified cross-modal embedding generator using available dependencies."""
    
    def __init__(self, primary_model: EmbeddingModel = EmbeddingModel.OLLAMA_EMBED):
        """Initialize simplified embedding generator."""
        self.primary_model = primary_model
        self.embedding_cache = {}
        self.standard_dim = 768  # Standard embedding dimension
        
        logger.info(f"Simplified cross-modal embedding generator initialized with {primary_model.value}")
    
    async def generate_text_embedding(self, text: str) -> EmbeddingVector:
        """Generate embedding for text content."""
        
        # Use cache if available
        cache_key = hashlib.md5(f"{text}_{self.primary_model.value}".encode()).hexdigest()
        if cache_key in self.embedding_cache:
            cached = self.embedding_cache[cache_key]
            return EmbeddingVector(
                content_id=cache_key[:16],
                content_type=ContentType.TEXT,
                embedding=cached['embedding'],
                model_name=self.primary_model.value,
                embedding_dim=len(cached['embedding']),
                confidence=cached.get('confidence', 1.0)
            )
        
        try:
            if self.primary_model == EmbeddingModel.OLLAMA_EMBED:
                embedding = await self._generate_ollama_embedding(text)
                confidence = 0.9
            else:
                embedding = self._generate_basic_text_embedding(text)
                confidence = 0.6
            
            # Cache result
            self.embedding_cache[cache_key] = {
                'embedding': embedding,
                'confidence': confidence,
                'timestamp': datetime.now()
            }
            
            return EmbeddingVector(
                content_id=cache_key[:16],
                content_type=ContentType.TEXT,
                embedding=embedding,
                model_name=self.primary_model.value,
                embedding_dim=len(embedding),
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Text embedding generation failed: {e}")
            # Return zero vector as fallback
            fallback_embedding = np.zeros(self.standard_dim)
            return EmbeddingVector(
                content_id=cache_key[:16],
                content_type=ContentType.TEXT,
                embedding=fallback_embedding,
                model_name=f"{self.primary_model.value}_fallback",
                embedding_dim=len(fallback_embedding),
                confidence=0.1
            )
    
    async def generate_image_embedding(self, description: str = "", image_properties: Dict = None) -> EmbeddingVector:
        """Generate embedding for image content using description and properties."""
        
        try:
            # Create image identifier
            content_str = description + str(image_properties or {})
            image_id = hashlib.md5(content_str.encode()).hexdigest()[:16]
            
            # Generate embedding from description and properties
            if description:
                # Use text embedding as base
                text_embedding = await self.generate_text_embedding(f"Image: {description}")
                
                # Add property-based features if available
                if image_properties:
                    prop_features = self._extract_image_property_features(image_properties)
                    # Combine text embedding with property features
                    combined_embedding = self._combine_embeddings(text_embedding.embedding, prop_features)
                else:
                    combined_embedding = text_embedding.embedding
                
                return EmbeddingVector(
                    content_id=image_id,
                    content_type=ContentType.IMAGE,
                    embedding=combined_embedding,
                    model_name="image_description_hybrid",
                    embedding_dim=len(combined_embedding),
                    confidence=0.7,
                    metadata={
                        "description": description,
                        "properties": image_properties or {},
                        "method": "description_with_properties"
                    }
                )
            else:
                # Generate basic embedding from properties only
                prop_embedding = self._generate_basic_image_embedding(image_properties or {})
                
                return EmbeddingVector(
                    content_id=image_id,
                    content_type=ContentType.IMAGE,
                    embedding=prop_embedding,
                    model_name="basic_image_properties",
                    embedding_dim=len(prop_embedding),
                    confidence=0.4,
                    metadata={
                        "properties": image_properties or {},
                        "method": "properties_only"
                    }
                )
                
        except Exception as e:
            logger.error(f"Image embedding generation failed: {e}")
            fallback_embedding = np.zeros(self.standard_dim)
            return EmbeddingVector(
                content_id="img_fallback",
                content_type=ContentType.IMAGE,
                embedding=fallback_embedding,
                model_name="image_fallback",
                embedding_dim=len(fallback_embedding),
                confidence=0.1
            )
    
    async def generate_table_embedding(self, table_data: pd.DataFrame = None, summary: str = "") -> EmbeddingVector:
        """Generate embedding for table content."""
        
        try:
            # Create table identifier
            table_str = summary + (table_data.to_string() if table_data is not None else "")
            table_id = hashlib.md5(table_str.encode()).hexdigest()[:16]
            
            # Create comprehensive text representation
            text_parts = []
            if summary:
                text_parts.append(f"Table: {summary}")
            
            # Add column and data information
            if table_data is not None and not table_data.empty:
                text_parts.append(f"Columns: {', '.join(table_data.columns)}")
                
                # Add sample data
                for i in range(min(3, len(table_data))):
                    row_text = " | ".join(str(cell) for cell in table_data.iloc[i])
                    text_parts.append(f"Row {i+1}: {row_text}")
            
            combined_text = "\n".join(text_parts) if text_parts else "Empty table"
            
            # Generate embedding from text representation
            text_embedding = await self.generate_text_embedding(combined_text)
            
            # Add table structure features
            if table_data is not None:
                structure_features = self._extract_table_structure_features(table_data)
                combined_embedding = self._combine_embeddings(text_embedding.embedding, structure_features)
            else:
                combined_embedding = text_embedding.embedding
            
            return EmbeddingVector(
                content_id=table_id,
                content_type=ContentType.TABLE,
                embedding=combined_embedding,
                model_name="table_hybrid_representation",
                embedding_dim=len(combined_embedding),
                confidence=0.8,
                metadata={
                    "table_shape": table_data.shape if table_data is not None else (0, 0),
                    "summary": summary,
                    "text_length": len(combined_text)
                }
            )
            
        except Exception as e:
            logger.error(f"Table embedding generation failed: {e}")
            fallback_embedding = np.zeros(self.standard_dim)
            return EmbeddingVector(
                content_id="table_fallback",
                content_type=ContentType.TABLE,
                embedding=fallback_embedding,
                model_name="table_fallback",
                embedding_dim=len(fallback_embedding),
                confidence=0.1
            )
    
    async def _generate_ollama_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using Ollama API."""
        
        try:
            # Use localhost with proper port instead of hostname
            endpoint = "http://localhost:11434/api/embeddings"
            model_name = getattr(settings, 'embedding_model', 'nomic-embed-text:v1.5')
            
            logger.debug(f"Using Ollama endpoint: {endpoint} with model: {model_name}")
            
            # Make request to Ollama embedding endpoint
            response = requests.post(
                endpoint,
                json={
                    "model": model_name,
                    "prompt": text
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                # Handle different response formats
                if "embeddings" in data:
                    embedding = np.array(data["embeddings"])
                    if embedding.ndim > 1:
                        embedding = embedding[0]  # Take first embedding if batch
                elif "embedding" in data:
                    embedding = np.array(data["embedding"])
                else:
                    raise Exception("No embedding found in response")
                
                return embedding
            else:
                logger.warning(f"Ollama embedding request failed: {response.status_code}")
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ollama embedding failed: {e}")
            raise
    
    def _generate_basic_text_embedding(self, text: str) -> np.ndarray:
        """Generate basic text embedding using simple techniques."""
        
        words = text.lower().split()
        embedding = np.zeros(self.standard_dim)
        
        # Simple hash-based embedding with TF-IDF-like weighting
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Create embedding
        for i, word in enumerate(words[:100]):  # Limit to first 100 words
            word_hash = hash(word) % self.standard_dim
            tf_idf_weight = (1.0 + np.log(word_counts[word])) / (i + 1)  # Simple TF-IDF approximation
            embedding[word_hash] += tf_idf_weight
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding
    
    def _extract_image_property_features(self, properties: Dict) -> np.ndarray:
        """Extract features from image properties."""
        
        features = np.zeros(64)  # Fixed size feature vector
        
        # Size features
        if 'width' in properties and 'height' in properties:
            features[0] = min(properties['width'] / 1000.0, 10.0)  # Normalized width
            features[1] = min(properties['height'] / 1000.0, 10.0)  # Normalized height
            features[2] = properties['width'] / properties['height']  # Aspect ratio
        
        # Color mode features
        if 'color_mode' in properties:
            mode = properties['color_mode'].lower()
            if mode == 'rgb':
                features[3] = 1.0
            elif mode == 'l':
                features[4] = 1.0
            else:
                features[5] = 1.0
        
        # File size feature
        if 'file_size' in properties:
            features[6] = min(properties['file_size'] / 1000000.0, 10.0)  # MB
        
        return features
    
    def _generate_basic_image_embedding(self, properties: Dict) -> np.ndarray:
        """Generate basic image embedding from properties."""
        
        embedding = np.zeros(self.standard_dim)
        
        # Extract property features
        prop_features = self._extract_image_property_features(properties)
        
        # Place features in embedding vector
        embedding[:len(prop_features)] = prop_features
        
        return embedding
    
    def _extract_table_structure_features(self, table_data: pd.DataFrame) -> np.ndarray:
        """Extract structural features from table."""
        
        features = np.zeros(32)  # Fixed size feature vector
        
        # Basic structure
        features[0] = min(table_data.shape[0] / 100.0, 10.0)  # Normalized row count
        features[1] = min(table_data.shape[1] / 20.0, 10.0)   # Normalized column count
        
        # Data type analysis
        numeric_cols = 0
        text_cols = 0
        
        for col in table_data.columns:
            column_data = table_data[col].dropna()
            if column_data.empty:
                continue
            
            # Simple type detection
            numeric_count = 0
            for val in column_data:
                try:
                    float(str(val))
                    numeric_count += 1
                except ValueError:
                    pass
            
            if numeric_count > len(column_data) * 0.7:
                numeric_cols += 1
            else:
                text_cols += 1
        
        features[2] = numeric_cols / max(table_data.shape[1], 1)  # Ratio of numeric columns
        features[3] = text_cols / max(table_data.shape[1], 1)    # Ratio of text columns
        
        return features
    
    def _combine_embeddings(self, embedding1: np.ndarray, features: np.ndarray) -> np.ndarray:
        """Combine text embedding with additional features."""
        
        # Ensure consistent dimensions
        combined_size = max(len(embedding1), self.standard_dim)
        combined = np.zeros(combined_size)
        
        # Copy main embedding
        combined[:len(embedding1)] = embedding1
        
        # Add features with reduced weight
        feature_weight = 0.3
        feature_indices = np.arange(len(features)) * (combined_size // max(len(features), 1))
        
        for i, feature in enumerate(features):
            if i < len(feature_indices) and feature_indices[i] < combined_size:
                combined[feature_indices[i]] += feature * feature_weight
        
        # Normalize
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm
        
        return combined

class SimpleCrossModalSimilarityCalculator:
    """Calculate similarity between embeddings using basic numpy operations."""
    
    def __init__(self):
        """Initialize similarity calculator."""
        logger.info("Simple cross-modal similarity calculator initialized")
    
    def calculate_cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        
        try:
            # Ensure same dimensions
            if len(embedding1) != len(embedding2):
                min_dim = min(len(embedding1), len(embedding2))
                embedding1 = embedding1[:min_dim]
                embedding2 = embedding2[:min_dim]
            
            # Calculate cosine similarity
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Cosine similarity calculation failed: {e}")
            return 0.0
    
    def calculate_similarity(
        self, 
        embedding1: EmbeddingVector, 
        embedding2: EmbeddingVector,
        method: str = "cosine"
    ) -> CrossModalSimilarity:
        """Calculate similarity between two embedding vectors."""
        
        try:
            if method == "cosine":
                similarity = self.calculate_cosine_similarity(embedding1.embedding, embedding2.embedding)
            else:
                # Default to cosine
                similarity = self.calculate_cosine_similarity(embedding1.embedding, embedding2.embedding)
            
            # Apply cross-modal penalty
            is_cross_modal = embedding1.content_type != embedding2.content_type
            if is_cross_modal:
                similarity *= 0.8  # Slight penalty for cross-modal similarity
            
            return CrossModalSimilarity(
                content_id_1=embedding1.content_id,
                content_id_2=embedding2.content_id,
                content_type_1=embedding1.content_type,
                content_type_2=embedding2.content_type,
                similarity_score=similarity,
                method=method,
                is_cross_modal=is_cross_modal,
                metadata={
                    "model1": embedding1.model_name,
                    "model2": embedding2.model_name,
                    "confidence1": embedding1.confidence,
                    "confidence2": embedding2.confidence
                }
            )
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return CrossModalSimilarity(
                content_id_1=embedding1.content_id,
                content_id_2=embedding2.content_id,
                content_type_1=embedding1.content_type,
                content_type_2=embedding2.content_type,
                similarity_score=0.0,
                method=f"{method}_failed",
                is_cross_modal=True,
                metadata={"error": str(e)}
            )

class SimpleCrossModalSearchEngine:
    """Simplified cross-modal search engine."""
    
    def __init__(self):
        """Initialize search engine."""
        self.embedding_generator = SimpleCrossModalEmbeddingGenerator()
        self.similarity_calculator = SimpleCrossModalSimilarityCalculator()
        self.embeddings = {}  # content_id -> EmbeddingVector
        self.content_index = {}  # content_type -> List[content_id]
        
        logger.info("Simple cross-modal search engine initialized")
    
    async def index_multimodal_content(self, contents: List[MultimodalContent]):
        """Index multimodal content for cross-modal search."""
        
        logger.info(f"Indexing {len(contents)} multimodal content items")
        
        for content in contents:
            try:
                # Generate appropriate embedding based on content type
                if content.content_type in [ContentType.TEXT]:
                    embedding = await self.embedding_generator.generate_text_embedding(
                        content.text_content or content.description
                    )
                
                elif content.content_type in [ContentType.IMAGE, ContentType.DIAGRAM]:
                    # Extract image properties from metadata
                    image_props = {}
                    if hasattr(content.metadata, 'width'):
                        image_props.update({
                            'width': content.metadata.width,
                            'height': content.metadata.height,
                            'color_mode': content.metadata.color_mode,
                            'file_size': content.metadata.file_size
                        })
                    
                    embedding = await self.embedding_generator.generate_image_embedding(
                        content.description or content.text_content,
                        image_props
                    )
                
                elif content.content_type == ContentType.TABLE:
                    embedding = await self.embedding_generator.generate_table_embedding(
                        content.table_data,
                        content.description or content.text_content
                    )
                
                else:
                    # Fallback to text embedding
                    embedding = await self.embedding_generator.generate_text_embedding(
                        content.text_content or content.description or "Unknown content"
                    )
                
                # Update content ID and content type
                embedding.content_id = content.content_id
                embedding.content_type = content.content_type
                
                # Store embedding
                self.embeddings[content.content_id] = embedding
                
                # Update content type index
                if content.content_type not in self.content_index:
                    self.content_index[content.content_type] = []
                
                if content.content_id not in self.content_index[content.content_type]:
                    self.content_index[content.content_type].append(content.content_id)
                
            except Exception as e:
                logger.error(f"Failed to index content {content.content_id}: {e}")
        
        logger.info(f"Successfully indexed {len(self.embeddings)} embeddings")
    
    async def cross_modal_search(
        self, 
        query: str, 
        content_types: Optional[List[ContentType]] = None,
        top_k: int = 10
    ) -> List[SearchResult]:
        """Perform cross-modal search using embeddings."""
        
        logger.info(f"Cross-modal search for: '{query}'")
        
        try:
            # Generate query embedding
            query_embedding = await self.embedding_generator.generate_text_embedding(query)
            
            # Get candidate embeddings
            candidates = []
            if content_types:
                for content_type in content_types:
                    content_ids = self.content_index.get(content_type, [])
                    for content_id in content_ids:
                        if content_id in self.embeddings:
                            candidates.append(self.embeddings[content_id])
            else:
                candidates = list(self.embeddings.values())
            
            # Calculate similarities
            similarities = []
            for candidate in candidates:
                similarity = self.similarity_calculator.calculate_similarity(
                    query_embedding, candidate
                )
                similarities.append((candidate, similarity.similarity_score))
            
            # Sort by similarity
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Convert to SearchResult objects
            results = []
            for embedding, similarity_score in similarities[:top_k]:
                result = SearchResult(
                    content=f"Content ID: {embedding.content_id}",
                    document_name="cross_modal_search",
                    metadata={
                        "content_id": embedding.content_id,
                        "content_type": embedding.content_type.value,
                        "embedding_model": embedding.model_name,
                        "embedding_confidence": embedding.confidence,
                        "similarity_method": "cross_modal_embedding"
                    },
                    score=similarity_score,
                    method="cross_modal_embedding",
                    confidence=embedding.confidence * similarity_score
                )
                results.append(result)
            
            logger.info(f"Cross-modal search completed: {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Cross-modal search failed: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the embedding system."""
        
        content_type_counts = {}
        model_counts = {}
        confidences = []
        
        for embedding in self.embeddings.values():
            # Content type distribution
            content_type = embedding.content_type.value
            content_type_counts[content_type] = content_type_counts.get(content_type, 0) + 1
            
            # Model distribution
            model_name = embedding.model_name
            model_counts[model_name] = model_counts.get(model_name, 0) + 1
            
            # Confidence tracking
            confidences.append(embedding.confidence)
        
        return {
            "total_embeddings": len(self.embeddings),
            "content_type_distribution": content_type_counts,
            "model_distribution": model_counts,
            "average_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "embedding_generator": {
                "primary_model": self.embedding_generator.primary_model.value,
                "cache_size": len(self.embedding_generator.embedding_cache),
                "standard_dimension": self.embedding_generator.standard_dim
            }
        }

# Testing and usage example
async def main():
    """Main function for testing cross-modal embeddings system."""
    
    logger.info("🚀 Starting Cross-Modal Embeddings System Test (Simplified)")
    
    # Initialize search engine
    search_engine = SimpleCrossModalSearchEngine()
    
    # Create mock multimodal content for testing
    mock_contents = []
    
    if PHASE3A_AVAILABLE:
        # Use Phase 3A types
        text_content = MultimodalContent(
            content_id="text_001",
            content_type=ContentType.TEXT,
            text_content="Network configuration for router setup with TCP/IP protocol settings",
            description="Network configuration document"
        )
        
        image_metadata = ImageMetadata(
            image_id="img_001",
            source_document="test.pdf",
            page_number=1,
            position=(100, 100, 400, 300),
            content_type=ContentType.DIAGRAM,
            width=300,
            height=200,
            file_size=1024,
            color_mode="RGB",
            description="Network diagram showing router connections"
        )
        
        image_content = MultimodalContent(
            content_id="img_001",
            content_type=ContentType.DIAGRAM,
            text_content="Network diagram showing router connections",
            metadata=image_metadata,
            description="Network topology diagram"
        )
        
        table_df = pd.DataFrame({
            'Parameter': ['IP Address', 'Subnet Mask', 'Gateway'],
            'Value': ['192.168.1.1', '255.255.255.0', '192.168.1.254']
        })
        
        table_metadata = TableMetadata(
            table_id="table_001",
            source_document="test.pdf",
            page_number=2,
            position=(50, 200, 500, 400),
            rows=3,
            columns=2,
            has_headers=True,
            summary="Network configuration parameters"
        )
        
        table_content = MultimodalContent(
            content_id="table_001",
            content_type=ContentType.TABLE,
            text_content="Network configuration: IP Address, Subnet Mask, Gateway",
            table_data=table_df,
            metadata=table_metadata,
            description="Network configuration table"
        )
        
        mock_contents = [text_content, image_content, table_content]
    
    else:
        logger.warning("Phase 3A not available, skipping content creation")
    
    # Index content
    if mock_contents:
        await search_engine.index_multimodal_content(mock_contents)
    
    # Test cross-modal search
    test_queries = [
        "network configuration",
        "router diagram", 
        "IP address table",
        "TCP protocol setup"
    ]
    
    for query in test_queries:
        logger.info(f"Testing cross-modal search: '{query}'")
        
        try:
            results = await search_engine.cross_modal_search(query, top_k=5)
            
            logger.info(f"Query: '{query}' -> {len(results)} results")
            
            for i, result in enumerate(results[:3]):
                logger.info(f"  Result {i+1}: {result.metadata.get('content_type', 'unknown')} "
                           f"(score: {result.score:.3f}, confidence: {result.confidence:.3f})")
            
        except Exception as e:
            logger.error(f"Cross-modal search test failed for '{query}': {e}")
    
    # Get statistics
    stats = search_engine.get_statistics()
    logger.info(f"Cross-modal embedding statistics:")
    logger.info(f"  Total embeddings: {stats['total_embeddings']}")
    logger.info(f"  Content types: {list(stats['content_type_distribution'].keys())}")
    logger.info(f"  Average confidence: {stats['average_confidence']:.3f}")
    logger.info(f"  Primary model: {stats['embedding_generator']['primary_model']}")
    
    logger.info("Cross-modal embeddings system test completed successfully")

if __name__ == "__main__":
    asyncio.run(main())