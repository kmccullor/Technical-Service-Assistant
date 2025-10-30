# Documentation Index

Use this map to locate the most relevant references for the Technical Service Assistant platform. Paths are relative to the repository root unless noted otherwise.

## 📚 Core Documentation
- **Project Overview**
  - [../README.md](../README.md) – Entry point with quick start, service summary, and key commands.
  - [../ARCHITECTURE.md](../ARCHITECTURE.md) – Deep dive into service boundaries, data flow, and configuration surface.
  - [../DEVELOPMENT.md](../DEVELOPMENT.md) – Local environment setup, tooling guidance, and contributor workflows.
  - [../CODE_QUALITY.md](../CODE_QUALITY.md) – Formatting, linting, typing, and coverage standards enforced in CI.
- **Operations & Support**
  - [../TROUBLESHOOTING.md](../TROUBLESHOOTING.md) – Common failure modes, diagnostics, and recovery playbooks.
  - [../SECURITY.md](../SECURITY.md) – Secrets management, hardening considerations, and environment policies.
  - [server_documentation.md](server_documentation.md) – Server roles, network layout, and service credentials.

## 🔧 Technical Deep Dives
- **System Components**
  - [REASONING_ENGINE.md](REASONING_ENGINE.md) – Model routing, inference pathways, and orchestration details.
  - [EMBEDDINGS.md](EMBEDDINGS.md) – Embedding model selection, performance benchmarks, and rollout history.
  - [HYBRID_SEARCH.md](HYBRID_SEARCH.md) – Retrieval strategy, hybrid scoring, and reranking configuration.
  - [DATABASE_REFERENCE.md](DATABASE_REFERENCE.md) – Tables, indices, and pgvector integration guide.
- **Configuration & Data Pipelines**
  - [REMOTE_DEPLOYMENT.md](REMOTE_DEPLOYMENT.md) – Environment variable matrix and production deployment requirements.
  - [ENV_CONFIGURATION_MIGRATION.md](ENV_CONFIGURATION_MIGRATION.md) – Migration history for environment settings.
  - [POSTGRESQL_INSTRUCTIONS.md](POSTGRESQL_INSTRUCTIONS.md) – Operational playbook for PostgreSQL + pgvector.
  - [MAINTENANCE.md](MAINTENANCE.md) – Scheduled jobs, cleanup tasks, and long-running pipeline expectations.

## 🧪 Testing & Quality
- [COMPREHENSIVE_TEST_FRAMEWORK_COMPLETE.md](COMPREHENSIVE_TEST_FRAMEWORK_COMPLETE.md) – Overview of the ring-based pytest orchestration.
- [COVERAGE_RING_STATUS.md](COVERAGE_RING_STATUS.md) – Coverage targets and historical compliance.
- [TEST_QUALITY_DASHBOARD.md](TEST_QUALITY_DASHBOARD.md) – Interpretation guide for generated QA dashboards.
- [QUALITY_MONITORING_SYSTEM_COMPLETE.md](QUALITY_MONITORING_SYSTEM_COMPLETE.md) – Metrics instrumentation and alerting integrations.
- [analysis/LINTING_REPORT.md](analysis/LINTING_REPORT.md) – Audit of linting/tooling scope with recommendations.

## 🛡 Operations & Monitoring
- [ADVANCED_MONITORING.md](ADVANCED_MONITORING.md) – Prometheus integration, Grafana dashboards, and alert wiring.
- [DAILY_WORKFLOW.md](DAILY_WORKFLOW.md) – Daily health check, report generation, and maintenance cadence.
- [SENSUS_AMI_QUERY_WORKFLOW.md](SENSUS_AMI_QUERY_WORKFLOW.md) – End-to-end workflow for AMI data synchronization.
- [AMI_QUERY_QUICK_REFERENCE.md](AMI_QUERY_QUICK_REFERENCE.md) – Cheatsheet for AMI query commands and parameters.
- `monitoring/` – Monitoring checklists and runbooks (e.g., `OPERATIONS_GUIDE.md`, `DAILY_CHECKLIST_QUICK_START.md`).

## 📂 Specialized References
- [PRIVACY_CLASSIFICATION.md](PRIVACY_CLASSIFICATION.md) – PII detection pipeline and classification taxonomy.
- [PHASE3A_MULTIMODAL.md](PHASE3A_MULTIMODAL.md) – Multimodal ingestion/processing enhancements.
- [ADMIN_CREDENTIALS.md](ADMIN_CREDENTIALS.md) – Seeded account reference and rotation procedures.
- [SCRIPTS.md](SCRIPTS.md) – Catalog of automation scripts with usage hints.
- [analysis/PROJECT_ANALYSIS_2025_10_07.md](analysis/PROJECT_ANALYSIS_2025_10_07.md) – Recent program-level analysis.
- [analysis/PROJECT_STATUS_SEPTEMBER_2025.md](analysis/PROJECT_STATUS_SEPTEMBER_2025.md) – Latest status dashboard for leadership.

## 🗄 Archive & Historical Notes
- `archive/` – Historical implementation logs, superseded designs, and deprecated procedures retained for reference.
- `analysis/` – Research artifacts, retrospectives, and planning documents (see directory listings above).
- `phases/` – Milestone documentation and phased release notes.

## 🚀 Quick Navigation by Role
- **New Developers**
  - [../README.md](../README.md) → [../ARCHITECTURE.md](../ARCHITECTURE.md) → [../DEVELOPMENT.md](../DEVELOPMENT.md)
  - Validate quality baselines with [../CODE_QUALITY.md](../CODE_QUALITY.md) and [COMPREHENSIVE_TEST_FRAMEWORK_COMPLETE.md](COMPREHENSIVE_TEST_FRAMEWORK_COMPLETE.md).
- **Operations & SRE**
  - Start with [ADVANCED_MONITORING.md](ADVANCED_MONITORING.md), [DAILY_WORKFLOW.md](DAILY_WORKFLOW.md), and [server_documentation.md](server_documentation.md).
  - Use [REMOTE_DEPLOYMENT.md](REMOTE_DEPLOYMENT.md) and [POSTGRESQL_INSTRUCTIONS.md](POSTGRESQL_INSTRUCTIONS.md) when rolling changes.
- **Feature Delivery**
  - Review [../CHANGELOG.md](../CHANGELOG.md) for recent work, then consult component docs (e.g., [REASONING_ENGINE.md](REASONING_ENGINE.md), [HYBRID_SEARCH.md](HYBRID_SEARCH.md)).
  - Align with quality gate expectations via [../CONTRIBUTING.md](../CONTRIBUTING.md) and [../CODE_QUALITY.md](../CODE_QUALITY.md).
