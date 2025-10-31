#!/usr/bin/env python3
"""
Phase 3A Enhanced Multimodal System with Cross-Modal Embeddings

This module integrates cross-modal embeddings with the Phase 3A multimodal system,
providing enhanced search capabilities across text, images, and tables.

Features:
1. Enhanced multimodal search with cross-modal embeddings
2. Unified embedding space for improved relevance
3. Advanced similarity scoring across content types
4. Integration with existing Phase 3A architecture
5. Comprehensive performance monitoring and analytics
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import get_settings
from utils.logging_config import setup_logging

# Import Phase 3A and cross-modal components
try:
    from cross_modal_embeddings_simple import SimpleCrossModalSearchEngine
    from phase3a_multimodal_simple import ContentType, Phase3AMultimodalSystem, VisionModel

    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Required dependencies not available: {e}")
    DEPENDENCIES_AVAILABLE = False

# Import Phase 2C components
try:
    from phase2c_accuracy_system import AccuracyMetrics, AdvancedConfidenceScorer, Phase2CAccuracySystem, SearchResult

    PHASE2C_AVAILABLE = True
except ImportError:
    PHASE2C_AVAILABLE = False

    @dataclass
    class SearchResult:
        content: str
        document_name: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        score: float = 0.0
        method: str = "mock"
        confidence: float = 0.5

    @dataclass
    class AccuracyMetrics:
        query: str
        method: str
        results_count: int
        response_time: float
        confidence_score: float
        semantic_coverage: float = 0.0
        keyword_coverage: float = 0.0
        diversity_score: float = 0.0
        uncertainty_level: float = 0.0
        quality_indicators: Dict[str, float] = field(default_factory=dict)


# Setup logging
logger = setup_logging(
    program_name="phase3a_enhanced_multimodal",
    log_level="INFO",
    console_output=True,
)

settings = get_settings()


@dataclass
class EnhancedSearchResult:
    """Enhanced search result with cross-modal information."""

    base_result: SearchResult
    embedding_similarity: float
    cross_modal_relevance: float
    content_type_boost: float
    final_score: float
    embedding_metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedMultimodalSearchEngine:
    """Enhanced multimodal search engine with cross-modal embeddings."""

    def __init__(self):
        """Initialize enhanced search engine."""
        if not DEPENDENCIES_AVAILABLE:
            raise ImportError("Required Phase 3A and cross-modal dependencies not available")

        # Initialize components
        self.phase3a_system = Phase3AMultimodalSystem(VisionModel.BASIC)
        self.cross_modal_engine = SimpleCrossModalSearchEngine()

        # Initialize Phase 2C if available
        if PHASE2C_AVAILABLE:
            self.phase2c_system = Phase2CAccuracySystem()
            self.confidence_scorer = AdvancedConfidenceScorer()
        else:
            self.phase2c_system = None
            self.confidence_scorer = None

        # Search enhancement settings
        self.cross_modal_weight = 0.4  # Weight for cross-modal similarity
        self.embedding_weight = 0.6  # Weight for embedding similarity
        self.content_type_boosts = {
            ContentType.TEXT: 1.0,
            ContentType.IMAGE: 1.1,
            ContentType.DIAGRAM: 1.2,
            ContentType.TABLE: 1.1,
            ContentType.CHART: 1.0,
        }

        logger.info("Enhanced multimodal search engine initialized")

    async def process_and_index_document(self, pdf_path: str) -> Dict[str, Any]:
        """Process document with both Phase 3A and cross-modal indexing."""

        logger.info(f"Enhanced processing for document: {pdf_path}")
        start_time = time.time()

        try:
            # Phase 1: Process with Phase 3A system
            phase3a_summary = await self.phase3a_system.process_document_multimodal(pdf_path)

            # Phase 2: Get multimodal content for cross-modal indexing
            document_name = Path(pdf_path).name
            if document_name in self.phase3a_system.processed_documents:
                multimodal_content = self.phase3a_system.processed_documents[document_name]["multimodal_content"]

                # Phase 3: Index with cross-modal embeddings
                await self.cross_modal_engine.index_multimodal_content(multimodal_content)

                # Phase 4: Create enhanced summary
                cross_modal_stats = self.cross_modal_engine.get_statistics()

                enhanced_summary = {
                    **phase3a_summary,
                    "cross_modal_embeddings": {
                        "total_embeddings": cross_modal_stats["total_embeddings"],
                        "embedding_models": list(cross_modal_stats["model_distribution"].keys()),
                        "average_confidence": cross_modal_stats["average_confidence"],
                    },
                    "enhanced_processing_time": time.time() - start_time,
                    "enhancement_status": "completed",
                }

                logger.info(
                    f"Enhanced processing completed for {document_name}: "
                    f"{enhanced_summary['multimodal_content_total']} items, "
                    f"{enhanced_summary['cross_modal_embeddings']['total_embeddings']} embeddings"
                )

                return enhanced_summary

            else:
                logger.warning(f"Document {document_name} not found in Phase 3A processed documents")
                return {**phase3a_summary, "enhancement_status": "partial"}

        except Exception as e:
            logger.error(f"Enhanced document processing failed for {pdf_path}: {e}")
            return {
                "document_name": Path(pdf_path).name,
                "error": str(e),
                "enhancement_status": "failed",
                "processing_time": time.time() - start_time,
            }

    async def enhanced_multimodal_search(
        self,
        query: str,
        content_types: Optional[List[ContentType]] = None,
        top_k: int = 10,
        use_cross_modal: bool = True,
        use_phase2c: bool = True,
    ) -> Tuple[List[EnhancedSearchResult], AccuracyMetrics]:
        """Perform enhanced multimodal search combining multiple approaches."""

        logger.info(f"Enhanced multimodal search for: '{query}'")
        start_time = time.time()

        try:
            # Phase 1: Phase 3A multimodal search
            phase3a_results, phase3a_metrics = await self.phase3a_system.search_multimodal(
                query, content_types, top_k * 2
            )

            # Phase 2: Cross-modal embedding search
            cross_modal_results = []
            if use_cross_modal:
                cross_modal_results = await self.cross_modal_engine.cross_modal_search(query, content_types, top_k * 2)

            # Phase 3: Phase 2C accuracy search (if available)
            phase2c_results = []
            if use_phase2c and self.phase2c_system:
                try:
                    phase2c_results, _ = await self.phase2c_system.comprehensive_search(query, top_k * 2)
                except Exception as e:
                    logger.warning(f"Phase 2C search failed: {e}")

            # Phase 4: Combine and enhance results
            enhanced_results = await self._combine_and_enhance_results(
                query, phase3a_results, cross_modal_results, phase2c_results
            )

            # Phase 5: Calculate enhanced metrics
            total_time = time.time() - start_time

            # Use Phase 2C confidence scoring if available
            if self.confidence_scorer and enhanced_results:
                try:
                    base_results = [er.base_result for er in enhanced_results]
                    confidence, analysis = self.confidence_scorer.calculate_confidence(query, base_results)
                except Exception as e:
                    logger.warning(f"Confidence scoring failed: {e}")
                    confidence = 0.5
                    analysis = {}
            else:
                confidence = 0.5
                analysis = {}

            enhanced_metrics = AccuracyMetrics(
                query=query,
                method="enhanced_multimodal_search",
                results_count=len(enhanced_results),
                response_time=total_time,
                confidence_score=confidence,
                semantic_coverage=phase3a_metrics.semantic_coverage,
                keyword_coverage=phase3a_metrics.keyword_coverage,
                diversity_score=self._calculate_enhanced_diversity(enhanced_results),
                uncertainty_level=analysis.get("uncertainty_penalty", 0.0),
                quality_indicators={
                    **analysis,
                    "phase3a_results": float(len(phase3a_results)),
                    "cross_modal_results": float(len(cross_modal_results)),
                    "phase2c_results": float(len(phase2c_results)),
                    "enhancement_active": float(use_cross_modal),
                    "average_embedding_similarity": float(
                        np.mean([er.embedding_similarity for er in enhanced_results]) if enhanced_results else 0.0
                    ),
                    "average_cross_modal_relevance": float(
                        np.mean([er.cross_modal_relevance for er in enhanced_results]) if enhanced_results else 0.0
                    ),
                },
            )

            # Sort enhanced results by final score
            enhanced_results.sort(key=lambda x: x.final_score, reverse=True)

            logger.info(
                f"Enhanced multimodal search completed: {len(enhanced_results)} results, "
                f"confidence: {confidence:.3f}, time: {total_time:.3f}s"
            )

            return enhanced_results[:top_k], enhanced_metrics

        except Exception as e:
            logger.error(f"Enhanced multimodal search failed: {e}")
            return [], AccuracyMetrics(
                query=query,
                method="enhanced_multimodal_search",
                results_count=0,
                response_time=time.time() - start_time,
                confidence_score=0.0,
                semantic_coverage=0.0,
                keyword_coverage=0.0,
                diversity_score=0.0,
                uncertainty_level=1.0,
                quality_indicators={"error": 1.0},
            )

    async def _combine_and_enhance_results(
        self,
        query: str,
        phase3a_results: List[SearchResult],
        cross_modal_results: List[SearchResult],
        phase2c_results: List[SearchResult],
    ) -> List[EnhancedSearchResult]:
        """Combine results from different search methods and enhance with scores."""

        enhanced_results = []

        # Create lookup for cross-modal results
        cross_modal_lookup = {
            result.metadata.get("content_id", result.content): result for result in cross_modal_results
        }

        # Create lookup for phase2c results
        phase2c_lookup = {result.document_name + result.content[:50]: result for result in phase2c_results}

        # Process Phase 3A results as primary
        for phase3a_result in phase3a_results:
            try:
                # Find corresponding cross-modal result
                content_id = phase3a_result.metadata.get("content_id", phase3a_result.content)
                cross_modal_result = cross_modal_lookup.get(content_id)

                # Find corresponding Phase 2C result
                phase2c_key = phase3a_result.document_name + phase3a_result.content[:50]
                phase2c_result = phase2c_lookup.get(phase2c_key)

                # Calculate enhanced scores
                embedding_similarity = cross_modal_result.score if cross_modal_result else 0.0
                cross_modal_relevance = self._calculate_cross_modal_relevance(phase3a_result, cross_modal_result)

                # Content type boost
                content_type = ContentType(phase3a_result.metadata.get("content_type", "text"))
                content_type_boost = self.content_type_boosts.get(content_type, 1.0)

                # Calculate final score
                base_score = phase3a_result.score
                phase2c_score = phase2c_result.score if phase2c_result else base_score

                final_score = (
                    base_score * 0.4
                    + phase2c_score * 0.3
                    + embedding_similarity * self.embedding_weight * 0.2
                    + cross_modal_relevance * self.cross_modal_weight * 0.1
                ) * content_type_boost

                # Create enhanced result
                enhanced_result = EnhancedSearchResult(
                    base_result=phase3a_result,
                    embedding_similarity=embedding_similarity,
                    cross_modal_relevance=cross_modal_relevance,
                    content_type_boost=content_type_boost,
                    final_score=final_score,
                    embedding_metadata={
                        "has_cross_modal": cross_modal_result is not None,
                        "has_phase2c": phase2c_result is not None,
                        "content_type": content_type.value,
                    },
                )

                enhanced_results.append(enhanced_result)

            except Exception as e:
                logger.warning(f"Failed to enhance result: {e}")
                # Add basic enhanced result
                enhanced_result = EnhancedSearchResult(
                    base_result=phase3a_result,
                    embedding_similarity=0.0,
                    cross_modal_relevance=0.0,
                    content_type_boost=1.0,
                    final_score=phase3a_result.score,
                    embedding_metadata={"enhancement_failed": True},
                )
                enhanced_results.append(enhanced_result)

        return enhanced_results

    def _calculate_cross_modal_relevance(
        self, phase3a_result: SearchResult, cross_modal_result: Optional[SearchResult]
    ) -> float:
        """Calculate cross-modal relevance score."""

        if not cross_modal_result:
            return 0.0

        # Basic relevance based on confidence and content type alignment
        base_relevance = cross_modal_result.confidence

        # Boost if content types are complementary
        p3a_type = phase3a_result.metadata.get("content_type", "text")
        cm_type = cross_modal_result.metadata.get("content_type", "text")

        if p3a_type != cm_type:
            base_relevance *= 1.1  # Cross-modal bonus

        return min(base_relevance, 1.0)

    def _calculate_enhanced_diversity(self, results: List[EnhancedSearchResult]) -> float:
        """Calculate diversity score for enhanced results."""

        if not results:
            return 0.0

        # Count different content types and enhancement methods
        content_types = set()
        enhancement_methods = set()

        for result in results:
            content_type = result.base_result.metadata.get("content_type", "text")
            content_types.add(content_type)

            if result.embedding_metadata.get("has_cross_modal"):
                enhancement_methods.add("cross_modal")
            if result.embedding_metadata.get("has_phase2c"):
                enhancement_methods.add("phase2c")
            enhancement_methods.add("phase3a")

        # Diversity based on content types and enhancement methods
        content_diversity = len(content_types) / len(ContentType)
        method_diversity = len(enhancement_methods) / 3  # Max 3 methods

        return (content_diversity + method_diversity) / 2

    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the enhanced system."""

        stats = {
            "phase3a_stats": self.phase3a_system.get_multimodal_statistics(),
            "cross_modal_stats": self.cross_modal_engine.get_statistics(),
            "enhancement_config": {
                "cross_modal_weight": self.cross_modal_weight,
                "embedding_weight": self.embedding_weight,
                "content_type_boosts": {k.value: v for k, v in self.content_type_boosts.items()},
            },
            "system_capabilities": {
                "phase3a_available": True,
                "cross_modal_available": True,
                "phase2c_available": PHASE2C_AVAILABLE,
            },
            "timestamp": datetime.now().isoformat(),
        }

        return stats


# Testing and usage example
async def main():
    """Main function for testing enhanced multimodal system."""

    logger.info("🚀 Starting Enhanced Phase 3A Multimodal System Test")

    if not DEPENDENCIES_AVAILABLE:
        logger.error("Required dependencies not available, cannot run test")
        return

    try:
        # Initialize enhanced system
        enhanced_system = EnhancedMultimodalSearchEngine()

        # Test document processing
        logger.info("Testing enhanced document processing...")
        mock_pdf_path = "enhanced_test_document.pdf"

        processing_summary = await enhanced_system.process_and_index_document(mock_pdf_path)
        logger.info(f"Processing summary: {json.dumps(processing_summary, indent=2)}")

        # Test enhanced search
        logger.info("Testing enhanced multimodal search...")

        test_queries = [
            "network configuration setup",
            "router diagram topology",
            "system performance metrics table",
            "TCP/IP protocol configuration",
        ]

        for query in test_queries:
            logger.info(f"Testing enhanced search: '{query}'")

            try:
                enhanced_results, metrics = await enhanced_system.enhanced_multimodal_search(
                    query, top_k=5, use_cross_modal=True, use_phase2c=PHASE2C_AVAILABLE
                )

                logger.info(f"Query: '{query}' -> {len(enhanced_results)} enhanced results")
                logger.info(f"  Confidence: {metrics.confidence_score:.3f}")
                logger.info(f"  Response time: {metrics.response_time:.3f}s")
                logger.info(f"  Diversity score: {metrics.diversity_score:.3f}")

                # Show top results
                for i, result in enumerate(enhanced_results[:3]):
                    logger.info(
                        f"  Result {i+1}: {result.base_result.metadata.get('content_type', 'unknown')} "
                        f"(final_score: {result.final_score:.3f}, "
                        f"embedding_sim: {result.embedding_similarity:.3f})"
                    )

            except Exception as e:
                logger.error(f"Enhanced search test failed for '{query}': {e}")

        # Get comprehensive statistics
        stats = enhanced_system.get_comprehensive_statistics()
        logger.info("Enhanced system statistics:")
        logger.info(f"  Phase 3A items: {stats['phase3a_stats']['total_multimodal_items']}")
        logger.info(f"  Cross-modal embeddings: {stats['cross_modal_stats']['total_embeddings']}")
        logger.info(f"  Phase 2C available: {stats['system_capabilities']['phase2c_available']}")

        logger.info("Enhanced Phase 3A multimodal system test completed successfully")

    except Exception as e:
        logger.error(f"Enhanced system test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
