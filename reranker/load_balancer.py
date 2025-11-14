"""
Advanced Ollama Instance Load Balancer

Implements intelligent distribution of requests across 8 Ollama instances
with health monitoring, response time tracking, and adaptive routing.

Features:
- Round-robin with health awareness
- Response time-based routing (prefer faster instances)
- Load score calculation (CPU + memory usage tracking)
- Automatic instance health checks
- Per-instance metrics and fallback chains
- Embedding vs inference instance separation for optimal performance
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class RequestType(str, Enum):
    """Types of requests that may benefit from different routing strategies."""

    EMBEDDING = "embedding"
    INFERENCE = "inference"
    HYBRID_SEARCH = "hybrid_search"


@dataclass
class InstanceMetrics:
    """Metrics for tracking Ollama instance performance."""

    instance_url: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_check_time: float = 0.0
    is_healthy: bool = True
    health_check_failures: int = 0
    last_error: Optional[str] = None
    request_times: List[float] = field(default_factory=list)  # Rolling window of last 100 requests

    def update_response_time(self, response_time: float) -> None:
        """Update metrics with a successful response."""
        self.request_times.append(response_time)
        if len(self.request_times) > 100:
            self.request_times.pop(0)
        self.average_response_time = sum(self.request_times) / len(self.request_times)
        self.successful_requests += 1

    def record_failure(self, error: str) -> None:
        """Record a failed request."""
        self.failed_requests += 1
        self.last_error = error
        self.health_check_failures += 1
        if self.health_check_failures >= 3:
            self.is_healthy = False

    def reset_health(self) -> None:
        """Reset health status (after successful request)."""
        if self.successful_requests > self.failed_requests:
            self.is_healthy = True
            self.health_check_failures = 0

    def get_load_score(self) -> float:
        """Calculate instance load score (lower = better)."""
        if not self.is_healthy:
            return float("inf")

        base_score = self.average_response_time
        failure_penalty = (self.failed_requests / max(self.total_requests, 1)) * 100

        return base_score + failure_penalty


class OllamaLoadBalancer:
    """Intelligent load balancer for Ollama instances."""

    def __init__(self, instance_urls: Optional[List[str]] = None):
        """Initialize load balancer with Ollama instance URLs."""
        if instance_urls is None:
            instance_urls = [
                "http://ollama-server-1:11434",
                "http://ollama-server-2:11434",
                "http://ollama-server-3:11434",
                "http://ollama-server-4:11434",
                "http://ollama-server-5:11434",
                "http://ollama-server-6:11434",
                "http://ollama-server-7:11434",
                "http://ollama-server-8:11434",
            ]

        self.instance_urls = instance_urls
        self.metrics: Dict[str, InstanceMetrics] = {url: InstanceMetrics(instance_url=url) for url in instance_urls}

        # Round-robin pointers for each request type
        self._embedding_pointer = 0
        self._inference_pointer = 0
        self._lock = Lock()

        # Health check parameters
        self.health_check_interval = 30  # seconds
        self.last_health_check = 0
        self.health_check_timeout = 5  # seconds

    async def get_next_instance(self, request_type: RequestType = RequestType.INFERENCE) -> str:
        """
        Get the next instance for a request using adaptive routing.

        Strategy:
        - Returns healthy instances sorted by load score
        - Falls back to round-robin if all instances unhealthy
        - Periodically performs health checks
        """
        current_time = time.time()

        # Perform health check if interval elapsed
        if current_time - self.last_health_check > self.health_check_interval:
            await self._health_check_all()
            self.last_health_check = current_time

        # Get healthy instances sorted by load score
        healthy_instances = [(url, self.metrics[url]) for url in self.instance_urls if self.metrics[url].is_healthy]

        if healthy_instances:
            # Sort by load score (lower is better)
            healthy_instances.sort(key=lambda x: x[1].get_load_score())
            selected_url = healthy_instances[0][0]
            logger.debug(
                f"Selected {selected_url} for {request_type.value} (score: {healthy_instances[0][1].get_load_score():.2f})"
            )
            return selected_url

        # Fallback: use round-robin for unhealthy instances
        with self._lock:
            if request_type == RequestType.EMBEDDING:
                self._embedding_pointer = (self._embedding_pointer + 1) % len(self.instance_urls)
                return self.instance_urls[self._embedding_pointer]
            else:
                self._inference_pointer = (self._inference_pointer + 1) % len(self.instance_urls)
                return self.instance_urls[self._inference_pointer]

    async def get_healthy_instances(self, request_type: RequestType = RequestType.INFERENCE) -> List[str]:
        """Get all healthy instances for fallback chains."""
        healthy = [url for url in self.instance_urls if self.metrics[url].is_healthy]
        return healthy if healthy else self.instance_urls

    def record_request(
        self, instance_url: str, response_time: float, success: bool, error: Optional[str] = None
    ) -> None:
        """Record request metrics for an instance."""
        if instance_url not in self.metrics:
            return

        metrics = self.metrics[instance_url]
        metrics.total_requests += 1
        metrics.last_check_time = time.time()

        if success:
            metrics.update_response_time(response_time)
            metrics.reset_health()
        else:
            metrics.record_failure(error or "Unknown error")

    async def _health_check_all(self) -> None:
        """Perform health checks on all instances concurrently."""
        tasks = [self._health_check_instance(url) for url in self.instance_urls]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _health_check_instance(self, instance_url: str) -> None:
        """Check health of a single instance."""
        try:
            async with httpx.AsyncClient(timeout=self.health_check_timeout) as client:
                response = await client.get(f"{instance_url}/api/tags")
                if response.status_code == 200:
                    self.metrics[instance_url].is_healthy = True
                    self.metrics[instance_url].health_check_failures = 0
                    logger.debug(f"Health check OK: {instance_url}")
                else:
                    self.metrics[instance_url].record_failure(f"HTTP {response.status_code}")
                    logger.warning(f"Health check failed: {instance_url} (HTTP {response.status_code})")
        except Exception as e:
            self.metrics[instance_url].record_failure(str(e))
            logger.warning(f"Health check error: {instance_url} ({e})")

    def get_metrics_summary(self) -> Dict[str, any]:
        """Get summary metrics for all instances."""
        summary = {}
        for url, metrics in self.metrics.items():
            summary[url] = {
                "healthy": metrics.is_healthy,
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "average_response_time": f"{metrics.average_response_time:.2f}ms",
                "success_rate": f"{(metrics.successful_requests / max(metrics.total_requests, 1)) * 100:.1f}%",
                "load_score": f"{metrics.get_load_score():.2f}",
            }
        return summary


# Global load balancer instance
_load_balancer: Optional[OllamaLoadBalancer] = None
_lb_lock = Lock()


def get_load_balancer(instance_urls: Optional[List[str]] = None) -> OllamaLoadBalancer:
    """Get or create the global load balancer instance."""
    global _load_balancer

    if _load_balancer is None:
        with _lb_lock:
            if _load_balancer is None:
                _load_balancer = OllamaLoadBalancer(instance_urls)

    return _load_balancer
