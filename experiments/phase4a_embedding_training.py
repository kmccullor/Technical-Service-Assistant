"""
Phase 4A: Custom Embedding Model Training
Domain-specific embedding models optimized for technical content.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from phase4a_ml_infrastructure import ExperimentConfig, ExperimentResult, MLPipeline, ModelConfig, ModelType
from sklearn.model_selection import train_test_split

from utils.exceptions import EmbeddingModelError
from utils.logging_setup import get_logger
from utils.monitoring import monitor_performance

logger = get_logger(__name__)


class EmbeddingModelType(Enum):
    """Types of embedding models."""

    TECHNICAL_BERT = "technical_bert"
    DOMAIN_ROBERTA = "domain_roberta"
    MULTIMODAL_CLIP = "multimodal_clip"
    GRAPH_EMBEDDING = "graph_embedding"
    SENTENCE_TRANSFORMER = "sentence_transformer"


class TechnicalDomain(Enum):
    """Technical domains for specialized embeddings."""

    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"
    NETWORK = "network"
    SOFTWARE = "software"
    CHEMICAL = "chemical"
    GENERAL_TECHNICAL = "general_technical"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding model training."""

    model_type: EmbeddingModelType
    base_model: str = "bert-base-uncased"
    embedding_dim: int = 768
    max_sequence_length: int = 512
    technical_domain: TechnicalDomain = TechnicalDomain.GENERAL_TECHNICAL
    fine_tuning_layers: int = 4
    learning_rate: float = 2e-5
    batch_size: int = 16
    num_epochs: int = 10
    warmup_steps: int = 1000
    weight_decay: float = 0.01
    dropout_rate: float = 0.1
    use_contrastive_learning: bool = True
    temperature: float = 0.07
    negative_samples: int = 5


@dataclass
class TechnicalCorpus:
    """Technical document corpus for training."""

    corpus_name: str
    domain: TechnicalDomain
    documents: List[Dict[str, Any]] = field(default_factory=list)
    vocabulary: Dict[str, int] = field(default_factory=dict)
    technical_terms: List[str] = field(default_factory=list)
    document_types: Dict[str, int] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingEvaluation:
    """Evaluation results for embedding models."""

    similarity_benchmarks: Dict[str, float] = field(default_factory=dict)
    retrieval_metrics: Dict[str, float] = field(default_factory=dict)
    clustering_metrics: Dict[str, float] = field(default_factory=dict)
    downstream_task_performance: Dict[str, float] = field(default_factory=dict)
    technical_term_accuracy: float = 0.0
    domain_specificity_score: float = 0.0


class TechnicalCorpusBuilder:
    """Builds and manages technical document corpora."""

    def __init__(self, corpus_path: str = "data/technical_corpus"):
        self.corpus_path = Path(corpus_path)
        self.corpus_path.mkdir(parents=True, exist_ok=True)
        self.corpora = {}

        logger.info(f"Technical corpus builder initialized at: {corpus_path}")

    def create_technical_corpus(
        self, corpus_name: str, domain: TechnicalDomain, document_sources: List[str] = None
    ) -> TechnicalCorpus:
        """Create a technical document corpus."""
        corpus = TechnicalCorpus(corpus_name=corpus_name, domain=domain)

        # Generate mock technical documents based on domain
        corpus.documents = self._generate_mock_documents(domain)
        corpus.technical_terms = self._extract_technical_terms(corpus.documents, domain)
        corpus.vocabulary = self._build_vocabulary(corpus.documents)
        corpus.document_types = self._analyze_document_types(corpus.documents)
        corpus.statistics = self._calculate_corpus_statistics(corpus)

        self.corpora[corpus_name] = corpus
        logger.info(f"Created technical corpus: {corpus_name} ({len(corpus.documents)} documents)")

        return corpus

    def _generate_mock_documents(self, domain: TechnicalDomain) -> List[Dict[str, Any]]:
        """Generate mock technical documents for training."""
        documents = []

        if domain == TechnicalDomain.ELECTRICAL:
            doc_templates = [
                {
                    "title": "Circuit Analysis and Design Fundamentals",
                    "content": "This document covers basic circuit analysis techniques including Ohm's law, Kirchhoff's voltage and current laws, node voltage analysis, and mesh current analysis. Topics include resistor networks, capacitor and inductor behavior, AC/DC analysis, operational amplifiers, and filter design principles.",
                    "type": "manual",
                    "technical_terms": [
                        "resistor",
                        "capacitor",
                        "inductor",
                        "operational amplifier",
                        "ohm's law",
                        "kirchhoff",
                        "AC",
                        "DC",
                        "filter",
                    ],
                    "specifications": {"voltage_range": "0-24V", "current_range": "0-5A", "frequency_range": "DC-1MHz"},
                },
                {
                    "title": "Power Electronics and Motor Control Systems",
                    "content": "Comprehensive guide to power electronic devices including MOSFETs, IGBTs, thyristors, and power diodes. Covers switching power supplies, motor drive circuits, PWM control techniques, and power factor correction methods.",
                    "type": "specification",
                    "technical_terms": [
                        "MOSFET",
                        "IGBT",
                        "thyristor",
                        "PWM",
                        "power factor",
                        "switching",
                        "motor drive",
                    ],
                    "specifications": {
                        "power_rating": "1kW-10kW",
                        "efficiency": ">95%",
                        "switching_frequency": "20kHz",
                    },
                },
            ]
        elif domain == TechnicalDomain.NETWORK:
            doc_templates = [
                {
                    "title": "Network Infrastructure Design and Implementation",
                    "content": "Guidelines for designing scalable network infrastructure including router configuration, switch management, VLAN setup, and security protocols. Covers TCP/IP addressing, routing protocols, network monitoring, and performance optimization.",
                    "type": "manual",
                    "technical_terms": [
                        "router",
                        "switch",
                        "VLAN",
                        "TCP/IP",
                        "routing protocol",
                        "network monitoring",
                        "firewall",
                    ],
                    "specifications": {"bandwidth": "1Gbps-100Gbps", "latency": "<1ms", "availability": "99.99%"},
                },
                {
                    "title": "Cybersecurity Framework and Best Practices",
                    "content": "Security implementation framework covering firewall configuration, intrusion detection systems, VPN setup, access control policies, and incident response procedures. Includes encryption protocols and security audit methodologies.",
                    "type": "specification",
                    "technical_terms": [
                        "firewall",
                        "intrusion detection",
                        "VPN",
                        "encryption",
                        "access control",
                        "incident response",
                    ],
                    "specifications": {
                        "encryption_strength": "AES-256",
                        "detection_rate": ">99%",
                        "response_time": "<5min",
                    },
                },
            ]
        else:  # GENERAL_TECHNICAL
            doc_templates = [
                {
                    "title": "Engineering Design Principles and Methodologies",
                    "content": "Fundamental engineering design principles including requirements analysis, system architecture, component selection, testing methodologies, and quality assurance procedures. Covers design optimization and lifecycle management.",
                    "type": "manual",
                    "technical_terms": [
                        "requirements analysis",
                        "system architecture",
                        "component selection",
                        "testing",
                        "quality assurance",
                    ],
                    "specifications": {
                        "design_life": "10-25 years",
                        "reliability": ">99.5%",
                        "maintenance_interval": "annual",
                    },
                },
                {
                    "title": "Technical Documentation Standards and Practices",
                    "content": "Standards for creating comprehensive technical documentation including schematic drawing conventions, specification formats, test procedures, and maintenance instructions. Covers version control and document management systems.",
                    "type": "specification",
                    "technical_terms": [
                        "schematic",
                        "specification",
                        "test procedure",
                        "maintenance",
                        "version control",
                    ],
                    "specifications": {
                        "document_format": "ISO 9001",
                        "review_cycle": "quarterly",
                        "retention_period": "7 years",
                    },
                },
            ]

        # Expand templates into multiple documents
        for i in range(50):  # Generate 50 documents per domain
            for template in doc_templates:
                doc = template.copy()
                doc["id"] = f"{domain.value}_{i}_{hash(template['title']) % 1000}"
                doc["domain"] = domain.value
                doc["length"] = len(doc["content"])
                doc["word_count"] = len(doc["content"].split())
                documents.append(doc)

        return documents

    def _extract_technical_terms(self, documents: List[Dict[str, Any]], domain: TechnicalDomain) -> List[str]:
        """Extract technical terms from documents."""
        all_terms = set()

        for doc in documents:
            if "technical_terms" in doc:
                all_terms.update(doc["technical_terms"])

        # Add domain-specific technical terms
        domain_terms = {
            TechnicalDomain.ELECTRICAL: [
                "voltage",
                "current",
                "resistance",
                "impedance",
                "frequency",
                "phase",
                "transformer",
                "generator",
                "motor",
                "relay",
                "contactor",
                "circuit breaker",
            ],
            TechnicalDomain.NETWORK: [
                "protocol",
                "packet",
                "frame",
                "header",
                "payload",
                "subnet",
                "gateway",
                "DNS",
                "DHCP",
                "NAT",
                "QoS",
                "bandwidth",
            ],
            TechnicalDomain.GENERAL_TECHNICAL: [
                "specification",
                "tolerance",
                "calibration",
                "measurement",
                "sensor",
                "actuator",
                "controller",
                "interface",
                "protocol",
                "standard",
            ],
        }

        all_terms.update(domain_terms.get(domain, []))
        return sorted(list(all_terms))

    def _build_vocabulary(self, documents: List[Dict[str, Any]]) -> Dict[str, int]:
        """Build vocabulary from documents."""
        word_counts = {}

        for doc in documents:
            words = doc["content"].lower().split()
            for word in words:
                # Simple tokenization - would use proper tokenizer in production
                clean_word = "".join(c for c in word if c.isalnum())
                if len(clean_word) > 2:  # Filter short words
                    word_counts[clean_word] = word_counts.get(clean_word, 0) + 1

        # Return top 10000 most frequent words
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_words[:10000])

    def _analyze_document_types(self, documents: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze document types in corpus."""
        type_counts = {}
        for doc in documents:
            doc_type = doc.get("type", "unknown")
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        return type_counts

    def _calculate_corpus_statistics(self, corpus: TechnicalCorpus) -> Dict[str, Any]:
        """Calculate corpus statistics."""
        docs = corpus.documents

        if not docs:
            return {}

        word_counts = [doc["word_count"] for doc in docs]
        lengths = [doc["length"] for doc in docs]

        return {
            "total_documents": len(docs),
            "total_vocabulary": len(corpus.vocabulary),
            "total_technical_terms": len(corpus.technical_terms),
            "avg_word_count": sum(word_counts) / len(word_counts),
            "avg_document_length": sum(lengths) / len(lengths),
            "max_word_count": max(word_counts),
            "min_word_count": min(word_counts),
            "document_types": corpus.document_types,
        }

    def get_corpus(self, corpus_name: str) -> Optional[TechnicalCorpus]:
        """Get a technical corpus by name."""
        return self.corpora.get(corpus_name)

    def list_corpora(self) -> List[str]:
        """List available corpora."""
        return list(self.corpora.keys())


class EmbeddingModelTrainer:
    """Trains custom embedding models for technical content."""

    def __init__(self, ml_pipeline: MLPipeline):
        self.ml_pipeline = ml_pipeline
        self.corpus_builder = TechnicalCorpusBuilder()
        self.trained_models = {}

        logger.info("Embedding model trainer initialized")

    @monitor_performance()
    async def train_technical_embedding_model(
        self, config: EmbeddingConfig, corpus: TechnicalCorpus, validation_split: float = 0.2
    ) -> ExperimentResult:
        """Train a technical embedding model."""
        start_time = time.time()

        try:
            # Prepare training data
            training_data, validation_data = self._prepare_training_data(corpus, validation_split)

            # Create model configuration
            model_config = ModelConfig(
                model_type=ModelType.EMBEDDING,
                model_name=f"{config.model_type.value}_{corpus.domain.value}",
                version="1.0.0",
                framework="pytorch",
                architecture="transformer",
                hyperparameters={
                    "base_model": config.base_model,
                    "embedding_dim": config.embedding_dim,
                    "max_length": config.max_sequence_length,
                    "learning_rate": config.learning_rate,
                    "batch_size": config.batch_size,
                    "num_epochs": config.num_epochs,
                    "warmup_steps": config.warmup_steps,
                    "weight_decay": config.weight_decay,
                    "dropout_rate": config.dropout_rate,
                    "use_contrastive_learning": config.use_contrastive_learning,
                    "temperature": config.temperature,
                },
                metadata={
                    "technical_domain": corpus.domain.value,
                    "corpus_size": len(corpus.documents),
                    "vocabulary_size": len(corpus.vocabulary),
                    "technical_terms": len(corpus.technical_terms),
                },
            )

            # Create experiment configuration
            experiment_config = ExperimentConfig(
                experiment_id=f"embedding_{config.model_type.value}_{int(time.time())}",
                experiment_name=f"Technical Embedding Training - {corpus.domain.value}",
                model_config=model_config,
                dataset_config={
                    "corpus_name": corpus.corpus_name,
                    "domain": corpus.domain.value,
                    "training_samples": len(training_data),
                    "validation_samples": len(validation_data) if validation_data is not None else 0,
                },
                training_params={
                    "epochs": config.num_epochs,
                    "learning_rate": config.learning_rate,
                    "batch_size": config.batch_size,
                    "warmup_steps": config.warmup_steps,
                    "weight_decay": config.weight_decay,
                },
                tags=["embedding", "technical", corpus.domain.value],
                description=f"Training {config.model_type.value} for {corpus.domain.value} domain",
            )

            # Train the model using ML pipeline
            logger.info(f"Starting embedding model training: {model_config.model_name}")
            result = await self.ml_pipeline.train_model(experiment_config, training_data, validation_data)

            # Perform embedding-specific evaluation
            if result.status.value == "completed":
                evaluation = await self._evaluate_embedding_model(model_config, corpus, validation_data)

                # Update result with embedding-specific metrics
                result.metrics.custom_metrics.update(
                    {
                        "embedding_similarity_score": evaluation.similarity_benchmarks.get("average", 0.0),
                        "retrieval_map_score": evaluation.retrieval_metrics.get("map", 0.0),
                        "technical_term_accuracy": evaluation.technical_term_accuracy,
                        "domain_specificity": evaluation.domain_specificity_score,
                    }
                )

                # Store trained model
                self.trained_models[model_config.model_name] = {
                    "config": config,
                    "model_config": model_config,
                    "corpus": corpus,
                    "evaluation": evaluation,
                    "result": result,
                }

            processing_time = time.time() - start_time
            logger.info(f"Embedding model training completed in {processing_time:.3f}s")

            return result

        except Exception as e:
            logger.error(f"Embedding model training failed: {e}")
            raise EmbeddingModelError(f"Training failed: {e}")

    def _prepare_training_data(
        self, corpus: TechnicalCorpus, validation_split: float
    ) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Prepare training data from corpus."""
        # Create training examples from documents
        training_examples = []

        for doc in corpus.documents:
            # Create positive pairs (document with its technical terms)
            for term in doc.get("technical_terms", []):
                training_examples.append(
                    {
                        "text": doc["content"],
                        "positive": term,
                        "label": 1,
                        "domain": doc["domain"],
                        "doc_type": doc["type"],
                    }
                )

            # Create negative pairs (document with random technical terms from other docs)
            import random

            other_terms = [
                term
                for other_doc in corpus.documents
                for term in other_doc.get("technical_terms", [])
                if other_doc["id"] != doc["id"]
            ]

            if other_terms:
                for _ in range(min(3, len(other_terms))):  # 3 negative samples per doc
                    negative_term = random.choice(other_terms)
                    training_examples.append(
                        {
                            "text": doc["content"],
                            "positive": negative_term,
                            "label": 0,
                            "domain": doc["domain"],
                            "doc_type": doc["type"],
                        }
                    )

        # Convert to DataFrame
        df = pd.DataFrame(training_examples)

        # Split into training and validation
        if validation_split > 0:
            train_df, val_df = train_test_split(df, test_size=validation_split, stratify=df["label"], random_state=42)
            return train_df, val_df
        else:
            return df, None

    async def _evaluate_embedding_model(
        self, model_config: ModelConfig, corpus: TechnicalCorpus, validation_data: Optional[pd.DataFrame]
    ) -> EmbeddingEvaluation:
        """Evaluate embedding model performance."""
        evaluation = EmbeddingEvaluation()

        # Mock evaluation - would implement actual evaluation here

        # Similarity benchmarks
        evaluation.similarity_benchmarks = {
            "technical_term_similarity": 0.85 + np.random.normal(0, 0.05),
            "document_similarity": 0.78 + np.random.normal(0, 0.03),
            "cross_domain_similarity": 0.65 + np.random.normal(0, 0.08),
            "average": 0.76 + np.random.normal(0, 0.04),
        }

        # Retrieval metrics
        evaluation.retrieval_metrics = {
            "map": 0.82 + np.random.normal(0, 0.03),  # Mean Average Precision
            "ndcg": 0.79 + np.random.normal(0, 0.04),  # Normalized DCG
            "recall_at_k": 0.88 + np.random.normal(0, 0.02),
            "precision_at_k": 0.75 + np.random.normal(0, 0.03),
        }

        # Clustering metrics
        evaluation.clustering_metrics = {
            "silhouette_score": 0.45 + np.random.normal(0, 0.08),
            "davies_bouldin_index": 1.2 + np.random.normal(0, 0.15),
            "calinski_harabasz_index": 150 + np.random.normal(0, 20),
        }

        # Technical term accuracy
        evaluation.technical_term_accuracy = 0.91 + np.random.normal(0, 0.02)

        # Domain specificity score
        evaluation.domain_specificity_score = 0.87 + np.random.normal(0, 0.03)

        # Clip values to reasonable ranges
        for metric_dict in [evaluation.similarity_benchmarks, evaluation.retrieval_metrics]:
            for key, value in metric_dict.items():
                metric_dict[key] = max(0.0, min(1.0, value))

        evaluation.technical_term_accuracy = max(0.0, min(1.0, evaluation.technical_term_accuracy))
        evaluation.domain_specificity_score = max(0.0, min(1.0, evaluation.domain_specificity_score))

        logger.info(f"Embedding evaluation completed: avg_similarity={evaluation.similarity_benchmarks['average']:.4f}")
        return evaluation

    def get_embedding_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get trained embedding model."""
        return self.trained_models.get(model_name)

    def compare_embedding_models(
        self, model_names: List[str], metric: str = "embedding_similarity_score"
    ) -> Dict[str, float]:
        """Compare embedding models by metric."""
        results = {}

        for model_name in model_names:
            model_info = self.trained_models.get(model_name)
            if model_info and "result" in model_info:
                custom_metrics = model_info["result"].metrics.custom_metrics
                if metric in custom_metrics:
                    results[model_name] = custom_metrics[metric]

        return dict(sorted(results.items(), key=lambda x: x[1], reverse=True))

    def generate_embeddings(self, model_name: str, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts using trained model."""
        model_info = self.trained_models.get(model_name)
        if not model_info:
            raise EmbeddingModelError(f"Model {model_name} not found")

        # Mock embedding generation - would use actual model here
        embedding_dim = model_info["config"].embedding_dim
        embeddings = []

        for text in texts:
            # Generate deterministic but varied embeddings based on text
            np.random.seed(hash(text) % 2**32)
            embedding = np.random.normal(0, 1, embedding_dim)
            embedding = embedding / np.linalg.norm(embedding)  # Normalize
            embeddings.append(embedding)

        return np.array(embeddings)

    def get_training_statistics(self) -> Dict[str, Any]:
        """Get comprehensive training statistics."""
        return {
            "total_models_trained": len(self.trained_models),
            "available_corpora": len(self.corpus_builder.corpora),
            "model_types": list(
                set(model_info["config"].model_type.value for model_info in self.trained_models.values())
            ),
            "technical_domains": list(
                set(model_info["corpus"].domain.value for model_info in self.trained_models.values())
            ),
            "average_performance": {
                "similarity_score": np.mean(
                    [
                        model_info["result"].metrics.custom_metrics.get("embedding_similarity_score", 0)
                        for model_info in self.trained_models.values()
                    ]
                )
                if self.trained_models
                else 0.0,
                "technical_accuracy": np.mean(
                    [
                        model_info["result"].metrics.custom_metrics.get("technical_term_accuracy", 0)
                        for model_info in self.trained_models.values()
                    ]
                )
                if self.trained_models
                else 0.0,
            },
        }


# Initialize embedding model trainer
from phase4a_ml_infrastructure import ml_pipeline

embedding_trainer = EmbeddingModelTrainer(ml_pipeline)

logger.info("Phase 4A Custom Embedding Model Training module loaded successfully")
