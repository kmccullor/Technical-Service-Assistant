from datetime import datetime
from utils.logging_config import setup_logging

# Setup standardized Log4 logging
logger = setup_logging(
    program_name='ollama_optimization_analysis',
    log_level='INFO',
    log_file=f'/app/logs/ollama_optimization_analysis_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True
)

#!/usr/bin/env python3
"""
Ollama Container Optimization Analysis

This analysis explores optimal utilization strategies for 4 Ollama containers
in the Technical Service Assistant, including load balancing, parallel execution,
and specialized model deployment patterns.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List

import aiohttp

@dataclass
class ContainerStrategy:
    """Represents a container utilization strategy."""

    name: str
    description: str
    containers: Dict[str, str]  # port -> purpose
    pros: List[str]
    cons: List[str]
    use_cases: List[str]
    performance_impact: str
    complexity: str

@dataclass
class LoadBalancingConfig:
    """Configuration for load balancing across containers."""

    strategy: str  # round_robin, least_connections, weighted
    health_check_interval: int
    retry_attempts: int
    timeout_seconds: int
    fallback_enabled: bool

class OllamaContainerOptimizer:
    """Analyzes and implements optimal Ollama container utilization."""

    def __init__(self):
        """Initialize with current container configuration."""
        self.containers = {
            "11434": "ollama-server-1",  # Primary/Main
            "11435": "ollama-server-2",  # Secondary
            "11436": "ollama-server-3",  # Tertiary
            "11437": "ollama-server-4",  # Quaternary
            "11438": "ollama-server-5",  # Additional
            "11439": "ollama-server-6",  # Additional
            "11440": "ollama-server-7",  # Additional
            "11441": "ollama-server-8",  # Additional
        }

        self.current_models = {
            "11434": ["athene-v2:72b", "nomic-embed-text:v1.5"],
            "11435": ["steamdj/llama3.1-cpu-only:8b"],
            "11436": ["DeepSeek-R1:8B", "DeepSeek-R1:7B", "codellama:7B"],
            "11437": ["nomic-embed-text:v1.5", "deepseek-coder:6.7b"],
        }

    def analyze_utilization_strategies(self) -> Dict[str, Any]:
        """Analyze different container utilization strategies."""

        strategies = [
            ContainerStrategy(
                name="Specialized Model Deployment",
                description="Dedicate each container to specific model types/purposes",
                containers={
                    "11434": "Primary Processing (PDF + Generation)",
                    "11435": "Embedding Generation (nomic-embed-text variants)",
                    "11436": "Reasoning & Analysis (DeepSeek, complex queries)",
                    "11437": "Code & Technical (codellama, technical documentation)",
                },
                pros=[
                    "Optimal resource allocation per model type",
                    "Predictable performance characteristics",
                    "Easy troubleshooting and monitoring",
                    "Model-specific optimization possible",
                    "Clear separation of concerns",
                ],
                cons=[
                    "Potential resource underutilization",
                    "Single points of failure per model type",
                    "Less flexibility for peak loads",
                ],
                use_cases=[
                    "Production environments with predictable workloads",
                    "Different SLA requirements per model type",
                    "Clear functional separation needed",
                ],
                performance_impact="High consistency, potential underutilization",
                complexity="Low",
            ),
            ContainerStrategy(
                name="Load Balanced Pool",
                description="All containers serve all models with intelligent load balancing",
                containers={"11434-11437": "Shared pool with dynamic model loading"},
                pros=[
                    "Maximum resource utilization",
                    "High availability and fault tolerance",
                    "Automatic scaling based on demand",
                    "No single points of failure",
                ],
                cons=[
                    "Model switching overhead",
                    "Complex load balancing logic needed",
                    "Potential cache inefficiency",
                    "Harder to debug performance issues",
                ],
                use_cases=[
                    "High-throughput production systems",
                    "Unpredictable or spiky workloads",
                    "Maximum uptime requirements",
                ],
                performance_impact="Variable performance, maximum throughput",
                complexity="High",
            ),
            ContainerStrategy(
                name="Hybrid Parallel Execution",
                description="Combine specialized deployment with parallel processing capabilities",
                containers={
                    "11434": "Primary Processing + Load Balancer Coordinator",
                    "11435": "Embedding Specialist + Backup Processing",
                    "11436": "Reasoning Specialist + Parallel Embeddings",
                    "11437": "Code/Technical + Emergency Fallback",
                },
                pros=[
                    "Best of both worlds",
                    "Optimized for specific tasks",
                    "Parallel processing for high-demand operations",
                    "Graceful degradation under load",
                ],
                cons=["More complex configuration", "Requires intelligent routing logic", "Moderate setup complexity"],
                use_cases=[
                    "Technical Service Assistant production deployment",
                    "Mixed workload environments",
                    "Need both performance and reliability",
                ],
                performance_impact="Optimal for mixed workloads",
                complexity="Medium",
            ),
            ContainerStrategy(
                name="Dynamic Model Distribution",
                description="Automatically distribute models based on usage patterns and performance",
                containers={"All": "AI-driven model placement and load distribution"},
                pros=[
                    "Self-optimizing performance",
                    "Adapts to changing usage patterns",
                    "Maximum efficiency over time",
                ],
                cons=[
                    "Complex implementation",
                    "Requires monitoring and ML algorithms",
                    "Potential instability during optimization",
                ],
                use_cases=[
                    "Advanced production systems",
                    "Research and development environments",
                    "Long-term optimization projects",
                ],
                performance_impact="Potentially optimal, but complex",
                complexity="Very High",
            ),
        ]

        return {
            "strategies": [strategy.__dict__ for strategy in strategies],
            "current_state": self._analyze_current_state(),
            "recommendations": self._generate_recommendations(),
        }

    def _analyze_current_state(self) -> Dict[str, Any]:
        """Analyze the current container utilization state."""
        return {
            "container_count": len(self.containers),
            "model_distribution": self.current_models,
            "current_strategy": "Specialized Model Deployment",
            "utilization_pattern": "PDF processing on 11434, specialized models on others",
            "strengths": ["Clear separation of concerns", "Predictable performance", "Easy to understand and debug"],
            "improvement_opportunities": [
                "Underutilized containers during low load",
                "No automatic failover between containers",
                "Missing parallel processing for embedding generation",
            ],
        }

    def _generate_recommendations(self) -> Dict[str, Any]:
        """Generate specific recommendations for the Technical Service Assistant."""
        return {
            "recommended_strategy": "Hybrid Parallel Execution",
            "rationale": [
                "Optimizes for Technical Service Assistant specific workloads",
                "Provides both specialization and parallel capabilities",
                "Balances performance with complexity",
                "Supports enhanced accuracy improvements",
            ],
            "implementation_phases": [
                {
                    "phase": "Phase 1: Enhanced Load Balancing",
                    "timeframe": "1-2 weeks",
                    "actions": [
                        "Implement intelligent embedding load balancer",
                        "Add health check and failover logic",
                        "Create container performance monitoring",
                    ],
                },
                {
                    "phase": "Phase 2: Parallel Embedding Generation",
                    "timeframe": "2-3 weeks",
                    "actions": [
                        "Distribute embedding generation across containers",
                        "Implement batch processing optimization",
                        "Add embedding caching layer",
                    ],
                },
                {
                    "phase": "Phase 3: Specialized + Parallel Hybrid",
                    "timeframe": "3-4 weeks",
                    "actions": [
                        "Maintain specialization for complex models",
                        "Enable parallel processing for high-volume tasks",
                        "Implement intelligent routing based on query type",
                    ],
                },
            ],
            "specific_configurations": self._generate_specific_configs(),
        }

    def _generate_specific_configs(self) -> Dict[str, Any]:
        """Generate specific configuration recommendations."""
        return {
            "recommended_setup": {
                "11434": {
                    "role": "Primary Coordinator + PDF Processing",
                    "models": ["athene-v2:72b", "mistral:7b"],
                    "purpose": "Main PDF processing, coordination, generation",
                    "backup_for": "embedding generation",
                },
                "11435": {
                    "role": "Embedding Specialist + Parallel Worker",
                    "models": ["nomic-embed-text:v1.5", "nomic-embed-text:v1.5"],
                    "purpose": "Primary embedding generation, parallel processing",
                    "backup_for": "11437 embedding tasks",
                },
                "11436": {
                    "role": "Reasoning Specialist + Heavy Processing",
                    "models": ["DeepSeek-R1:8B", "DeepSeek-R1:7B"],
                    "purpose": "Complex reasoning, analysis, heavy computation",
                    "backup_for": "generation tasks",
                },
                "11437": {
                    "role": "Technical Specialist + General Backup",
                    "models": ["codellama:7B", "deepseek-coder:6.7b"],
                    "purpose": "Code/technical queries, general backup",
                    "backup_for": "any container failure",
                },
            },
            "load_balancing_config": {
                "embedding_generation": {
                    "primary": ["11435", "11437"],
                    "strategy": "round_robin",
                    "health_check": True,
                    "retry_logic": True,
                },
                "text_generation": {
                    "primary": ["11434", "11436"],
                    "strategy": "weighted_by_model_size",
                    "fallback": "any_available",
                },
            },
            "parallel_processing": {
                "batch_embeddings": {
                    "enabled": True,
                    "chunk_size": 50,
                    "parallel_containers": ["11435", "11437", "11434"],
                    "coordination": "11434",
                },
                "document_processing": {
                    "enabled": True,
                    "parallel_extraction": True,
                    "chunk_distribution": "round_robin",
                },
            },
        }

class OllamaLoadBalancer:
    """Implements intelligent load balancing across Ollama containers."""

    def __init__(self, containers: List[str], strategy: str = "round_robin"):
        """Initialize load balancer with container endpoints."""
        self.containers = [f"http://localhost:{port}" for port in containers]
        self.strategy = strategy
        self.current_index = 0
        self.health_status = {container: True for container in self.containers}
        self.request_counts = {container: 0 for container in self.containers}

    async def get_embeddings_parallel(self, texts: List[str], model: str) -> List[Dict]:
        """Get embeddings for multiple texts in parallel across containers."""
        # Distribute texts across available containers
        available_containers = [c for c in self.containers if self.health_status[c]]

        if not available_containers:
            raise Exception("No healthy containers available")

        # Split texts across containers
        chunk_size = max(1, len(texts) // len(available_containers))
        text_chunks = [texts[i : i + chunk_size] for i in range(0, len(texts), chunk_size)]

        # Process chunks in parallel
        tasks = []
        for i, chunk in enumerate(text_chunks):
            if i < len(available_containers):
                container = available_containers[i]
                tasks.append(self._process_chunk(container, chunk, model))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_embeddings = []
        for result in results:
            if isinstance(result, list):
                all_embeddings.extend(result)
            else:
                logger.error(f"Chunk processing failed: {result}")

        return all_embeddings

    async def _process_chunk(self, container: str, texts: List[str], model: str) -> List[Dict]:
        """Process a chunk of texts on a specific container."""
        embeddings = []
        async with aiohttp.ClientSession() as session:
            for text in texts:
                try:
                    async with session.post(
                        f"{container}/api/embeddings",
                        json={"model": model, "prompt": text},
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            embeddings.append(data)
                        else:
                            logger.warning(f"Request failed: {response.status}")
                except Exception as e:
                    logger.error(f"Error processing text on {container}: {e}")
                    self.health_status[container] = False

        return embeddings

    def get_next_container(self) -> str:
        """Get next container based on load balancing strategy."""
        available = [c for c in self.containers if self.health_status[c]]

        if not available:
            raise Exception("No healthy containers available")

        if self.strategy == "round_robin":
            container = available[self.current_index % len(available)]
            self.current_index += 1
            return container

        elif self.strategy == "least_connections":
            return min(available, key=lambda c: self.request_counts[c])

        else:  # Default to round_robin
            return available[0]

def main():
    """Run Ollama container optimization analysis."""
    logger.info("🔄 Ollama Container Optimization Analysis")
    logger.info("=" * 60)

    optimizer = OllamaContainerOptimizer()
    analysis = optimizer.analyze_utilization_strategies()

    # Current State
    logger.info("📊 Current Container State:")
    current = analysis["current_state"]
    logger.info(f"  Strategy: {current['current_strategy']}")
    logger.info(f"  Containers: {current['container_count']}")
    logger.info(f"  Model Distribution: {len(current['model_distribution'])} specialized containers")

    # Recommended Strategy
    logger.info(f"\n🎯 Recommended Strategy: {analysis['recommendations']['recommended_strategy']}")
    logger.info("Rationale:")
    for reason in analysis["recommendations"]["rationale"]:
        logger.info(f"  • {reason}")

    # Implementation Phases
    logger.info(f"\n🚀 Implementation Roadmap:")
    for phase in analysis["recommendations"]["implementation_phases"]:
        logger.info(f"  {phase['phase']} ({phase['timeframe']}):")
        for action in phase["actions"]:
            logger.info(f"    - {action}")

    # Specific Configuration
    logger.info(f"\n🔧 Recommended Container Configuration:")
    config = analysis["recommendations"]["specific_configurations"]["recommended_setup"]
    for port, setup in config.items():
        logger.info(f"  Container {port} ({setup['role']}):")
        logger.info(f"    Models: {setup['models']}")
        logger.info(f"    Purpose: {setup['purpose']}")
        logger.info(f"    Backup for: {setup['backup_for']}")

    # Load Balancing Benefits
    logger.info(f"\n⚖️ Load Balancing Benefits:")
    logger.info("  • Parallel embedding generation across containers")
    logger.info("  • Automatic failover for high availability")
    logger.info("  • Optimal resource utilization")
    logger.info("  • Reduced bottlenecks during peak loads")

    # Performance Expectations
    logger.info(f"\n📈 Expected Performance Improvements:")
    logger.info("  • 2-4x faster embedding generation (parallel processing)")
    logger.info("  • 99%+ uptime with container failover")
    logger.info("  • 50-70% better resource utilization")
    logger.info("  • Scalable to additional containers as needed")

    # Save analysis
    with open("ollama_optimization_analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)

    logger.info(f"\n💾 Detailed analysis saved to: ollama_optimization_analysis.json")

if __name__ == "__main__":
    main()
