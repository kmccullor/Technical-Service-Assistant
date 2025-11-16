from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='ollama_load_balancer',
    log_level='INFO',
    log_file=f'/app/logs/ollama_load_balancer_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

#!/usr/bin/env python3
"""
Ollama Load Balancer Implementation

Intelligent load balancing and parallel processing across 4 Ollama containers
for optimal performance in the Technical Service Assistant.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

@dataclass
class ContainerHealth:
    """Health status of an Ollama container."""

    url: str
    healthy: bool
    last_check: float
    response_time: float
    error_count: int
    request_count: int

class OllamaLoadBalancer:
    """Production-ready load balancer for Ollama containers."""

    def __init__(
        self, containers: Optional[List[str]] = None, strategy: str = "round_robin", health_check_interval: int = 30
    ):
        """
        Initialize load balancer.

        Args:
            containers: List of container ports (default: ['11434', '11435', '11436', '11437'])
            strategy: Load balancing strategy ('round_robin', 'least_connections', 'response_time')
            health_check_interval: Seconds between health checks
        """
        self.containers = containers or ["11434", "11435", "11436", "11437"]
        self.strategy = strategy
        self.health_check_interval = health_check_interval

        # Initialize container health tracking
        self.health_status = {
            port: ContainerHealth(
                url=f"http://localhost:{port}",
                healthy=True,
                last_check=0,
                response_time=0,
                error_count=0,
                request_count=0,
            )
            for port in self.containers
        }

        self.current_index = 0
        self._last_health_check = 0

        # Container specialization (based on current deployment)
        self.specializations = {
            "11434": ["general", "pdf_processing", "generation"],
            "11435": ["embedding", "parallel_processing"],
            "11436": ["reasoning", "analysis", "generation"],
            "11437": ["embedding", "technical", "backup"],
        }

    def get_embeddings_parallel(self, texts: List[str], model: str = "nomic-embed-text:v1.5") -> List[Dict]:
        """
        Generate embeddings for multiple texts in parallel across containers.

        Args:
            texts: List of texts to embed
            model: Embedding model to use

        Returns:
            List of embedding results
        """
        if not texts:
            return []

        # Check health and get embedding-capable containers
        self._check_health_if_needed()
        embedding_containers = self._get_embedding_containers()

        if not embedding_containers:
            raise Exception("No healthy embedding containers available")

        # For small batches, use single container
        if len(texts) <= 5:
            container = self._select_best_container(embedding_containers, "embedding")
            return self._process_embeddings_sequential(container, texts, model)

        # For larger batches, distribute across containers
        return self._process_embeddings_parallel(embedding_containers, texts, model)

    def get_embedding(self, text: str, model: str = "nomic-embed-text:v1.5") -> Optional[Dict]:
        """Get embedding for a single text."""
        results = self.get_embeddings_parallel([text], model)
        return results[0] if results else None

    def _get_embedding_containers(self) -> List[str]:
        """Get list of healthy containers capable of embedding generation."""
        embedding_capable = []
        for port, health in self.health_status.items():
            if health.healthy and "embedding" in self.specializations.get(port, []):
                embedding_capable.append(port)

        # If no specialized embedding containers, fall back to any healthy container
        if not embedding_capable:
            embedding_capable = [port for port, health in self.health_status.items() if health.healthy]

        return embedding_capable

    def _select_best_container(self, available_containers: List[str], task_type: str = "general") -> str:
        """Select the best container based on strategy and task type."""
        if not available_containers:
            raise Exception("No available containers")

        if self.strategy == "round_robin":
            container = available_containers[self.current_index % len(available_containers)]
            self.current_index += 1
            return container

        elif self.strategy == "least_connections":
            return min(available_containers, key=lambda p: self.health_status[p].request_count)

        elif self.strategy == "response_time":
            return min(available_containers, key=lambda p: self.health_status[p].response_time or float("inf"))

        else:
            return available_containers[0]

    def _process_embeddings_sequential(self, container: str, texts: List[str], model: str) -> List[Dict]:
        """Process embeddings sequentially on a single container."""
        results = []
        container_url = self.health_status[container].url

        for text in texts:
            try:
                start_time = time.time()
                response = requests.post(
                    f"{container_url}/api/embeddings", json={"model": model, "prompt": text}, timeout=30
                )

                response_time = time.time() - start_time
                self.health_status[container].response_time = response_time
                self.health_status[container].request_count += 1

                if response.status_code == 200:
                    results.append(response.json())
                else:
                    logger.warning(f"Embedding request failed: {response.status_code}")
                    self._mark_container_error(container)

            except Exception as e:
                logger.error(f"Error getting embedding from {container}: {e}")
                self._mark_container_error(container)

        return results

    def _process_embeddings_parallel(self, containers: List[str], texts: List[str], model: str) -> List[Dict]:
        """Process embeddings in parallel across multiple containers."""
        # Distribute texts across containers
        chunk_size = max(1, len(texts) // len(containers))
        text_chunks = [texts[i : i + chunk_size] for i in range(0, len(texts), chunk_size)]

        results = []
        with ThreadPoolExecutor(max_workers=len(containers)) as executor:
            # Submit tasks
            future_to_container = {}
            for i, chunk in enumerate(text_chunks):
                if i < len(containers):
                    container = containers[i]
                    future = executor.submit(self._process_embeddings_sequential, container, chunk, model)
                    future_to_container[future] = container

            # Collect results
            for future in as_completed(future_to_container):
                container = future_to_container[future]
                try:
                    chunk_results = future.result(timeout=60)
                    results.extend(chunk_results)
                except Exception as e:
                    logger.error(f"Parallel embedding failed for {container}: {e}")
                    self._mark_container_error(container)

        return results

    def _check_health_if_needed(self):
        """Check container health if interval has passed."""
        current_time = time.time()
        if current_time - self._last_health_check > self.health_check_interval:
            self._check_all_health()
            self._last_health_check = current_time

    def _check_all_health(self):
        """Check health of all containers."""
        for port in self.containers:
            self._check_container_health(port)

    def _check_container_health(self, port: str):
        """Check health of a specific container."""
        container_url = self.health_status[port].url
        try:
            start_time = time.time()
            response = requests.get(f"{container_url}/api/tags", timeout=5)
            response_time = time.time() - start_time

            if response.status_code == 200:
                self.health_status[port].healthy = True
                self.health_status[port].response_time = response_time
                self.health_status[port].error_count = 0
            else:
                self._mark_container_error(port)

        except Exception as e:
            logger.warning(f"Health check failed for {port}: {e}")
            self._mark_container_error(port)

        self.health_status[port].last_check = time.time()

    def _mark_container_error(self, port: str):
        """Mark a container as having an error."""
        self.health_status[port].error_count += 1

        # Mark unhealthy after 3 consecutive errors
        if self.health_status[port].error_count >= 3:
            self.health_status[port].healthy = False
            logger.warning(f"Container {port} marked as unhealthy")

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status of all containers."""
        self._check_all_health()

        status = {
            "strategy": self.strategy,
            "total_containers": len(self.containers),
            "healthy_containers": sum(1 for h in self.health_status.values() if h.healthy),
            "containers": {},
        }

        for port, health in self.health_status.items():
            status["containers"][port] = {
                "healthy": health.healthy,
                "response_time": health.response_time,
                "error_count": health.error_count,
                "request_count": health.request_count,
                "specializations": self.specializations.get(port, []),
            }

        return status

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        total_requests = sum(h.request_count for h in self.health_status.values())
        avg_response_time = sum(h.response_time for h in self.health_status.values() if h.response_time > 0)
        healthy_count = sum(1 for h in self.health_status.values() if h.healthy)

        if healthy_count > 0:
            avg_response_time /= healthy_count

        return {
            "total_requests": total_requests,
            "average_response_time": avg_response_time,
            "healthy_containers": healthy_count,
            "total_containers": len(self.containers),
            "uptime_percentage": (healthy_count / len(self.containers)) * 100,
        }

def main():
    """Test the Ollama load balancer implementation."""
    logger.info("⚖️ Testing Ollama Load Balancer")
    logger.info("=" * 50)

    # Initialize load balancer
    lb = OllamaLoadBalancer(strategy="response_time")

    logger.info("🏥 Checking container health...")
    health = lb.get_health_status()
    logger.info(f"Healthy containers: {health['healthy_containers']}/{health['total_containers']}")

    for port, status in health["containers"].items():
        health_icon = "✅" if status["healthy"] else "❌"
        logger.info(f"  {health_icon} Container {port}: {status['response_time']:.3f}s, {status['specializations']}")

    # Test single embedding
    logger.info(f"\n🔍 Testing single embedding...")
    single_time = 0  # Initialize default value
    try:
        start_time = time.time()
        result = lb.get_embedding("Test embedding query")
        single_time = time.time() - start_time

        if result:
            logger.info(f"✅ Single embedding: {single_time:.3f}s")
        else:
            logger.info("❌ Single embedding failed")
    except Exception as e:
        logger.info(f"❌ Single embedding error: {e}")
        single_time = 1.0  # Default fallback for calculation

    # Test parallel embeddings
    logger.info(f"\n⚡ Testing parallel embeddings...")
    test_texts = [
        "RNI 4.16 installation requirements",
        "security configuration setup",
        "Active Directory integration",
        "hardware security module",
        "backup and restore procedures",
        "troubleshooting authentication",
        "network interface configuration",
        "user management setup",
    ]

    try:
        start_time = time.time()
        results = lb.get_embeddings_parallel(test_texts)
        parallel_time = time.time() - start_time

        logger.info(f"✅ Parallel embeddings: {len(results)} results in {parallel_time:.3f}s")
        logger.info(f"   Average per embedding: {parallel_time/len(results):.3f}s")

        # Performance comparison
        if len(results) > 0:
            estimated_sequential = single_time * len(test_texts)
            speedup = estimated_sequential / parallel_time
            logger.info(f"   Estimated speedup: {speedup:.1f}x")

    except Exception as e:
        logger.info(f"❌ Parallel embeddings error: {e}")

    # Performance stats
    logger.info(f"\n📊 Performance Statistics:")
    stats = lb.get_performance_stats()
    logger.info(f"  Total Requests: {stats['total_requests']}")
    logger.info(f"  Average Response Time: {stats['average_response_time']:.3f}s")
    logger.info(f"  System Uptime: {stats['uptime_percentage']:.1f}%")

    logger.info(f"\n💡 Load Balancing Benefits:")
    logger.info(f"  • Automatic failover between containers")
    logger.info(f"  • Parallel processing for better throughput")
    logger.info(f"  • Health monitoring and error recovery")
    logger.info(f"  • Specialized container utilization")

    # Save configuration
    config = {
        "load_balancer_config": {
            "strategy": lb.strategy,
            "containers": lb.containers,
            "specializations": lb.specializations,
        },
        "health_status": health,
        "performance_stats": stats,
    }

    with open("ollama_load_balancer_config.json", "w") as f:
        json.dump(config, f, indent=2)

    logger.info(f"\n💾 Configuration saved to: ollama_load_balancer_config.json")

if __name__ == "__main__":
    main()
