"""
Phase 4A: Machine Learning Infrastructure Setup
Comprehensive MLOps platform with experiment tracking and model management.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from utils.exceptions import MLPipelineError
from utils.logging_setup import get_logger
from utils.monitoring import monitor_performance

logger = get_logger(__name__)


class ModelType(Enum):
    """Types of ML models in the pipeline."""

    EMBEDDING = "embedding"
    CLASSIFICATION = "classification"
    NER = "named_entity_recognition"
    RELATION_EXTRACTION = "relation_extraction"
    ANOMALY_DETECTION = "anomaly_detection"
    PREDICTION = "prediction"
    OPTIMIZATION = "optimization"


class ModelStatus(Enum):
    """Model lifecycle status."""

    TRAINING = "training"
    VALIDATION = "validation"
    TESTING = "testing"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    FAILED = "failed"


class ExperimentStatus(Enum):
    """Experiment execution status."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ModelConfig:
    """Configuration for ML models."""

    model_type: ModelType
    model_name: str
    version: str = "1.0.0"
    framework: str = "pytorch"
    architecture: str = "transformer"
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    training_config: Dict[str, Any] = field(default_factory=dict)
    evaluation_metrics: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentConfig:
    """Configuration for ML experiments."""

    experiment_id: str
    experiment_name: str
    model_config: ModelConfig
    dataset_config: Dict[str, Any]
    training_params: Dict[str, Any] = field(default_factory=dict)
    evaluation_params: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ModelMetrics:
    """Model performance metrics."""

    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    loss: Optional[float] = None
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    training_time: Optional[float] = None
    inference_time: Optional[float] = None


@dataclass
class ExperimentResult:
    """Results from ML experiment."""

    experiment_id: str
    model_config: ModelConfig
    metrics: ModelMetrics
    model_path: Optional[str] = None
    artifacts: Dict[str, str] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    status: ExperimentStatus = ExperimentStatus.RUNNING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None


class MLflowTracker:
    """MLflow integration for experiment tracking."""

    def __init__(self, tracking_uri: str = "http://localhost:5000"):
        self.tracking_uri = tracking_uri
        self.experiments = {}
        self.active_experiments = {}

        logger.info(f"MLflow tracker initialized with URI: {tracking_uri}")

    def create_experiment(self, experiment_name: str, description: str = "") -> str:
        """Create a new MLflow experiment."""
        experiment_id = str(uuid.uuid4())

        self.experiments[experiment_id] = {
            "name": experiment_name,
            "description": description,
            "created_at": datetime.now(),
            "runs": {},
        }

        logger.info(f"Created experiment: {experiment_name} ({experiment_id})")
        return experiment_id

    def start_run(self, experiment_id: str, run_name: str, config: ExperimentConfig) -> str:
        """Start a new experiment run."""
        run_id = str(uuid.uuid4())

        run_data = {
            "run_id": run_id,
            "run_name": run_name,
            "config": config,
            "start_time": datetime.now(),
            "status": ExperimentStatus.RUNNING,
            "metrics": {},
            "parameters": config.training_params,
            "artifacts": {},
        }

        if experiment_id in self.experiments:
            self.experiments[experiment_id]["runs"][run_id] = run_data
            self.active_experiments[run_id] = experiment_id

        logger.info(f"Started run: {run_name} ({run_id})")
        return run_id

    def log_metrics(self, run_id: str, metrics: Dict[str, float], step: int = 0):
        """Log metrics for a run."""
        if run_id in self.active_experiments:
            experiment_id = self.active_experiments[run_id]
            run_data = self.experiments[experiment_id]["runs"][run_id]

            if step not in run_data["metrics"]:
                run_data["metrics"][step] = {}

            run_data["metrics"][step].update(metrics)
            logger.debug(f"Logged metrics for run {run_id}: {metrics}")

    def log_parameters(self, run_id: str, parameters: Dict[str, Any]):
        """Log parameters for a run."""
        if run_id in self.active_experiments:
            experiment_id = self.active_experiments[run_id]
            run_data = self.experiments[experiment_id]["runs"][run_id]
            run_data["parameters"].update(parameters)
            logger.debug(f"Logged parameters for run {run_id}: {parameters}")

    def log_artifact(self, run_id: str, artifact_name: str, artifact_path: str):
        """Log artifact for a run."""
        if run_id in self.active_experiments:
            experiment_id = self.active_experiments[run_id]
            run_data = self.experiments[experiment_id]["runs"][run_id]
            run_data["artifacts"][artifact_name] = artifact_path
            logger.debug(f"Logged artifact for run {run_id}: {artifact_name}")

    def end_run(self, run_id: str, status: ExperimentStatus = ExperimentStatus.COMPLETED):
        """End an experiment run."""
        if run_id in self.active_experiments:
            experiment_id = self.active_experiments[run_id]
            run_data = self.experiments[experiment_id]["runs"][run_id]
            run_data["status"] = status
            run_data["end_time"] = datetime.now()

            del self.active_experiments[run_id]
            logger.info(f"Ended run {run_id} with status: {status.value}")

    def get_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """Get results from an experiment."""
        if experiment_id in self.experiments:
            return self.experiments[experiment_id]
        return {}

    def get_best_run(self, experiment_id: str, metric_name: str, maximize: bool = True) -> Optional[Dict[str, Any]]:
        """Get the best run based on a metric."""
        if experiment_id not in self.experiments:
            return None

        runs = self.experiments[experiment_id]["runs"]
        best_run = None
        best_metric = float("-inf") if maximize else float("inf")

        for run_data in runs.values():
            if run_data["status"] != ExperimentStatus.COMPLETED:
                continue

            # Get latest metric value
            latest_step = max(run_data["metrics"].keys()) if run_data["metrics"] else -1
            if latest_step >= 0 and metric_name in run_data["metrics"][latest_step]:
                metric_value = run_data["metrics"][latest_step][metric_name]

                if (maximize and metric_value > best_metric) or (not maximize and metric_value < best_metric):
                    best_metric = metric_value
                    best_run = run_data

        return best_run


class ModelRegistry:
    """Model registry for versioning and lifecycle management."""

    def __init__(self, registry_path: str = "models/registry"):
        self.registry_path = Path(registry_path)
        self.registry_path.mkdir(parents=True, exist_ok=True)
        self.models = {}
        self._load_registry()

        logger.info(f"Model registry initialized at: {registry_path}")

    def _load_registry(self):
        """Load existing model registry."""
        registry_file = self.registry_path / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, "r") as f:
                    self.models = json.load(f)
                logger.info(f"Loaded {len(self.models)} models from registry")
            except Exception as e:
                logger.error(f"Failed to load model registry: {e}")

    def _save_registry(self):
        """Save model registry to disk."""
        registry_file = self.registry_path / "registry.json"
        try:
            with open(registry_file, "w") as f:
                json.dump(self.models, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save model registry: {e}")

    def register_model(
        self, model_name: str, model_path: str, config: ModelConfig, metrics: ModelMetrics, tags: List[str] = None
    ) -> str:
        """Register a new model version."""
        if model_name not in self.models:
            self.models[model_name] = {"versions": {}, "latest_version": None}

        version = config.version
        model_id = f"{model_name}:{version}"

        model_info = {
            "model_id": model_id,
            "model_name": model_name,
            "version": version,
            "model_path": model_path,
            "config": config.__dict__,
            "metrics": metrics.__dict__,
            "tags": tags or [],
            "status": ModelStatus.DEPLOYED.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        self.models[model_name]["versions"][version] = model_info
        self.models[model_name]["latest_version"] = version

        self._save_registry()
        logger.info(f"Registered model: {model_id}")
        return model_id

    def get_model(self, model_name: str, version: str = None) -> Optional[Dict[str, Any]]:
        """Get model information."""
        if model_name not in self.models:
            return None

        if version is None:
            version = self.models[model_name]["latest_version"]

        return self.models[model_name]["versions"].get(version)

    def list_models(self, model_type: ModelType = None) -> List[Dict[str, Any]]:
        """List all registered models."""
        models = []
        for model_name, model_data in self.models.items():
            for version, model_info in model_data["versions"].items():
                if model_type is None or model_info["config"]["model_type"] == model_type.value:
                    models.append(model_info)
        return models

    def update_model_status(self, model_name: str, version: str, status: ModelStatus):
        """Update model status."""
        if model_name in self.models and version in self.models[model_name]["versions"]:
            self.models[model_name]["versions"][version]["status"] = status.value
            self.models[model_name]["versions"][version]["updated_at"] = datetime.now().isoformat()
            self._save_registry()
            logger.info(f"Updated model {model_name}:{version} status to {status.value}")

    def delete_model(self, model_name: str, version: str):
        """Delete a model version."""
        if model_name in self.models and version in self.models[model_name]["versions"]:
            del self.models[model_name]["versions"][version]

            # Update latest version if necessary
            if self.models[model_name]["latest_version"] == version:
                remaining_versions = list(self.models[model_name]["versions"].keys())
                self.models[model_name]["latest_version"] = remaining_versions[-1] if remaining_versions else None

            # Remove model entirely if no versions left
            if not self.models[model_name]["versions"]:
                del self.models[model_name]

            self._save_registry()
            logger.info(f"Deleted model {model_name}:{version}")


class DatasetManager:
    """Manages datasets for ML training and evaluation."""

    def __init__(self, data_path: str = "data/ml"):
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.datasets = {}

        logger.info(f"Dataset manager initialized at: {data_path}")

    def create_dataset(
        self,
        dataset_name: str,
        data: Union[pd.DataFrame, np.ndarray, List],
        dataset_type: str = "training",
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Create and save a dataset."""
        dataset_id = f"{dataset_name}_{dataset_type}_{int(time.time())}"
        dataset_path = self.data_path / f"{dataset_id}.parquet"

        # Convert to DataFrame if necessary
        if isinstance(data, (np.ndarray, list)):
            df = pd.DataFrame(data)
        else:
            df = data

        # Save dataset
        df.to_parquet(dataset_path)

        # Store metadata
        self.datasets[dataset_id] = {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name,
            "dataset_type": dataset_type,
            "path": str(dataset_path),
            "size": len(df),
            "columns": list(df.columns) if hasattr(df, "columns") else [],
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        logger.info(f"Created dataset: {dataset_id} with {len(df)} samples")
        return dataset_id

    def load_dataset(self, dataset_id: str) -> Optional[pd.DataFrame]:
        """Load a dataset."""
        if dataset_id not in self.datasets:
            return None

        dataset_path = self.datasets[dataset_id]["path"]
        try:
            return pd.read_parquet(dataset_path)
        except Exception as e:
            logger.error(f"Failed to load dataset {dataset_id}: {e}")
            return None

    def split_dataset(
        self, dataset_id: str, test_size: float = 0.2, val_size: float = 0.1, random_state: int = 42
    ) -> Tuple[str, str, str]:
        """Split dataset into train/validation/test sets."""
        df = self.load_dataset(dataset_id)
        if df is None:
            raise MLPipelineError(f"Dataset {dataset_id} not found")

        # First split: train+val / test
        train_val, test = train_test_split(df, test_size=test_size, random_state=random_state)

        # Second split: train / val
        val_size_adjusted = val_size / (1 - test_size)
        train, val = train_test_split(train_val, test_size=val_size_adjusted, random_state=random_state)

        # Create split datasets
        base_name = self.datasets[dataset_id]["dataset_name"]
        train_id = self.create_dataset(f"{base_name}_train", train, "training")
        val_id = self.create_dataset(f"{base_name}_val", val, "validation")
        test_id = self.create_dataset(f"{base_name}_test", test, "testing")

        logger.info(f"Split dataset {dataset_id}: train={len(train)}, val={len(val)}, test={len(test)}")
        return train_id, val_id, test_id

    def get_dataset_info(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get dataset information."""
        return self.datasets.get(dataset_id)

    def list_datasets(self, dataset_type: str = None) -> List[Dict[str, Any]]:
        """List all datasets."""
        datasets = list(self.datasets.values())
        if dataset_type:
            datasets = [d for d in datasets if d["dataset_type"] == dataset_type]
        return datasets


class MLPipeline:
    """Main ML pipeline orchestrator."""

    def __init__(self):
        self.tracker = MLflowTracker()
        self.registry = ModelRegistry()
        self.dataset_manager = DatasetManager()

        # Initialize experiment for this session
        self.current_experiment_id = self.tracker.create_experiment(
            "Phase4A_ML_Pipeline", "Machine Learning Pipeline for Technical Service Assistant"
        )

        logger.info("ML Pipeline initialized successfully")

    @monitor_performance()
    async def train_model(
        self, config: ExperimentConfig, training_data: pd.DataFrame, validation_data: Optional[pd.DataFrame] = None
    ) -> ExperimentResult:
        """Train a machine learning model."""
        start_time = time.time()

        try:
            # Start MLflow run
            run_id = self.tracker.start_run(
                self.current_experiment_id, f"{config.model_config.model_name}_training", config
            )

            # Log parameters
            self.tracker.log_parameters(run_id, config.training_params)

            # Mock training process - would implement actual training here
            await self._mock_training_process(run_id, config, training_data, validation_data)

            # Calculate metrics
            metrics = await self._evaluate_model(config, training_data, validation_data)

            # Log final metrics
            final_metrics = {
                "final_accuracy": metrics.accuracy or 0.0,
                "final_f1": metrics.f1_score or 0.0,
                "training_time": time.time() - start_time,
            }
            self.tracker.log_metrics(run_id, final_metrics)

            # Save model (mock)
            model_path = f"models/{config.model_config.model_name}_{config.model_config.version}.pkl"
            self.tracker.log_artifact(run_id, "model", model_path)

            # Register model
            model_id = self.registry.register_model(
                config.model_config.model_name, model_path, config.model_config, metrics
            )

            # End run
            self.tracker.end_run(run_id, ExperimentStatus.COMPLETED)

            result = ExperimentResult(
                experiment_id=config.experiment_id,
                model_config=config.model_config,
                metrics=metrics,
                model_path=model_path,
                status=ExperimentStatus.COMPLETED,
                start_time=datetime.fromtimestamp(start_time),
                end_time=datetime.now(),
            )

            logger.info(f"Model training completed: {model_id}")
            return result

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            if "run_id" in locals():
                self.tracker.end_run(run_id, ExperimentStatus.FAILED)

            return ExperimentResult(
                experiment_id=config.experiment_id,
                model_config=config.model_config,
                metrics=ModelMetrics(),
                status=ExperimentStatus.FAILED,
                error_message=str(e),
                start_time=datetime.fromtimestamp(start_time),
                end_time=datetime.now(),
            )

    async def _mock_training_process(
        self,
        run_id: str,
        config: ExperimentConfig,
        training_data: pd.DataFrame,
        validation_data: Optional[pd.DataFrame],
    ):
        """Mock the training process with progress logging."""
        epochs = config.training_params.get("epochs", 10)

        for epoch in range(epochs):
            await asyncio.sleep(0.1)  # Simulate training time

            # Mock metrics that improve over time
            train_loss = 1.0 - (epoch * 0.08) + np.random.normal(0, 0.02)
            train_acc = 0.5 + (epoch * 0.04) + np.random.normal(0, 0.01)

            metrics = {"train_loss": max(0.1, train_loss), "train_accuracy": min(0.95, max(0.5, train_acc))}

            if validation_data is not None:
                val_loss = train_loss + 0.1 + np.random.normal(0, 0.02)
                val_acc = train_acc - 0.05 + np.random.normal(0, 0.01)
                metrics.update({"val_loss": max(0.1, val_loss), "val_accuracy": min(0.9, max(0.4, val_acc))})

            self.tracker.log_metrics(run_id, metrics, step=epoch)
            logger.debug(f"Epoch {epoch+1}/{epochs}: {metrics}")

    async def _evaluate_model(
        self, config: ExperimentConfig, training_data: pd.DataFrame, validation_data: Optional[pd.DataFrame]
    ) -> ModelMetrics:
        """Evaluate trained model."""
        # Mock evaluation - would implement actual evaluation here
        base_accuracy = 0.85 + np.random.normal(0, 0.05)

        return ModelMetrics(
            accuracy=min(0.98, max(0.7, base_accuracy)),
            precision=min(0.97, max(0.65, base_accuracy - 0.02)),
            recall=min(0.96, max(0.68, base_accuracy - 0.01)),
            f1_score=min(0.97, max(0.66, base_accuracy - 0.015)),
            loss=max(0.05, 0.4 - base_accuracy * 0.3),
            training_time=np.random.uniform(120, 600),  # 2-10 minutes
            inference_time=np.random.uniform(0.01, 0.1),  # 10-100ms
        )

    def create_experiment_config(
        self,
        model_name: str,
        model_type: ModelType,
        hyperparameters: Dict[str, Any] = None,
        training_params: Dict[str, Any] = None,
    ) -> ExperimentConfig:
        """Create experiment configuration."""
        experiment_id = str(uuid.uuid4())

        model_config = ModelConfig(
            model_type=model_type,
            model_name=model_name,
            hyperparameters=hyperparameters or {},
            training_config=training_params or {},
        )

        return ExperimentConfig(
            experiment_id=experiment_id,
            experiment_name=f"{model_name}_experiment",
            model_config=model_config,
            dataset_config={},
            training_params=training_params or {"epochs": 10, "learning_rate": 0.001},
            evaluation_params={"metrics": ["accuracy", "f1_score"]},
        )

    def get_model_performance(self, model_name: str, version: str = None) -> Optional[ModelMetrics]:
        """Get model performance metrics."""
        model_info = self.registry.get_model(model_name, version)
        if model_info and "metrics" in model_info:
            metrics_dict = model_info["metrics"]
            return ModelMetrics(**metrics_dict)
        return None

    def compare_models(self, model_names: List[str], metric: str = "accuracy") -> Dict[str, float]:
        """Compare performance of multiple models."""
        results = {}

        for model_name in model_names:
            metrics = self.get_model_performance(model_name)
            if metrics and hasattr(metrics, metric):
                results[model_name] = getattr(metrics, metric)

        return dict(sorted(results.items(), key=lambda x: x[1], reverse=True))

    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics."""
        return {
            "total_experiments": len(self.tracker.experiments),
            "total_models": len(self.registry.models),
            "total_datasets": len(self.dataset_manager.datasets),
            "active_runs": len(self.tracker.active_experiments),
            "model_types": list(
                set(
                    model_info["config"]["model_type"]
                    for model_data in self.registry.models.values()
                    for model_info in model_data["versions"].values()
                )
            ),
            "latest_experiment": self.current_experiment_id,
        }


# Initialize global ML pipeline
ml_pipeline = MLPipeline()

logger.info("Phase 4A Machine Learning Infrastructure module loaded successfully")
