SHELL := /usr/bin/env bash

.DEFAULT_GOAL := help

PYTHON ?= python
PIP ?= pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv: ## Create virtual environment (.venv)
	@test -d .venv || $(PYTHON) -m venv .venv
	@echo "Activate with: source .venv/bin/activate"

install: venv ## Install base + dev dependencies
	. .venv/bin/activate && $(PIP) install -r requirements.txt -r requirements-dev.txt

up: ## Start docker stack
	docker compose up -d --build

down: ## Stop docker stack
	docker compose down

logs: ## Tail pdf processor logs
	docker logs -f pdf_processor

eval-sample: ## Run evaluation suite against sample dataset
	$(PYTHON) scripts/eval_suite.py --eval-file eval/sample_eval.json --k 5 10 20 --ndcg-k 20

lint-docs: ## Run markdown lint + link check locally (requires markdownlint & lychee)
	markdownlint '**/*.md'

# === DOC SHORTCUTS (NEW) ===
docs-phases: ## Open development phases consolidated doc
	@echo "Opening phases summary..."; grep -q DEVELOPMENT_PHASES.md docs/phases/DEVELOPMENT_PHASES.md && sed -n '1,40p' docs/phases/DEVELOPMENT_PHASES.md || echo "Missing phases summary"

docs-accuracy: ## Open accuracy & testing consolidated doc
	@echo "Opening accuracy improvements summary..."; sed -n '1,60p' docs/testing/ACCURACY_IMPROVEMENTS.md

docs-ops: ## Open operations & monitoring guide
	@echo "Opening operations guide..."; sed -n '1,60p' docs/monitoring/OPERATIONS_GUIDE.md

docs-migrations: ## Open system migrations consolidated doc
	@echo "Opening migrations summary..."; sed -n '1,60p' docs/migrations/SYSTEM_MIGRATIONS.md

docs-structure: ## Show documentation structure overview
	@grep -n "Documentation Structure" README.md | head -1 || echo "Section not found"

# === DAILY MORNING CHECKLIST ===
morning: ## 🌅 Run complete daily morning checklist
	@echo "☀️ Good Morning! Starting system check..."
	@./scripts/daily_morning_checklist.sh || (echo "\n❌ Critical issues found! Check the log file." && exit 1)
	@echo "\n🚀 System ready for development work!"

daily-checklist: ## 🔍 Run automated daily checklist
	@echo "🌅 Running Daily Morning Checklist..."
	@./scripts/daily_morning_checklist.sh

advanced-health: ## 🔍 Run comprehensive system health analysis
	@echo "🔍 Running Advanced Health Analysis..."
	@./scripts/advanced_health_check.sh

end-of-day: ## 🌙 End of day routine (backup, commit, report)
	@echo "🌙 Starting End of Day Routine..."
	@./scripts/end_of_day.sh

health-check: ## 🏥 Quick health check of core services
	@echo "🏥 Quick Health Check..."
	@echo "=== Docker Compose Services vs Running Containers ==="
	@./scripts/compare_services.sh
	@echo "\n=== Testing Core Endpoints ==="
	@curl -f -s http://localhost:8008/health && echo "✅ Reranker OK" || echo "❌ Reranker FAIL"
	@curl -f -s http://localhost:11434/api/tags > /dev/null && echo "✅ Ollama-1 OK" || echo "❌ Ollama-1 FAIL"
	@curl -f -s http://localhost:11435/api/tags > /dev/null && echo "✅ Ollama-2 OK" || echo "❌ Ollama-2 FAIL"
	@curl -f -s http://localhost:11436/api/tags > /dev/null && echo "✅ Ollama-3 OK" || echo "❌ Ollama-3 FAIL"
	@curl -f -s http://localhost:11437/api/tags > /dev/null && echo "✅ Ollama-4 OK" || echo "❌ Ollama-4 FAIL"
	@curl -f -s http://localhost:8080 > /dev/null && echo "✅ Frontend OK" || echo "❌ Frontend FAIL"
	@curl -f -s http://localhost:6379 > /dev/null && echo "✅ Redis OK" || echo "❌ Redis FAIL" 
	@echo "\n=== System Resources ==="
	@df -h . | tail -1
	@free -h | head -2

check-logs: ## 📋 Show recent error logs from all containers
	@echo "🔍 Recent Error Logs (Last 24 Hours)..."
	@echo "=== PDF Processor ==="
	@docker logs --since="24h" pdf_processor 2>/dev/null | grep -E "(ERROR|FATAL|Exception)" | tail -5 || echo "No critical errors"
	@echo "=== Reranker ==="  
	@docker logs --since="24h" reranker 2>/dev/null | grep -E "(ERROR|FATAL|Exception)" | tail -5 || echo "No critical errors"
	@echo "=== Database ==="
	@docker logs --since="24h" pgvector 2>/dev/null | grep -E "(ERROR|FATAL|Exception)" | tail -5 || echo "No critical errors"

check-db: ## 🗄️ Check database integrity (orphans, empty docs, missing embeddings)
	@echo "🗄️ Database Integrity Check..."
	@docker exec pgvector psql -U postgres -d vector_db -c "SELECT 'Orphan Chunks' as check_type, COUNT(*) as count FROM document_chunks dc WHERE NOT EXISTS (SELECT 1 FROM documents d WHERE d.id = dc.document_id) UNION ALL SELECT 'Empty Documents' as check_type, COUNT(*) as count FROM documents d WHERE NOT EXISTS (SELECT 1 FROM document_chunks dc WHERE dc.document_id = d.id) UNION ALL SELECT 'Missing Embeddings' as check_type, COUNT(*) as count FROM document_chunks dc WHERE dc.embedding IS NULL;"

cleanup: ## 🧹 Weekly system cleanup (logs, cache, Docker)
	@echo "🧹 Running weekly system cleanup..."
	@echo "📋 Removing old backup files..."
	@find . -name "*.bak*" -type f -mtime +7 -delete 2>/dev/null || true
	@echo "📋 Cleaning old log files..."
	@find logs/ -type f -mtime +7 -delete 2>/dev/null || true
	@echo "📋 Removing Python cache files..."
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -o -name "*.tmp" -o -name ".DS_Store" -type f -delete 2>/dev/null || true
	@echo "🐳 Docker system cleanup..."
	@docker system prune -f --volumes 2>/dev/null || echo "Docker cleanup skipped (not available)"
	@echo "✅ Weekly cleanup completed"

test: ## Run pytest
	$(PYTHON) -m pytest -q

# === COMPREHENSIVE TEST FRAMEWORK ===
test-all: ## 🧪 Run all ring test suites with performance metrics  
	$(PYTHON) test_runner.py --all --verbose --performance

test-ring1: ## 🔒 Run Ring 1 enforced coverage tests (blocking)
	$(PYTHON) test_runner.py --ring 1 --verbose

test-ring2: ## 📄 Run Ring 2 PDF processing pipeline tests
	$(PYTHON) test_runner.py --ring 2 --verbose

test-ring3: ## ⚡ Run Ring 3 advanced functionality tests
	$(PYTHON) test_runner.py --ring 3 --verbose

test-validate: ## ✅ Quick validation of all ring stability
	$(PYTHON) test_runner.py --validate

test-report: ## 📊 Generate comprehensive quality report
	$(PYTHON) test_runner.py --all --performance --report test_quality_report.json
	@echo "📁 Report generated: test_quality_report.json"

test-quick: ## ⚡ Quick test execution (Ring 1 + core Ring 2)
	$(PYTHON) test_runner.py --ring 1 2

# === QUALITY MONITORING & CONTINUOUS IMPROVEMENT ===
quality-track: ## 📊 Track current quality metrics
	$(PYTHON) quality_monitor.py --track

quality-analyze: ## 📈 Analyze quality trends (default: 30 days)
	$(PYTHON) quality_monitor.py --analyze

quality-report: ## 📋 Generate HTML quality dashboard
	$(PYTHON) quality_monitor.py --report quality_dashboard.html --days 30
	@echo "📁 Quality dashboard: quality_dashboard.html"

quality-check-regressions: ## ⚠️ Check for quality regressions
	$(PYTHON) quality_monitor.py --regressions

quality-full: ## 🔍 Complete quality monitoring cycle
	@echo "🔍 Running complete quality monitoring cycle..."
	$(PYTHON) quality_monitor.py --track
	$(PYTHON) quality_monitor.py --analyze
	$(PYTHON) quality_monitor.py --report quality_dashboard.html
	@echo "📁 Dashboard ready: quality_dashboard.html"

# === INTELLIGENT TEST GENERATION & EXPANSION ===
test-generate-analyze: ## 🔍 Analyze project structure and identify coverage gaps
	$(PYTHON) test_generator.py --analyze

test-generate-module: ## 🧪 Generate tests for specific module (use MODULE=path)
	$(PYTHON) test_generator.py --generate --module $(MODULE) --output tests/generated

test-expand-ring1: ## 📈 Expand Ring 1 test coverage with intelligent generation
	$(PYTHON) test_generator.py --expand --ring 1

test-expand-ring2: ## 📈 Expand Ring 2 test coverage with intelligent generation
	$(PYTHON) test_generator.py --expand --ring 2

test-expand-ring3: ## 📈 Expand Ring 3 test coverage with intelligent generation
	$(PYTHON) test_generator.py --expand --ring 3

test-generate-all: ## 🚀 Complete test generation cycle (analyze + expand all rings)
	@echo "🚀 Running complete intelligent test generation cycle..."
	$(PYTHON) test_generator.py --analyze
	$(PYTHON) test_generator.py --expand --ring 1
	$(PYTHON) test_generator.py --expand --ring 2
	$(PYTHON) test_generator.py --expand --ring 3
	@echo "✅ Intelligent test generation complete - check tests/generated/"

recreate-db: ## (Destructive) Remove Postgres volume and restart
	docker compose down
	docker volume rm Technical-Service-Assistant_pgvector_data || true
	docker compose up -d --build

.PHONY: help venv install up down logs eval-sample lint-docs test recreate-db cleanup advanced-health end-of-day quality-track quality-analyze quality-report quality-check-regressions quality-full
