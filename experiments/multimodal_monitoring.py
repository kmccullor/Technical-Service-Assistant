#!/usr/bin/env python3
"""
Phase 3A Multimodal Monitoring Extension

This module extends the Phase 2B monitoring infrastructure to provide comprehensive
analytics and metrics for multimodal content processing, including:

1. Vision model performance tracking
2. Cross-modal embedding generation metrics
3. Content type distribution analytics
4. Search accuracy and relevance scoring
5. Processing pipeline performance monitoring
6. Resource utilization for multimodal operations

Integrates with existing Prometheus/Grafana stack to provide real-time dashboards
and alerting for multimodal system health and performance.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

try:
    from prometheus_client import Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from config import get_settings
from utils.logging_config import setup_logging

# Setup logging
logger = setup_logging(
    program_name="multimodal_monitoring",
    log_level="INFO",
    console_output=True,
)

settings = get_settings()


class MultimodalMetricType(str, Enum):
    """Types of multimodal metrics to track."""

    VISION_MODEL_LATENCY = "vision_model_latency"
    EMBEDDING_GENERATION = "embedding_generation"
    CROSS_MODAL_SIMILARITY = "cross_modal_similarity"
    CONTENT_PROCESSING = "content_processing"
    SEARCH_ACCURACY = "search_accuracy"
    CONTENT_TYPE_DISTRIBUTION = "content_type_distribution"


@dataclass
class MultimodalMetric:
    """Represents a multimodal performance metric."""

    metric_type: MultimodalMetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultimodalMetricsCollector:
    """Collects and manages multimodal performance metrics."""

    def __init__(self, enable_prometheus: bool = True):
        """Initialize multimodal metrics collector."""
        self.enable_prometheus = enable_prometheus and PROMETHEUS_AVAILABLE
        self.metrics_history = []
        self.current_session_metrics = {}

        if self.enable_prometheus:
            self._setup_prometheus_metrics()

        logger.info(f"Multimodal metrics collector initialized (Prometheus: {self.enable_prometheus})")

    def _setup_prometheus_metrics(self):
        """Setup Prometheus metrics for multimodal monitoring."""

        # Vision model performance metrics
        self.vision_model_latency = Histogram(
            "multimodal_vision_model_latency_seconds",
            "Latency of vision model inference operations",
            ["model_name", "content_type", "operation"],
        )

        self.vision_model_confidence = Histogram(
            "multimodal_vision_model_confidence",
            "Confidence scores from vision model operations",
            ["model_name", "content_type"],
        )

        # Embedding generation metrics
        self.embedding_generation_latency = Histogram(
            "multimodal_embedding_generation_seconds",
            "Time taken to generate embeddings",
            ["content_type", "model_name", "dimension"],
        )

        self.embedding_cache_hits = Counter(
            "multimodal_embedding_cache_hits_total", "Number of embedding cache hits", ["content_type"]
        )

        self.embedding_cache_misses = Counter(
            "multimodal_embedding_cache_misses_total", "Number of embedding cache misses", ["content_type"]
        )

        # Cross-modal similarity metrics
        self.cross_modal_similarity_scores = Histogram(
            "multimodal_cross_modal_similarity_score",
            "Cross-modal similarity scores between content types",
            ["content_type_1", "content_type_2", "is_cross_modal"],
        )

        self.cross_modal_search_latency = Histogram(
            "multimodal_cross_modal_search_seconds",
            "Latency of cross-modal search operations",
            ["query_type", "content_types_searched"],
        )

        # Content processing metrics
        self.content_processing_latency = Histogram(
            "multimodal_content_processing_seconds",
            "Time taken to process multimodal content",
            ["content_type", "processing_stage"],
        )

        self.content_type_distribution = Gauge(
            "multimodal_content_type_count", "Current count of content by type", ["content_type"]
        )

        # Search accuracy metrics
        self.search_accuracy_scores = Histogram(
            "multimodal_search_accuracy_score",
            "Search accuracy and relevance scores",
            ["search_method", "content_types"],
        )

        self.search_diversity_scores = Histogram(
            "multimodal_search_diversity_score", "Search result diversity scores", ["search_method"]
        )

        # System resource metrics
        self.multimodal_memory_usage = Gauge(
            "multimodal_memory_usage_bytes", "Memory usage for multimodal operations", ["component", "operation"]
        )

        self.multimodal_processing_queue_size = Gauge(
            "multimodal_processing_queue_size", "Size of multimodal processing queue", ["queue_type"]
        )

        logger.info("Prometheus metrics initialized for multimodal monitoring")

    def record_vision_model_performance(
        self, model_name: str, content_type: str, operation: str, latency: float, confidence: float
    ):
        """Record vision model performance metrics."""

        metric = MultimodalMetric(
            metric_type=MultimodalMetricType.VISION_MODEL_LATENCY,
            value=latency,
            labels={"model_name": model_name, "content_type": content_type, "operation": operation},
            metadata={"confidence": confidence},
        )

        self._record_metric(metric)

        if self.enable_prometheus:
            self.vision_model_latency.labels(
                model_name=model_name, content_type=content_type, operation=operation
            ).observe(latency)

            self.vision_model_confidence.labels(model_name=model_name, content_type=content_type).observe(confidence)

    def record_embedding_generation(
        self, content_type: str, model_name: str, dimension: int, latency: float, cache_hit: bool = False
    ):
        """Record embedding generation performance."""

        metric = MultimodalMetric(
            metric_type=MultimodalMetricType.EMBEDDING_GENERATION,
            value=latency,
            labels={"content_type": content_type, "model_name": model_name, "dimension": str(dimension)},
            metadata={"cache_hit": cache_hit},
        )

        self._record_metric(metric)

        if self.enable_prometheus:
            self.embedding_generation_latency.labels(
                content_type=content_type, model_name=model_name, dimension=str(dimension)
            ).observe(latency)

            if cache_hit:
                self.embedding_cache_hits.labels(content_type=content_type).inc()
            else:
                self.embedding_cache_misses.labels(content_type=content_type).inc()

    def record_cross_modal_similarity(
        self, content_type_1: str, content_type_2: str, similarity_score: float, is_cross_modal: bool
    ):
        """Record cross-modal similarity measurements."""

        metric = MultimodalMetric(
            metric_type=MultimodalMetricType.CROSS_MODAL_SIMILARITY,
            value=similarity_score,
            labels={
                "content_type_1": content_type_1,
                "content_type_2": content_type_2,
                "is_cross_modal": str(is_cross_modal),
            },
        )

        self._record_metric(metric)

        if self.enable_prometheus:
            self.cross_modal_similarity_scores.labels(
                content_type_1=content_type_1, content_type_2=content_type_2, is_cross_modal=str(is_cross_modal)
            ).observe(similarity_score)

    def record_search_performance(
        self,
        search_method: str,
        content_types: List[str],
        accuracy_score: float,
        diversity_score: float,
        latency: float,
    ):
        """Record search performance metrics."""

        content_types_str = ",".join(sorted(content_types))

        # Accuracy metric
        accuracy_metric = MultimodalMetric(
            metric_type=MultimodalMetricType.SEARCH_ACCURACY,
            value=accuracy_score,
            labels={"search_method": search_method, "content_types": content_types_str},
            metadata={"diversity_score": diversity_score, "latency": latency},
        )

        self._record_metric(accuracy_metric)

        if self.enable_prometheus:
            self.search_accuracy_scores.labels(search_method=search_method, content_types=content_types_str).observe(
                accuracy_score
            )

            self.search_diversity_scores.labels(search_method=search_method).observe(diversity_score)

            self.cross_modal_search_latency.labels(
                query_type=search_method, content_types_searched=content_types_str
            ).observe(latency)

    def record_content_processing(self, content_type: str, processing_stage: str, latency: float):
        """Record content processing performance."""

        metric = MultimodalMetric(
            metric_type=MultimodalMetricType.CONTENT_PROCESSING,
            value=latency,
            labels={"content_type": content_type, "processing_stage": processing_stage},
        )

        self._record_metric(metric)

        if self.enable_prometheus:
            self.content_processing_latency.labels(
                content_type=content_type, processing_stage=processing_stage
            ).observe(latency)

    def update_content_type_distribution(self, content_type_counts: Dict[str, int]):
        """Update content type distribution metrics."""

        for content_type, count in content_type_counts.items():
            metric = MultimodalMetric(
                metric_type=MultimodalMetricType.CONTENT_TYPE_DISTRIBUTION,
                value=float(count),
                labels={"content_type": content_type},
            )

            self._record_metric(metric)

            if self.enable_prometheus:
                self.content_type_distribution.labels(content_type=content_type).set(count)

    def record_resource_usage(self, component: str, operation: str, memory_bytes: int):
        """Record resource usage for multimodal operations."""

        if self.enable_prometheus:
            self.multimodal_memory_usage.labels(component=component, operation=operation).set(memory_bytes)

    def _record_metric(self, metric: MultimodalMetric):
        """Internal method to record metrics in history."""

        self.metrics_history.append(metric)

        # Update session metrics
        metric_key = f"{metric.metric_type.value}_{metric.labels.get('content_type', 'all')}"
        if metric_key not in self.current_session_metrics:
            self.current_session_metrics[metric_key] = []

        self.current_session_metrics[metric_key].append(metric.value)

        # Keep only recent history (last 1000 metrics)
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session metrics."""

        summary = {
            "session_start": datetime.now().isoformat(),
            "total_metrics_recorded": len(self.metrics_history),
            "metrics_by_type": {},
            "performance_summary": {},
        }

        # Count metrics by type
        for metric in self.metrics_history:
            metric_type = metric.metric_type.value
            if metric_type not in summary["metrics_by_type"]:
                summary["metrics_by_type"][metric_type] = 0
            summary["metrics_by_type"][metric_type] += 1

        # Calculate performance summary
        for metric_key, values in self.current_session_metrics.items():
            if values:
                summary["performance_summary"][metric_key] = {
                    "count": len(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }

        return summary

    def export_prometheus_metrics(self) -> str:
        """Export Prometheus metrics in text format."""

        if not self.enable_prometheus:
            return "# Prometheus not available\n"

        # This would normally use generate_latest() but we'll return a summary
        return f"# Multimodal metrics exported at {datetime.now().isoformat()}\n"


class MultimodalMonitoringIntegration:
    """Integrates multimodal monitoring with existing Phase 2B infrastructure."""

    def __init__(self):
        """Initialize multimodal monitoring integration."""
        self.metrics_collector = MultimodalMetricsCollector()
        self.monitoring_active = True

        logger.info("Multimodal monitoring integration initialized")

    def instrument_vision_model(self, vision_model_manager):
        """Add monitoring instrumentation to vision model manager."""

        original_describe_image = vision_model_manager.describe_image

        async def monitored_describe_image(image, context=""):
            start_time = time.time()
            try:
                description, confidence = await original_describe_image(image, context)
                latency = time.time() - start_time

                self.metrics_collector.record_vision_model_performance(
                    model_name=vision_model_manager.model_name.value,
                    content_type="image",
                    operation="describe_image",
                    latency=latency,
                    confidence=confidence,
                )

                return description, confidence
            except Exception:
                latency = time.time() - start_time
                self.metrics_collector.record_vision_model_performance(
                    model_name=vision_model_manager.model_name.value,
                    content_type="image",
                    operation="describe_image_failed",
                    latency=latency,
                    confidence=0.0,
                )
                raise

        vision_model_manager.describe_image = monitored_describe_image
        logger.info("Vision model instrumented with monitoring")

    def instrument_embedding_generator(self, embedding_generator):
        """Add monitoring instrumentation to embedding generator."""

        original_generate_text_embedding = embedding_generator.generate_text_embedding

        async def monitored_generate_text_embedding(text):
            start_time = time.time()
            cache_key = f"{text}_{embedding_generator.primary_model.value}"
            cache_hit = cache_key in embedding_generator.embedding_cache

            try:
                result = await original_generate_text_embedding(text)
                latency = time.time() - start_time

                self.metrics_collector.record_embedding_generation(
                    content_type="text",
                    model_name=embedding_generator.primary_model.value,
                    dimension=result.embedding_dim,
                    latency=latency,
                    cache_hit=cache_hit,
                )

                return result
            except Exception:
                latency = time.time() - start_time
                self.metrics_collector.record_embedding_generation(
                    content_type="text",
                    model_name=f"{embedding_generator.primary_model.value}_failed",
                    dimension=0,
                    latency=latency,
                    cache_hit=False,
                )
                raise

        embedding_generator.generate_text_embedding = monitored_generate_text_embedding
        logger.info("Embedding generator instrumented with monitoring")

    def instrument_search_engine(self, search_engine):
        """Add monitoring instrumentation to multimodal search engine."""

        original_cross_modal_search = search_engine.cross_modal_search

        async def monitored_cross_modal_search(query, content_types=None, top_k=10):
            start_time = time.time()

            try:
                results = await original_cross_modal_search(query, content_types, top_k)
                latency = time.time() - start_time

                # Calculate metrics
                if results:
                    accuracy_score = sum(r.confidence for r in results) / len(results)
                    content_types_found = list(set(r.metadata.get("content_type", "unknown") for r in results))
                    diversity_score = len(content_types_found) / max(len(results), 1)
                else:
                    accuracy_score = 0.0
                    content_types_found = []
                    diversity_score = 0.0

                content_types_searched = content_types or ["all"]
                if isinstance(content_types_searched[0], object):  # Handle ContentType enum
                    content_types_searched = [ct.value for ct in content_types_searched]

                self.metrics_collector.record_search_performance(
                    search_method="cross_modal_search",
                    content_types=content_types_searched,
                    accuracy_score=accuracy_score,
                    diversity_score=diversity_score,
                    latency=latency,
                )

                return results
            except Exception:
                latency = time.time() - start_time
                self.metrics_collector.record_search_performance(
                    search_method="cross_modal_search_failed",
                    content_types=content_types or ["unknown"],
                    accuracy_score=0.0,
                    diversity_score=0.0,
                    latency=latency,
                )
                raise

        search_engine.cross_modal_search = monitored_cross_modal_search
        logger.info("Search engine instrumented with monitoring")

    def record_similarity_calculation(self, similarity_result):
        """Record cross-modal similarity calculation results."""

        self.metrics_collector.record_cross_modal_similarity(
            content_type_1=similarity_result.content_type_1.value,
            content_type_2=similarity_result.content_type_2.value,
            similarity_score=similarity_result.similarity_score,
            is_cross_modal=similarity_result.is_cross_modal,
        )

    def update_system_statistics(self, statistics: Dict[str, Any]):
        """Update system-wide multimodal statistics."""

        # Update content type distribution
        if "content_type_distribution" in statistics:
            self.metrics_collector.update_content_type_distribution(statistics["content_type_distribution"])

        # Record resource usage if available
        if "memory_usage" in statistics:
            for component, usage in statistics["memory_usage"].items():
                self.metrics_collector.record_resource_usage(
                    component=component, operation="current_usage", memory_bytes=usage
                )

    def get_monitoring_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboards."""

        session_summary = self.metrics_collector.get_session_summary()

        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "monitoring_status": "active" if self.monitoring_active else "inactive",
            "prometheus_enabled": self.metrics_collector.enable_prometheus,
            "session_summary": session_summary,
            "recent_metrics": {
                "vision_model_calls": len(
                    [
                        m
                        for m in self.metrics_collector.metrics_history[-100:]
                        if m.metric_type == MultimodalMetricType.VISION_MODEL_LATENCY
                    ]
                ),
                "embedding_generations": len(
                    [
                        m
                        for m in self.metrics_collector.metrics_history[-100:]
                        if m.metric_type == MultimodalMetricType.EMBEDDING_GENERATION
                    ]
                ),
                "similarity_calculations": len(
                    [
                        m
                        for m in self.metrics_collector.metrics_history[-100:]
                        if m.metric_type == MultimodalMetricType.CROSS_MODAL_SIMILARITY
                    ]
                ),
                "search_operations": len(
                    [
                        m
                        for m in self.metrics_collector.metrics_history[-100:]
                        if m.metric_type == MultimodalMetricType.SEARCH_ACCURACY
                    ]
                ),
            },
        }

        return dashboard_data


# Testing and usage example
def main():
    """Main function for testing multimodal monitoring."""

    logger.info("🚀 Testing Multimodal Monitoring Extension")

    # Initialize monitoring
    monitoring = MultimodalMonitoringIntegration()

    # Simulate some metrics
    logger.info("📊 Simulating multimodal metrics...")

    # Vision model metrics
    monitoring.metrics_collector.record_vision_model_performance(
        model_name="blip", content_type="image", operation="describe_image", latency=1.5, confidence=0.85
    )

    # Embedding generation metrics
    monitoring.metrics_collector.record_embedding_generation(
        content_type="text", model_name="ollama_embed", dimension=768, latency=0.2, cache_hit=False
    )

    # Cross-modal similarity metrics
    monitoring.metrics_collector.record_cross_modal_similarity(
        content_type_1="text", content_type_2="image", similarity_score=0.65, is_cross_modal=True
    )

    # Search performance metrics
    monitoring.metrics_collector.record_search_performance(
        search_method="cross_modal_search",
        content_types=["text", "image", "table"],
        accuracy_score=0.72,
        diversity_score=0.8,
        latency=2.1,
    )

    # Update content distribution
    monitoring.metrics_collector.update_content_type_distribution(
        {"text": 150, "image": 45, "table": 30, "diagram": 25}
    )

    # Get dashboard data
    dashboard_data = monitoring.get_monitoring_dashboard_data()

    logger.info("📈 Monitoring Dashboard Data:")
    logger.info(f"  Status: {dashboard_data['monitoring_status']}")
    logger.info(f"  Prometheus: {'enabled' if dashboard_data['prometheus_enabled'] else 'disabled'}")
    logger.info(f"  Total metrics: {dashboard_data['session_summary']['total_metrics_recorded']}")
    logger.info(f"  Recent operations:")
    for operation, count in dashboard_data["recent_metrics"].items():
        logger.info(f"    {operation}: {count}")

    logger.info("✅ Multimodal monitoring extension test completed")


if __name__ == "__main__":
    main()
