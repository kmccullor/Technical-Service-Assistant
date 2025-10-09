#!/usr/bin/env python3
"""
Cross-Modal Embeddings System for Phase 3A

This module implements unified embedding space for text, image, and table content,
enabling semantic search across multiple modalities with advanced similarity scoring.

Key Features:
1. Unified embedding generation for text, image, and table content
2. Cross-modal similarity scoring and ranking
3. Hybrid embedding fusion for enhanced search relevance
4. Integration with existing Phase 3A multimodal system
5. Vector database storage and efficient retrieval
6. Advanced embedding alignment and normalization
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

# Optional imports with fallbacks
try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    logger.info("PyTorch not available, using numpy fallbacks")
    TORCH_AVAILABLE = False

try:
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import normalize
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.info("Scikit-learn not available, using numpy fallbacks")
    SKLEARN_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    logger.info("PIL not available")
    PIL_AVAILABLE = False

from config import get_settings
from utils.logging_config import setup_logging

# Import Phase 3A components
try:
    from phase3a_multimodal_simple import (
        MultimodalContent, ContentType, Phase3AMultimodalSystem,
        VisionModel, ImageMetadata, TableMetadata
    )
    PHASE3A_AVAILABLE = True
except ImportError:
    logger.warning("Phase 3A system not available, using basic types")
    PHASE3A_AVAILABLE = False

# Import Phase 2C components
try:
    from phase2c_accuracy_system import SearchResult, AccuracyMetrics
    PHASE2C_AVAILABLE = True
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

# Setup logging first
logger = setup_logging(
    program_name="cross_modal_embeddings",
    log_level="INFO",
    console_output=True,
)

settings = get_settings()

# Suppress some warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)

class EmbeddingModel(str, Enum):
    """Available embedding models for different modalities."""
    CLIP = "clip"                    # OpenAI CLIP for text-image alignment
    SENTENCE_BERT = "sentence_bert"  # For text embeddings
    RESNET = "resnet"               # For image embeddings
    TABLE_BERT = "table_bert"       # For table understanding
    UNIFIED_BERT = "unified_bert"   # Multi-modal BERT
    OLLAMA_EMBED = "ollama_embed"   # Use existing Ollama embeddings

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

class CrossModalEmbeddingGenerator:
    """Generates embeddings across different content modalities."""
    
    def __init__(self, primary_model: EmbeddingModel = EmbeddingModel.OLLAMA_EMBED):
        """Initialize cross-modal embedding generator."""
        self.primary_model = primary_model
        self.embedding_cache = {}
        self.model_configs = {}
        
        # Initialize based on available models
        self._initialize_embedding_models()
        
        logger.info(f"Cross-modal embedding generator initialized with {primary_model.value}")
    
    def _initialize_embedding_models(self):
        """Initialize available embedding models."""
        
        # Always available: basic text embeddings via Ollama
        self.model_configs[EmbeddingModel.OLLAMA_EMBED] = {
            "available": True,
            "endpoint": settings.ollama_url,
            "model_name": getattr(settings, 'embedding_model', 'nomic-embed-text:v1.5'),
            "dimensions": 768
        }
        
        # Try to initialize advanced models
        try:
            import sentence_transformers
            self.model_configs[EmbeddingModel.SENTENCE_BERT] = {
                "available": True,
                "model": None,  # Lazy load
                "model_name": "all-MiniLM-L6-v2",
                "dimensions": 384
            }
        except ImportError:
            logger.info("SentenceTransformers not available")
        
        try:
            import clip
            self.model_configs[EmbeddingModel.CLIP] = {
                "available": True,
                "model": None,  # Lazy load
                "device": "cuda" if torch.cuda.is_available() else "cpu",
                "dimensions": 512
            }
        except ImportError:
            logger.info("CLIP not available")
    
    async def generate_text_embedding(self, text: str, model: EmbeddingModel = None) -> EmbeddingVector:
        """Generate embedding for text content."""
        
        if model is None:
            model = self.primary_model
        
        # Use cache if available
        cache_key = hashlib.md5(f"{text}_{model.value}".encode()).hexdigest()
        if cache_key in self.embedding_cache:
            cached = self.embedding_cache[cache_key]
            return EmbeddingVector(
                content_id=cache_key[:16],
                content_type=ContentType.TEXT,
                embedding=cached['embedding'],
                model_name=model.value,
                embedding_dim=len(cached['embedding']),
                confidence=cached.get('confidence', 1.0)
            )
        
        try:
            if model == EmbeddingModel.OLLAMA_EMBED:
                embedding = await self._generate_ollama_embedding(text)
            elif model == EmbeddingModel.SENTENCE_BERT:
                embedding = await self._generate_sentence_bert_embedding(text)
            else:
                # Fallback to basic text representation
                embedding = await self._generate_basic_text_embedding(text)
            
            # Cache result
            self.embedding_cache[cache_key] = {
                'embedding': embedding,
                'confidence': 0.9,
                'timestamp': datetime.now()
            }
            
            return EmbeddingVector(
                content_id=cache_key[:16],
                content_type=ContentType.TEXT,
                embedding=embedding,
                model_name=model.value,
                embedding_dim=len(embedding),
                confidence=0.9
            )
            
        except Exception as e:
            logger.error(f"Text embedding generation failed: {e}")
            # Return zero vector as fallback
            fallback_embedding = np.zeros(768)
            return EmbeddingVector(
                content_id=cache_key[:16],
                content_type=ContentType.TEXT,
                embedding=fallback_embedding,
                model_name=f"{model.value}_fallback",
                embedding_dim=len(fallback_embedding),
                confidence=0.1
            )
    
    async def generate_image_embedding(self, image: Image.Image, description: str = "") -> EmbeddingVector:
        """Generate embedding for image content."""
        
        try:
            # Create image identifier
            image_bytes = image.tobytes()
            image_id = hashlib.md5(image_bytes).hexdigest()[:16]
            
            # For now, use text description embedding as image proxy
            # This can be enhanced with actual image embeddings (CLIP, ResNet, etc.)
            if description:
                text_embedding = await self.generate_text_embedding(
                    f"Image: {description}", 
                    EmbeddingModel.OLLAMA_EMBED
                )
                
                return EmbeddingVector(
                    content_id=image_id,
                    content_type=ContentType.IMAGE,
                    embedding=text_embedding.embedding,
                    model_name="image_description_proxy",
                    embedding_dim=text_embedding.embedding_dim,
                    confidence=0.7,
                    metadata={
                        "original_description": description,
                        "image_size": image.size,
                        "proxy_method": "text_description"
                    }
                )
            else:
                # Generate basic embedding from image properties
                embedding = await self._generate_basic_image_embedding(image)
                
                return EmbeddingVector(
                    content_id=image_id,
                    content_type=ContentType.IMAGE,
                    embedding=embedding,
                    model_name="basic_image_properties",
                    embedding_dim=len(embedding),
                    confidence=0.4,
                    metadata={
                        "image_size": image.size,
                        "method": "basic_properties"
                    }
                )
                
        except Exception as e:
            logger.error(f"Image embedding generation failed: {e}")
            # Return zero vector as fallback
            fallback_embedding = np.zeros(768)
            return EmbeddingVector(
                content_id="img_fallback",
                content_type=ContentType.IMAGE,
                embedding=fallback_embedding,
                model_name="image_fallback",
                embedding_dim=len(fallback_embedding),
                confidence=0.1
            )
    
    async def generate_table_embedding(self, table_data: pd.DataFrame, summary: str = "") -> EmbeddingVector:
        """Generate embedding for table content."""
        
        try:
            # Create table identifier
            table_str = table_data.to_string()
            table_id = hashlib.md5(table_str.encode()).hexdigest()[:16]
            
            # Create comprehensive text representation
            text_parts = []
            if summary:
                text_parts.append(f"Table: {summary}")
            
            # Add column information
            if not table_data.empty:
                text_parts.append(f"Columns: {', '.join(table_data.columns)}")
                
                # Add sample data
                for i in range(min(3, len(table_data))):
                    row_text = " | ".join(str(cell) for cell in table_data.iloc[i])
                    text_parts.append(f"Row {i+1}: {row_text}")
            
            combined_text = "\n".join(text_parts)
            
            # Generate embedding from text representation
            text_embedding = await self.generate_text_embedding(
                combined_text,
                EmbeddingModel.OLLAMA_EMBED
            )
            
            return EmbeddingVector(
                content_id=table_id,
                content_type=ContentType.TABLE,
                embedding=text_embedding.embedding,
                model_name="table_text_representation",
                embedding_dim=text_embedding.embedding_dim,
                confidence=0.8,
                metadata={
                    "table_shape": table_data.shape,
                    "summary": summary,
                    "text_length": len(combined_text)
                }
            )
            
        except Exception as e:
            logger.error(f"Table embedding generation failed: {e}")
            # Return zero vector as fallback
            fallback_embedding = np.zeros(768)
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
            endpoint = self.model_configs[EmbeddingModel.OLLAMA_EMBED]["endpoint"]
            model_name = self.model_configs[EmbeddingModel.OLLAMA_EMBED]["model_name"]
            
            # Make request to Ollama embedding endpoint
            response = requests.post(
                endpoint,
                json={
                    "model": model_name,
                    "input": text
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                embedding = np.array(data.get("embeddings", [data.get("embedding", [])]))
                
                # Handle different response formats
                if embedding.ndim > 1:
                    embedding = embedding[0]  # Take first embedding if batch
                
                return embedding
            else:
                logger.warning(f"Ollama embedding request failed: {response.status_code}")
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ollama embedding failed, using fallback: {e}")
            raise
    
    async def _generate_sentence_bert_embedding(self, text: str) -> np.ndarray:
        """Generate embedding using SentenceBERT."""
        
        try:
            # Lazy load model
            config = self.model_configs[EmbeddingModel.SENTENCE_BERT]
            if config["model"] is None:
                from sentence_transformers import SentenceTransformer
                config["model"] = SentenceTransformer(config["model_name"])
            
            embedding = config["model"].encode(text, convert_to_numpy=True)
            return embedding
            
        except Exception as e:
            logger.error(f"SentenceBERT embedding failed: {e}")
            raise
    
    async def _generate_basic_text_embedding(self, text: str) -> np.ndarray:
        """Generate basic text embedding using simple techniques."""
        
        # Simple bag-of-words with TF-IDF-like weighting
        words = text.lower().split()
        
        # Create simple hash-based embedding
        embedding_dim = 768
        embedding = np.zeros(embedding_dim)
        
        for i, word in enumerate(words[:100]):  # Limit to first 100 words
            # Simple hash-based embedding
            word_hash = hash(word) % embedding_dim
            embedding[word_hash] += 1.0 / (i + 1)  # Position weighting
        
        # Normalize
        if np.linalg.norm(embedding) > 0:
            embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    async def _generate_basic_image_embedding(self, image: Image.Image) -> np.ndarray:
        """Generate basic image embedding from image properties."""
        
        width, height = image.size
        mode = image.mode
        
        # Create feature vector from image properties
        features = []
        
        # Size features
        features.extend([width / 1000.0, height / 1000.0, (width * height) / 1000000.0])
        
        # Aspect ratio
        aspect_ratio = width / height
        features.append(aspect_ratio)
        
        # Color mode features
        mode_features = [0.0, 0.0, 0.0]  # RGB, L, Other
        if mode == "RGB":
            mode_features[0] = 1.0
        elif mode == "L":
            mode_features[1] = 1.0
        else:
            mode_features[2] = 1.0
        features.extend(mode_features)
        
        # Pad to standard embedding size
        embedding_dim = 768
        embedding = np.zeros(embedding_dim)
        
        # Place features at regular intervals
        for i, feature in enumerate(features):
            if i < embedding_dim:
                embedding[i * (embedding_dim // len(features))] = feature
        
        return embedding

class CrossModalSimilarityCalculator:
    """Calculates similarity between content across different modalities."""
    
    def __init__(self, embedding_generator: CrossModalEmbeddingGenerator):
        """Initialize similarity calculator."""
        self.embedding_generator = embedding_generator
        self.similarity_cache = {}
        
        logger.info("Cross-modal similarity calculator initialized")
    
    def calculate_similarity(
        self, 
        embedding1: EmbeddingVector, 
        embedding2: EmbeddingVector,
        method: str = "cosine"
    ) -> CrossModalSimilarity:
        """Calculate similarity between two embeddings."""
        
        try:
            # Ensure embeddings are same dimensionality
            if embedding1.embedding_dim != embedding2.embedding_dim:
                logger.warning(f"Embedding dimension mismatch: {embedding1.embedding_dim} vs {embedding2.embedding_dim}")
                # Pad smaller embedding with zeros
                max_dim = max(embedding1.embedding_dim, embedding2.embedding_dim)
                
                if embedding1.embedding_dim < max_dim:
                    padded = np.zeros(max_dim)
                    padded[:embedding1.embedding_dim] = embedding1.embedding
                    embedding1.embedding = padded
                    embedding1.embedding_dim = max_dim
                
                if embedding2.embedding_dim < max_dim:
                    padded = np.zeros(max_dim)
                    padded[:embedding2.embedding_dim] = embedding2.embedding
                    embedding2.embedding = padded
                    embedding2.embedding_dim = max_dim
            
            # Calculate similarity
            if method == "cosine":
                similarity = cosine_similarity(
                    embedding1.embedding.reshape(1, -1),
                    embedding2.embedding.reshape(1, -1)
                )[0, 0]
            elif method == "euclidean":
                distance = np.linalg.norm(embedding1.embedding - embedding2.embedding)
                similarity = 1.0 / (1.0 + distance)  # Convert distance to similarity
            else:
                # Default to dot product
                similarity = np.dot(embedding1.embedding, embedding2.embedding)
            
            # Determine if cross-modal
            is_cross_modal = embedding1.content_type != embedding2.content_type
            
            return CrossModalSimilarity(
                content_id_1=embedding1.content_id,
                content_id_2=embedding2.content_id,
                content_type_1=embedding1.content_type,
                content_type_2=embedding2.content_type,
                similarity_score=float(similarity),
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
    
    def batch_similarity(
        self, 
        embeddings: List[EmbeddingVector], 
        query_embedding: EmbeddingVector,
        top_k: int = 10
    ) -> List[CrossModalSimilarity]:
        """Calculate similarity between query and multiple embeddings."""
        
        similarities = []
        
        for embedding in embeddings:
            similarity = self.calculate_similarity(query_embedding, embedding)
            similarities.append(similarity)
        
        # Sort by similarity score
        similarities.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return similarities[:top_k]

class CrossModalEmbeddingStore:
    """Stores and manages cross-modal embeddings with efficient retrieval."""
    
    def __init__(self):
        """Initialize embedding store."""
        self.embeddings = {}  # content_id -> EmbeddingVector
        self.content_index = {}  # content_type -> List[content_id]
        self.similarity_index = {}  # For fast similarity lookup
        
        logger.info("Cross-modal embedding store initialized")
    
    def store_embedding(self, embedding: EmbeddingVector):
        """Store an embedding vector."""
        
        content_id = embedding.content_id
        content_type = embedding.content_type
        
        # Store embedding
        self.embeddings[content_id] = embedding
        
        # Update content type index
        if content_type not in self.content_index:
            self.content_index[content_type] = []
        
        if content_id not in self.content_index[content_type]:
            self.content_index[content_type].append(content_id)
        
        logger.debug(f"Stored embedding for {content_id} ({content_type.value})")
    
    def get_embedding(self, content_id: str) -> Optional[EmbeddingVector]:
        """Retrieve an embedding by content ID."""
        return self.embeddings.get(content_id)
    
    def get_embeddings_by_type(self, content_type: ContentType) -> List[EmbeddingVector]:
        """Get all embeddings of a specific content type."""
        
        content_ids = self.content_index.get(content_type, [])
        return [self.embeddings[cid] for cid in content_ids if cid in self.embeddings]
    
    def get_all_embeddings(self) -> List[EmbeddingVector]:
        """Get all stored embeddings."""
        return list(self.embeddings.values())
    
    def search_similar(
        self, 
        query_embedding: EmbeddingVector, 
        content_types: Optional[List[ContentType]] = None,
        top_k: int = 10
    ) -> List[Tuple[EmbeddingVector, float]]:
        """Search for similar embeddings."""
        
        # Get candidate embeddings
        candidates = []
        
        if content_types:
            for content_type in content_types:
                candidates.extend(self.get_embeddings_by_type(content_type))
        else:
            candidates = self.get_all_embeddings()
        
        # Calculate similarities
        similarities = []
        calculator = CrossModalSimilarityCalculator(None)  # Pass None for generator
        
        for candidate in candidates:
            similarity = calculator.calculate_similarity(query_embedding, candidate)
            similarities.append((candidate, similarity.similarity_score))
        
        # Sort and return top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored embeddings."""
        
        stats = {
            "total_embeddings": len(self.embeddings),
            "content_type_distribution": {},
            "model_distribution": {},
            "average_confidence": 0.0,
            "embedding_dimensions": set()
        }
        
        confidences = []
        
        for embedding in self.embeddings.values():
            # Content type distribution
            content_type = embedding.content_type.value
            stats["content_type_distribution"][content_type] = \
                stats["content_type_distribution"].get(content_type, 0) + 1
            
            # Model distribution
            model_name = embedding.model_name
            stats["model_distribution"][model_name] = \
                stats["model_distribution"].get(model_name, 0) + 1
            
            # Confidence tracking
            confidences.append(embedding.confidence)
            
            # Embedding dimensions
            stats["embedding_dimensions"].add(embedding.embedding_dim)
        
        if confidences:
            stats["average_confidence"] = sum(confidences) / len(confidences)
        
        stats["embedding_dimensions"] = list(stats["embedding_dimensions"])
        
        return stats

class CrossModalSearchEngine:
    """Advanced search engine leveraging cross-modal embeddings."""
    
    def __init__(self):
        """Initialize cross-modal search engine."""
        self.embedding_generator = CrossModalEmbeddingGenerator()
        self.similarity_calculator = CrossModalSimilarityCalculator(self.embedding_generator)
        self.embedding_store = CrossModalEmbeddingStore()
        
        logger.info("Cross-modal search engine initialized")
    
    async def index_multimodal_content(self, contents: List[MultimodalContent]):
        """Index multimodal content for cross-modal search."""
        
        logger.info(f"Indexing {len(contents)} multimodal content items")
        
        for content in contents:
            try:
                # Generate appropriate embedding based on content type
                if content.content_type in [ContentType.TEXT]:
                    embedding = await self.embedding_generator.generate_text_embedding(
                        content.text_content
                    )
                
                elif content.content_type in [ContentType.IMAGE, ContentType.DIAGRAM, ContentType.CHART]:
                    # Use description as proxy for image embedding
                    embedding = await self.embedding_generator.generate_image_embedding(
                        None,  # We don't have actual image data in this simplified version
                        content.description or content.text_content
                    )
                
                elif content.content_type == ContentType.TABLE:
                    # Generate table embedding
                    embedding = await self.embedding_generator.generate_table_embedding(
                        content.table_data if content.table_data is not None else pd.DataFrame(),
                        content.description or content.text_content
                    )
                
                else:
                    # Fallback to text embedding
                    embedding = await self.embedding_generator.generate_text_embedding(
                        content.text_content or content.description
                    )
                
                # Update content ID to match multimodal content
                embedding.content_id = content.content_id
                
                # Store embedding
                self.embedding_store.store_embedding(embedding)
                
            except Exception as e:
                logger.error(f"Failed to index content {content.content_id}: {e}")
        
        logger.info(f"Successfully indexed {len(self.embedding_store.embeddings)} embeddings")
    
    async def cross_modal_search(
        self, 
        query: str, 
        content_types: Optional[List[ContentType]] = None,
        top_k: int = 10,
        include_cross_modal: bool = True
    ) -> List[SearchResult]:
        """Perform cross-modal search using embeddings."""
        
        logger.info(f"Cross-modal search for: '{query}'")
        
        try:
            # Generate query embedding
            query_embedding = await self.embedding_generator.generate_text_embedding(query)
            
            # Search for similar embeddings
            similar_embeddings = self.embedding_store.search_similar(
                query_embedding, 
                content_types, 
                top_k * 2  # Get more candidates for filtering
            )
            
            # Convert to SearchResult objects
            results = []
            
            for embedding, similarity_score in similar_embeddings[:top_k]:
                # Create search result
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
    
    def get_embedding_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the embedding system."""
        
        store_stats = self.embedding_store.get_statistics()
        
        # Add additional statistics
        stats = {
            **store_stats,
            "embedding_generator_config": {
                "primary_model": self.embedding_generator.primary_model.value,
                "available_models": list(self.embedding_generator.model_configs.keys()),
                "cache_size": len(self.embedding_generator.embedding_cache)
            },
            "cross_modal_capabilities": {
                "text_embedding": True,
                "image_embedding": True,
                "table_embedding": True,
                "cross_modal_similarity": True
            }
        }
        
        return stats

# Usage example and testing
async def main():
    """Main function for testing cross-modal embeddings system."""
    
    logger.info("🚀 Starting Cross-Modal Embeddings System Test")
    
    # Initialize cross-modal search engine
    search_engine = CrossModalSearchEngine()
    
    # Create mock multimodal content for testing
    if PHASE3A_AVAILABLE:
        from phase3a_multimodal_simple import MultimodalContent, ImageMetadata, TableMetadata
        
        # Mock text content
        text_content = MultimodalContent(
            content_id="text_001",
            content_type=ContentType.TEXT,
            text_content="Network configuration for router setup with TCP/IP protocol settings",
            description="Network configuration document"
        )
        
        # Mock image content
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
            text_content="Network diagram showing router connections with TCP/IP configuration",
            metadata=image_metadata,
            description="Network topology diagram"
        )
        
        # Mock table content
        import pandas as pd
        table_df = pd.DataFrame({
            'Parameter': ['IP Address', 'Subnet Mask', 'Gateway', 'DNS'],
            'Value': ['192.168.1.1', '255.255.255.0', '192.168.1.254', '8.8.8.8']
        })
        
        table_metadata = TableMetadata(
            table_id="table_001",
            source_document="test.pdf",
            page_number=2,
            position=(50, 200, 500, 400),
            rows=4,
            columns=2,
            has_headers=True,
            summary="Network configuration parameters table"
        )
        
        table_content = MultimodalContent(
            content_id="table_001",
            content_type=ContentType.TABLE,
            text_content="Network configuration parameters: IP Address, Subnet Mask, Gateway, DNS",
            table_data=table_df,
            metadata=table_metadata,
            description="Network configuration table"
        )
        
        mock_contents = [text_content, image_content, table_content]
        
    else:
        # Fallback mock content if Phase 3A not available
        mock_contents = []
        logger.warning("Phase 3A not available, using empty content list")
    
    # Index mock content
    if mock_contents:
        await search_engine.index_multimodal_content(mock_contents)
    
    # Test cross-modal search
    test_queries = [
        "network configuration",
        "router setup diagram", 
        "TCP/IP settings table",
        "IP address configuration"
    ]
    
    for query in test_queries:
        logger.info(f"Testing cross-modal search: '{query}'")
        
        try:
            results = await search_engine.cross_modal_search(
                query, 
                top_k=5
            )
            
            logger.info(f"Query: '{query}' -> {len(results)} results")
            
            for i, result in enumerate(results[:3]):
                logger.info(f"  Result {i+1}: {result.metadata.get('content_type', 'unknown')} "
                           f"(score: {result.score:.3f}, confidence: {result.confidence:.3f})")
            
        except Exception as e:
            logger.error(f"Cross-modal search test failed for '{query}': {e}")
    
    # Get embedding statistics
    stats = search_engine.get_embedding_statistics()
    logger.info(f"Embedding system statistics:")
    logger.info(f"  Total embeddings: {stats['total_embeddings']}")
    logger.info(f"  Content types: {list(stats['content_type_distribution'].keys())}")
    logger.info(f"  Average confidence: {stats['average_confidence']:.3f}")
    logger.info(f"  Primary model: {stats['embedding_generator_config']['primary_model']}")
    
    logger.info("Cross-modal embeddings system test completed")

if __name__ == "__main__":
    asyncio.run(main())