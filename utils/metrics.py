"""
Performance metrics collection and monitoring utilities.
Provides Prometheus metrics for specialized model performance tracking.
"""

import logging
import time
from functools import wraps
from typing import Dict, Optional

import psutil

logger = logging.getLogger(__name__)

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server

    PROMETHEUS_AVAILABLE = True
except ImportError:
    # Graceful fallback if prometheus_client not available
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available - metrics disabled")

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class MetricsCollector:
    """Centralized metrics collection for the Technical Service Assistant."""

    def __init__(self):
        self.enabled = PROMETHEUS_AVAILABLE and getattr(settings, "enable_metrics", True)

        if self.enabled:
            # Create custom registry to avoid conflicts
            self.registry = CollectorRegistry()

            # Model performance metrics
            self.model_request_duration = Histogram(
                "model_request_duration_seconds",
                "Time spent processing model requests",
                ["model_name", "instance", "question_type"],
                registry=self.registry,
            )

            self.model_request_total = Counter(
                "model_requests_total",
                "Total number of model requests",
                ["model_name", "instance", "question_type", "status"],
                registry=self.registry,
            )

            # AI categorization metrics
            self.ai_categorization_duration = Histogram(
                "ai_categorization_duration_seconds",
                "Time spent on AI document categorization",
                ["document_type"],
                registry=self.registry,
            )

            self.ai_categorization_confidence = Histogram(
                "ai_categorization_confidence_score",
                "AI categorization confidence scores",
                ["document_type", "category"],
                registry=self.registry,
            )

            # Search and RAG metrics
            self.search_request_duration = Histogram(
                "search_request_duration_seconds",
                "Time spent processing search requests",
                ["search_type", "confidence_level"],
                registry=self.registry,
            )

            self.rag_confidence_scores = Histogram(
                "rag_confidence_scores", "RAG system confidence scores", ["search_method"], registry=self.registry
            )

            # System resource metrics
            self.system_memory_usage = Gauge(
                "system_memory_usage_percent", "System memory usage percentage", registry=self.registry
            )

            self.system_cpu_usage = Gauge(
                "system_cpu_usage_percent", "System CPU usage percentage", registry=self.registry
            )

            # Instance health metrics
            self.ollama_instance_health = Gauge(
                "ollama_instance_health_status",
                "Ollama instance health status (1=healthy, 0=unhealthy)",
                ["instance_name", "instance_url"],
                registry=self.registry,
            )

            self.ollama_instance_response_time = Histogram(
                "ollama_instance_response_time_seconds",
                "Ollama instance response times",
                ["instance_name"],
                registry=self.registry,
            )

            # API endpoint metrics
            self.api_request_duration = Histogram(
                "api_request_duration_seconds",
                "API endpoint request duration",
                ["endpoint", "method", "status_code"],
                registry=self.registry,
            )

            # Document processing metrics
            self.document_processing_duration = Histogram(
                "document_processing_duration_seconds",
                "Time spent processing documents",
                ["document_type", "processing_stage"],
                registry=self.registry,
            )

            # Quality metrics
            self.response_quality_score = Histogram(
                "response_quality_score",
                "Response quality assessment scores",
                ["model_name", "question_type"],
                registry=self.registry,
            )

            logger.info("Metrics collector initialized with Prometheus support")
        else:
            logger.warning("Metrics collector initialized in disabled mode")

    def record_model_request(
        self, model_name: str, instance: str, question_type: str, duration: float, status: str = "success"
    ):
        """Record metrics for model requests."""
        if not self.enabled:
            return

        self.model_request_duration.labels(
            model_name=model_name, instance=instance, question_type=question_type
        ).observe(duration)

        self.model_request_total.labels(
            model_name=model_name, instance=instance, question_type=question_type, status=status
        ).inc()

    def record_ai_categorization(self, document_type: str, duration: float, confidence: float, category: str):
        """Record AI categorization performance metrics."""
        if not self.enabled:
            return

        self.ai_categorization_duration.labels(document_type=document_type).observe(duration)
        self.ai_categorization_confidence.labels(document_type=document_type, category=category).observe(confidence)

    def record_search_request(self, search_type: str, duration: float, confidence_level: str):
        """Record search request metrics."""
        if not self.enabled:
            return

        self.search_request_duration.labels(search_type=search_type, confidence_level=confidence_level).observe(
            duration
        )

    def record_rag_confidence(self, confidence: float, search_method: str):
        """Record RAG confidence scores."""
        if not self.enabled:
            return

        self.rag_confidence_scores.labels(search_method=search_method).observe(confidence)

    def update_system_metrics(self):
        """Update system resource metrics."""
        if not self.enabled:
            return

        try:
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.percent)

            # CPU usage (1-second sample)
            cpu_usage = psutil.cpu_percent(interval=1)
            self.system_cpu_usage.set(cpu_usage)

        except Exception as e:
            logger.warning(f"Failed to update system metrics: {e}")

    def record_ollama_health(
        self, instance_name: str, instance_url: str, is_healthy: bool, response_time: Optional[float] = None
    ):
        """Record Ollama instance health metrics."""
        if not self.enabled:
            return

        self.ollama_instance_health.labels(instance_name=instance_name, instance_url=instance_url).set(
            1 if is_healthy else 0
        )

        if response_time is not None:
            self.ollama_instance_response_time.labels(instance_name=instance_name).observe(response_time)

    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """Record API request metrics."""
        if not self.enabled:
            return

        self.api_request_duration.labels(endpoint=endpoint, method=method, status_code=str(status_code)).observe(
            duration
        )

    def record_document_processing(self, document_type: str, processing_stage: str, duration: float):
        """Record document processing metrics."""
        if not self.enabled:
            return

        self.document_processing_duration.labels(
            document_type=document_type, processing_stage=processing_stage
        ).observe(duration)

    def record_response_quality(self, model_name: str, question_type: str, quality_score: float):
        """Record response quality assessment."""
        if not self.enabled:
            return

        self.response_quality_score.labels(model_name=model_name, question_type=question_type).observe(quality_score)

    def start_metrics_server(self, port: int = 9090):
        """Start Prometheus metrics HTTP server."""
        if not self.enabled:
            logger.warning("Cannot start metrics server - Prometheus not available")
            return

        try:
            start_http_server(port, registry=self.registry)
            logger.info(f"Metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")


# Global metrics collector instance
metrics_collector = MetricsCollector()


def monitor_performance(metric_name: str = None, labels: Dict[str, str] = None):
    """
    Decorator to monitor function performance.

    Args:
        metric_name: Custom metric name (optional)
        labels: Additional labels for the metric
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"

            try:
                result = kwargs
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.time() - start_time

                # Record generic performance metric
                if metric_name and metrics_collector.enabled:
                    try:
                        # Use the model_request_duration as a generic performance metric
                        final_labels = labels or {}
                        metrics_collector.model_request_duration.labels(
                            model_name=final_labels.get("model_name", "unknown"),
                            instance=final_labels.get("instance", "unknown"),
                            question_type=final_labels.get("question_type", func.__name__),
                        ).observe(duration)
                    except Exception as metric_error:
                        logger.warning(f"Failed to record metric: {metric_error}")

                # Always log performance
                logger.info(f"Performance: {func.__name__} took {duration:.3f}s (status: {status})")

        return wrapper

    return decorator


def performance_context(operation_name: str, labels: Dict[str, str] = None):
    """
    Context manager for monitoring code block performance.

    Usage:
        with performance_context("search_operation", {"search_type": "vector"}):
            # Your code here
            pass
    """

    class PerformanceContext:
        def __init__(self, name: str, labels: Dict[str, str] = None):
            self.name = name
            self.labels = labels or {}
            self.start_time = None

        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.start_time:
                duration = time.time() - self.start_time
                status = "error" if exc_type else "success"

                logger.info(f"Performance: {self.name} took {duration:.3f}s (status: {status})")

                # Record metric if enabled
                if metrics_collector.enabled:
                    try:
                        metrics_collector.model_request_duration.labels(
                            model_name=self.labels.get("model_name", "unknown"),
                            instance=self.labels.get("instance", "unknown"),
                            question_type=self.name,
                        ).observe(duration)
                    except Exception as e:
                        logger.warning(f"Failed to record context metric: {e}")

    return PerformanceContext(operation_name, labels)
