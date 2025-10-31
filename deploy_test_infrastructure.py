#!/usr/bin/env python3
"""
Enterprise Test Infrastructure Deployment System

Production-ready deployment and integration system for the automated test
maintenance infrastructure. Provides enterprise-grade deployment, monitoring,
and integration capabilities.

Features:
- Docker containerization for all components
- Kubernetes deployment manifests
- CI/CD pipeline integration
- Enterprise monitoring and alerting
- Multi-environment configuration
- Security hardening and compliance

Usage:
    python deploy_test_infrastructure.py --environment production
    python deploy_test_infrastructure.py --environment staging --validate
    python deploy_test_infrastructure.py --generate-k8s-manifests
    python deploy_test_infrastructure.py --setup-monitoring
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml


class TestInfrastructureDeployer:
    """Enterprise deployment system for test infrastructure."""

    def __init__(self, environment: str = "staging"):
        """Initialize deployment system."""
        self.environment = environment
        self.project_root = Path.cwd()
        self.deployment_dir = self.project_root / "deployment"
        self.deployment_dir.mkdir(exist_ok=True)

        # Environment-specific configurations
        self.environments = {
            "development": {
                "replicas": 1,
                "resources": {"cpu": "100m", "memory": "256Mi"},
                "storage": "1Gi",
                "monitoring": False,
            },
            "staging": {
                "replicas": 2,
                "resources": {"cpu": "200m", "memory": "512Mi"},
                "storage": "5Gi",
                "monitoring": True,
            },
            "production": {
                "replicas": 3,
                "resources": {"cpu": "500m", "memory": "1Gi"},
                "storage": "20Gi",
                "monitoring": True,
            },
        }

    def generate_dockerfile(self) -> str:
        """Generate production-ready Dockerfile for test infrastructure."""
        dockerfile_content = """# Production Test Infrastructure Docker Image
FROM python:3.9-slim

LABEL maintainer="Technical Service Assistant Team"
LABEL version="1.0.0"
LABEL description="Enterprise Test Infrastructure with AI-powered automation"

# Security: Create non-root user
RUN groupadd -r testinfra && useradd -r -g testinfra testinfra

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    curl \\
    sqlite3 \\
    nginx \\
    supervisor \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/uploads /app/reports \\
    && chown -R testinfra:testinfra /app

# Copy configuration files
COPY deployment/nginx.conf /etc/nginx/nginx.conf
COPY deployment/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose ports
EXPOSE 8080 8090 8008

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \\
    CMD curl -f http://localhost:8090/api/suite-health || exit 1

# Switch to non-root user
USER testinfra

# Start services using supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
"""

        dockerfile_path = self.deployment_dir / "Dockerfile"
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)

        return str(dockerfile_path)

    def generate_docker_compose(self) -> str:
        """Generate production Docker Compose configuration."""
        env_config = self.environments[self.environment]

        compose_content = {
            "version": "3.8",
            "services": {
                "test-infrastructure": {
                    "build": {"context": ".", "dockerfile": "deployment/Dockerfile"},
                    "container_name": f"test-infra-{self.environment}",
                    "restart": "unless-stopped",
                    "ports": [
                        "8080:8080",  # Main dashboard
                        "8090:8090",  # Test maintenance dashboard
                        "8008:8008",  # Reranker API
                    ],
                    "volumes": [
                        "./uploads:/app/uploads",
                        "./logs:/app/logs",
                        "./data:/app/data",
                        f"test-infra-db-{self.environment}:/app/database",
                    ],
                    "environment": [
                        f"ENVIRONMENT={self.environment}",
                        "LOG_LEVEL=INFO",
                        "ENABLE_MONITORING=true",
                        "DATABASE_PATH=/app/database/test_optimization.db",
                    ],
                    "healthcheck": {
                        "test": ["CMD", "curl", "-f", "http://localhost:8090/api/suite-health"],
                        "interval": "30s",
                        "timeout": "10s",
                        "retries": 3,
                        "start_period": "60s",
                    },
                    "deploy": {
                        "resources": {
                            "limits": {
                                "cpus": env_config["resources"]["cpu"],
                                "memory": env_config["resources"]["memory"],
                            }
                        }
                    },
                },
                "prometheus": {
                    "image": "prom/prometheus:latest",
                    "container_name": f"prometheus-{self.environment}",
                    "ports": ["9090:9090"],
                    "volumes": [
                        "./deployment/prometheus.yml:/etc/prometheus/prometheus.yml",
                        f"prometheus-data-{self.environment}:/prometheus",
                    ],
                    "command": [
                        "--config.file=/etc/prometheus/prometheus.yml",
                        "--storage.tsdb.path=/prometheus",
                        "--web.console.libraries=/etc/prometheus/console_libraries",
                        "--web.console.templates=/etc/prometheus/consoles",
                        "--storage.tsdb.retention.time=200h",
                        "--web.enable-lifecycle",
                    ],
                }
                if env_config["monitoring"]
                else {},
                "grafana": {
                    "image": "grafana/grafana:latest",
                    "container_name": f"grafana-{self.environment}",
                    "ports": ["3000:3000"],
                    "volumes": [
                        f"grafana-data-{self.environment}:/var/lib/grafana",
                        "./deployment/grafana/dashboards:/etc/grafana/provisioning/dashboards",
                        "./deployment/grafana/datasources:/etc/grafana/provisioning/datasources",
                    ],
                    "environment": ["GF_SECURITY_ADMIN_PASSWORD=test-infra-admin"],
                }
                if env_config["monitoring"]
                else {},
            },
            "volumes": {
                f"test-infra-db-{self.environment}": {},
                f"prometheus-data-{self.environment}": {} if env_config["monitoring"] else None,
                f"grafana-data-{self.environment}": {} if env_config["monitoring"] else None,
            },
            "networks": {"test-infra-network": {"driver": "bridge"}},
        }

        # Remove empty monitoring services
        compose_content["services"] = {k: v for k, v in compose_content["services"].items() if v}
        compose_content["volumes"] = {k: v for k, v in compose_content["volumes"].items() if v is not None}

        compose_path = self.deployment_dir / f"docker-compose.{self.environment}.yml"
        with open(compose_path, "w") as f:
            yaml.dump(compose_content, f, default_flow_style=False, indent=2)

        return str(compose_path)

    def generate_kubernetes_manifests(self) -> List[str]:
        """Generate Kubernetes deployment manifests."""
        env_config = self.environments[self.environment]
        k8s_dir = self.deployment_dir / "k8s" / self.environment
        k8s_dir.mkdir(parents=True, exist_ok=True)

        manifests = []

        # Namespace
        namespace_manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": f"test-infrastructure-{self.environment}",
                "labels": {"environment": self.environment, "app": "test-infrastructure"},
            },
        }

        namespace_path = k8s_dir / "namespace.yaml"
        with open(namespace_path, "w") as f:
            yaml.dump(namespace_manifest, f, default_flow_style=False)
        manifests.append(str(namespace_path))

        # ConfigMap
        configmap_manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "test-infra-config", "namespace": f"test-infrastructure-{self.environment}"},
            "data": {
                "ENVIRONMENT": self.environment,
                "LOG_LEVEL": "INFO",
                "ENABLE_MONITORING": "true",
                "DATABASE_PATH": "/app/database/test_optimization.db",
            },
        }

        configmap_path = k8s_dir / "configmap.yaml"
        with open(configmap_path, "w") as f:
            yaml.dump(configmap_manifest, f, default_flow_style=False)
        manifests.append(str(configmap_path))

        # Deployment
        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "test-infrastructure",
                "namespace": f"test-infrastructure-{self.environment}",
                "labels": {"app": "test-infrastructure", "environment": self.environment},
            },
            "spec": {
                "replicas": env_config["replicas"],
                "selector": {"matchLabels": {"app": "test-infrastructure"}},
                "template": {
                    "metadata": {"labels": {"app": "test-infrastructure", "environment": self.environment}},
                    "spec": {
                        "containers": [
                            {
                                "name": "test-infrastructure",
                                "image": f"test-infrastructure:{self.environment}",
                                "ports": [
                                    {"containerPort": 8080, "name": "dashboard"},
                                    {"containerPort": 8090, "name": "maintenance"},
                                    {"containerPort": 8008, "name": "api"},
                                ],
                                "resources": {
                                    "requests": env_config["resources"],
                                    "limits": {
                                        "cpu": env_config["resources"]["cpu"].replace("m", "m"),
                                        "memory": env_config["resources"]["memory"],
                                    },
                                },
                                "envFrom": [{"configMapRef": {"name": "test-infra-config"}}],
                                "volumeMounts": [
                                    {"name": "database-storage", "mountPath": "/app/database"},
                                    {"name": "uploads-storage", "mountPath": "/app/uploads"},
                                    {"name": "logs-storage", "mountPath": "/app/logs"},
                                ],
                                "livenessProbe": {
                                    "httpGet": {"path": "/api/suite-health", "port": 8090},
                                    "initialDelaySeconds": 60,
                                    "periodSeconds": 30,
                                    "timeoutSeconds": 10,
                                    "failureThreshold": 3,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/api/test-execution-status", "port": 8090},
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                    "timeoutSeconds": 5,
                                    "failureThreshold": 3,
                                },
                            }
                        ],
                        "volumes": [
                            {"name": "database-storage", "persistentVolumeClaim": {"claimName": "test-infra-db-pvc"}},
                            {
                                "name": "uploads-storage",
                                "persistentVolumeClaim": {"claimName": "test-infra-uploads-pvc"},
                            },
                            {"name": "logs-storage", "persistentVolumeClaim": {"claimName": "test-infra-logs-pvc"}},
                        ],
                    },
                },
            },
        }

        deployment_path = k8s_dir / "deployment.yaml"
        with open(deployment_path, "w") as f:
            yaml.dump(deployment_manifest, f, default_flow_style=False)
        manifests.append(str(deployment_path))

        # Service
        service_manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "test-infrastructure-service", "namespace": f"test-infrastructure-{self.environment}"},
            "spec": {
                "selector": {"app": "test-infrastructure"},
                "ports": [
                    {"name": "dashboard", "port": 8080, "targetPort": 8080},
                    {"name": "maintenance", "port": 8090, "targetPort": 8090},
                    {"name": "api", "port": 8008, "targetPort": 8008},
                ],
                "type": "LoadBalancer" if self.environment == "production" else "ClusterIP",
            },
        }

        service_path = k8s_dir / "service.yaml"
        with open(service_path, "w") as f:
            yaml.dump(service_manifest, f, default_flow_style=False)
        manifests.append(str(service_path))

        # Persistent Volume Claims
        for pvc_name, size in [("db", "5Gi"), ("uploads", "10Gi"), ("logs", "2Gi")]:
            pvc_manifest = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": f"test-infra-{pvc_name}-pvc",
                    "namespace": f"test-infrastructure-{self.environment}",
                },
                "spec": {"accessModes": ["ReadWriteOnce"], "resources": {"requests": {"storage": size}}},
            }

            pvc_path = k8s_dir / f"pvc-{pvc_name}.yaml"
            with open(pvc_path, "w") as f:
                yaml.dump(pvc_manifest, f, default_flow_style=False)
            manifests.append(str(pvc_path))

        return manifests

    def generate_cicd_pipeline(self) -> str:
        """Generate CI/CD pipeline configuration."""
        github_actions_dir = self.project_root / ".github" / "workflows"
        github_actions_dir.mkdir(parents=True, exist_ok=True)

        pipeline_config = {
            "name": "Test Infrastructure Deployment",
            "on": {
                "push": {
                    "branches": ["main", "develop"],
                    "paths": [
                        "test_runner.py",
                        "test_optimizer.py",
                        "test_dashboard.py",
                        "ai_test_generator.py",
                        "quality_monitor.py",
                        "deployment/**",
                        "requirements.txt",
                    ],
                },
                "pull_request": {
                    "branches": ["main"],
                    "paths": [
                        "test_runner.py",
                        "test_optimizer.py",
                        "test_dashboard.py",
                        "ai_test_generator.py",
                        "quality_monitor.py",
                        "deployment/**",
                        "requirements.txt",
                    ],
                },
                "workflow_dispatch": {},
            },
            "env": {"REGISTRY": "ghcr.io", "IMAGE_NAME": "${{ github.repository }}/test-infrastructure"},
            "jobs": {
                "quality-assurance": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {"name": "Set up Python", "uses": "actions/setup-python@v4", "with": {"python-version": "3.9"}},
                        {
                            "name": "Install dependencies",
                            "run": "pip install -r requirements.txt -r requirements-dev.txt",
                        },
                        {"name": "Run quality checks", "run": "pre-commit run --all-files"},
                        {
                            "name": "Run comprehensive tests",
                            "run": "python test_runner.py --all --coverage --report results.json",
                        },
                        {"name": "Run test optimization analysis", "run": "python test_optimizer.py --analyze"},
                        {
                            "name": "Generate AI test scenarios",
                            "run": "python ai_test_generator.py --scenario integration --validate",
                        },
                    ],
                },
                "build-and-deploy": {
                    "needs": "quality-assurance",
                    "runs-on": "ubuntu-latest",
                    "permissions": {"contents": "read", "packages": "write"},
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Log in to Container Registry",
                            "uses": "docker/login-action@v3",
                            "with": {
                                "registry": "${{ env.REGISTRY }}",
                                "username": "${{ github.actor }}",
                                "password": "${{ secrets.GITHUB_TOKEN }}",
                            },
                        },
                        {
                            "name": "Extract metadata",
                            "id": "meta",
                            "uses": "docker/metadata-action@v5",
                            "with": {
                                "images": "${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}",
                                "tags": ["type=ref,event=branch", "type=ref,event=pr", "type=sha,prefix={{branch}}-"],
                            },
                        },
                        {
                            "name": "Build and push Docker image",
                            "uses": "docker/build-push-action@v5",
                            "with": {
                                "context": ".",
                                "file": "deployment/Dockerfile",
                                "push": True,
                                "tags": "${{ steps.meta.outputs.tags }}",
                                "labels": "${{ steps.meta.outputs.labels }}",
                            },
                        },
                    ],
                },
                "deploy-staging": {
                    "needs": "build-and-deploy",
                    "runs-on": "ubuntu-latest",
                    "if": "github.ref == 'refs/heads/develop'",
                    "environment": "staging",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Deploy to staging",
                            "run": [
                                "python deploy_test_infrastructure.py --environment staging --validate",
                                "kubectl apply -f deployment/k8s/staging/",
                            ],
                        },
                        {"name": "Run smoke tests", "run": "python test_runner.py --smoke-tests --environment staging"},
                    ],
                },
                "deploy-production": {
                    "needs": "build-and-deploy",
                    "runs-on": "ubuntu-latest",
                    "if": "github.ref == 'refs/heads/main'",
                    "environment": "production",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Deploy to production",
                            "run": [
                                "python deploy_test_infrastructure.py --environment production --validate",
                                "kubectl apply -f deployment/k8s/production/",
                            ],
                        },
                        {
                            "name": "Run production validation",
                            "run": "python test_runner.py --production-validation --environment production",
                        },
                        {
                            "name": "Setup monitoring alerts",
                            "run": "python deploy_test_infrastructure.py --setup-monitoring --environment production",
                        },
                    ],
                },
            },
        }

        pipeline_path = github_actions_dir / "test-infrastructure-deployment.yml"
        with open(pipeline_path, "w") as f:
            yaml.dump(pipeline_config, f, default_flow_style=False, indent=2)

        return str(pipeline_path)

    def generate_monitoring_config(self) -> List[str]:
        """Generate monitoring and alerting configuration."""
        monitoring_dir = self.deployment_dir / "monitoring"
        monitoring_dir.mkdir(exist_ok=True)

        configs = []

        # Prometheus configuration
        prometheus_config = {
            "global": {"scrape_interval": "15s", "evaluation_interval": "15s"},
            "rule_files": ["alert_rules.yml"],
            "alertmanager": {"alertmanagers": [{"static_configs": [{"targets": ["alertmanager:9093"]}]}]},
            "scrape_configs": [
                {
                    "job_name": "test-infrastructure",
                    "static_configs": [{"targets": ["test-infrastructure:8090"]}],
                    "metrics_path": "/metrics",
                    "scrape_interval": "30s",
                }
            ],
        }

        prometheus_path = monitoring_dir / "prometheus.yml"
        with open(prometheus_path, "w") as f:
            yaml.dump(prometheus_config, f, default_flow_style=False)
        configs.append(str(prometheus_path))

        # Alert rules
        alert_rules = {
            "groups": [
                {
                    "name": "test-infrastructure-alerts",
                    "rules": [
                        {
                            "alert": "TestSuiteHealthDegraded",
                            "expr": "test_suite_health_score < 0.8",
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Test suite health has degraded",
                                "description": "Test suite health score is {{ $value }}, below the 0.8 threshold",
                            },
                        },
                        {
                            "alert": "FlakyTestsDetected",
                            "expr": "flaky_tests_count > 5",
                            "for": "1m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "High number of flaky tests detected",
                                "description": "{{ $value }} flaky tests detected, requiring attention",
                            },
                        },
                        {
                            "alert": "TestExecutionTimeHigh",
                            "expr": "test_execution_time_avg > 300",
                            "for": "10m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "Test execution time is high",
                                "description": "Average test execution time is {{ $value }} seconds",
                            },
                        },
                    ],
                }
            ]
        }

        alert_rules_path = monitoring_dir / "alert_rules.yml"
        with open(alert_rules_path, "w") as f:
            yaml.dump(alert_rules, f, default_flow_style=False)
        configs.append(str(alert_rules_path))

        return configs

    def validate_deployment(self) -> Dict:
        """Validate deployment configuration and readiness."""
        validation_results = {"status": "passed", "checks": [], "warnings": [], "errors": []}

        # Check required files
        required_files = [
            "test_runner.py",
            "test_optimizer.py",
            "test_dashboard.py",
            "ai_test_generator.py",
            "quality_monitor.py",
            "requirements.txt",
        ]

        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                validation_results["errors"].append(f"Required file missing: {file_path}")
                validation_results["status"] = "failed"
            else:
                validation_results["checks"].append(f"✅ {file_path} exists")

        # Check Python syntax
        for py_file in required_files:
            if py_file.endswith(".py"):
                try:
                    result = subprocess.run(
                        ["python", "-m", "py_compile", py_file], capture_output=True, text=True, cwd=self.project_root
                    )

                    if result.returncode == 0:
                        validation_results["checks"].append(f"✅ {py_file} syntax valid")
                    else:
                        validation_results["errors"].append(f"Syntax error in {py_file}: {result.stderr}")
                        validation_results["status"] = "failed"

                except Exception as e:
                    validation_results["warnings"].append(f"Could not validate {py_file}: {e}")

        # Check deployment files
        deployment_files = [
            self.deployment_dir / "Dockerfile",
            self.deployment_dir / f"docker-compose.{self.environment}.yml",
        ]

        for deploy_file in deployment_files:
            if deploy_file.exists():
                validation_results["checks"].append(f"✅ {deploy_file.name} generated")
            else:
                validation_results["warnings"].append(f"Deployment file not found: {deploy_file.name}")

        return validation_results

    def deploy(self) -> Dict:
        """Execute deployment process."""
        print(f"🚀 Deploying Test Infrastructure to {self.environment.upper()}")

        deployment_results = {
            "environment": self.environment,
            "timestamp": datetime.now().isoformat(),
            "status": "in_progress",
            "steps": [],
        }

        try:
            # Step 1: Generate Dockerfile
            print("📦 Generating Dockerfile...")
            dockerfile_path = self.generate_dockerfile()
            deployment_results["steps"].append(f"✅ Dockerfile generated: {dockerfile_path}")

            # Step 2: Generate Docker Compose
            print("🐳 Generating Docker Compose configuration...")
            compose_path = self.generate_docker_compose()
            deployment_results["steps"].append(f"✅ Docker Compose generated: {compose_path}")

            # Step 3: Generate Kubernetes manifests
            print("☸️  Generating Kubernetes manifests...")
            k8s_manifests = self.generate_kubernetes_manifests()
            deployment_results["steps"].append(f"✅ Kubernetes manifests generated: {len(k8s_manifests)} files")

            # Step 4: Generate CI/CD pipeline
            print("🔄 Generating CI/CD pipeline...")
            pipeline_path = self.generate_cicd_pipeline()
            deployment_results["steps"].append(f"✅ CI/CD pipeline generated: {pipeline_path}")

            # Step 5: Generate monitoring configuration
            print("📊 Generating monitoring configuration...")
            monitoring_configs = self.generate_monitoring_config()
            deployment_results["steps"].append(f"✅ Monitoring configs generated: {len(monitoring_configs)} files")

            # Step 6: Validate deployment
            print("🔍 Validating deployment configuration...")
            validation = self.validate_deployment()
            if validation["status"] == "passed":
                deployment_results["steps"].append("✅ Deployment validation passed")
            else:
                deployment_results["steps"].append(f"⚠️  Validation warnings: {len(validation['warnings'])}")
                if validation["errors"]:
                    deployment_results["status"] = "failed"
                    deployment_results["errors"] = validation["errors"]
                    return deployment_results

            deployment_results["status"] = "completed"
            deployment_results["validation"] = validation

            print("🎉 Test Infrastructure deployment configuration generated successfully!")

        except Exception as e:
            deployment_results["status"] = "failed"
            deployment_results["error"] = str(e)
            print(f"❌ Deployment failed: {e}")

        return deployment_results


def main():
    """Main entry point for deployment system."""
    parser = argparse.ArgumentParser(description="Enterprise Test Infrastructure Deployment")
    parser.add_argument(
        "--environment", choices=["development", "staging", "production"], default="staging", help="Target environment"
    )
    parser.add_argument("--validate", action="store_true", help="Validate deployment only")
    parser.add_argument("--generate-k8s-manifests", action="store_true", help="Generate Kubernetes manifests")
    parser.add_argument("--setup-monitoring", action="store_true", help="Setup monitoring configuration")
    parser.add_argument("--output", help="Output results to JSON file")

    args = parser.parse_args()

    deployer = TestInfrastructureDeployer(environment=args.environment)

    if args.validate:
        print("🔍 Validating deployment configuration...")
        validation = deployer.validate_deployment()

        print(f"\n📊 Validation Results:")
        print(f"Status: {validation['status'].upper()}")

        for check in validation["checks"]:
            print(f"  {check}")

        for warning in validation["warnings"]:
            print(f"  ⚠️  {warning}")

        for error in validation["errors"]:
            print(f"  ❌ {error}")

        sys.exit(0 if validation["status"] == "passed" else 1)

    elif args.generate_k8s_manifests:
        print("☸️  Generating Kubernetes manifests...")
        manifests = deployer.generate_kubernetes_manifests()
        print(f"Generated {len(manifests)} Kubernetes manifest files:")
        for manifest in manifests:
            print(f"  - {manifest}")

    elif args.setup_monitoring:
        print("📊 Setting up monitoring configuration...")
        configs = deployer.generate_monitoring_config()
        print(f"Generated {len(configs)} monitoring configuration files:")
        for config in configs:
            print(f"  - {config}")

    else:
        # Full deployment
        results = deployer.deploy()

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"📄 Results saved to {args.output}")

        sys.exit(0 if results["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
