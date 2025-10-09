# Project Documentation Cleanup Plan

## Analysis of Root Directory Markdown Files

### Core Documentation (Keep in Root)
- `README.md` - Main project documentation
- `ARCHITECTURE.md` - System architecture overview  
- `DEVELOPMENT.md` - Development setup and guidelines
- `CODE_QUALITY.md` - Code quality standards
- `CONTRIBUTING.md` - Contribution guidelines
- `CHANGELOG.md` - Version history
- `TROUBLESHOOTING.md` - Common issues and solutions

### Operations & Deployment (Move to docs/operations/)
- `DEPLOYMENT_GUIDE.md`
- `SCALING_PLAN.md` 
- `SECURITY_IMPLEMENTATION.md`
- `ENTERPRISE_DEPLOYMENT_COMPLETE.md`
- `RBAC_FIX_SUMMARY.md`

### Monitoring & Alerting (Move to docs/monitoring/)
- `ALERTING_SETUP.md`
- `EOD_REPORTING.md`
- `GMAIL_SETUP_GUIDE.md`
- `LOG_ANALYSIS_GUIDE.md`
- `CRONTAB_SETUP_GUIDE.md`
- `DAILY_CHECKLIST_QUICK_START.md`
- `DAILY_MORNING_CHECKLIST.md`

### Phase Completion Reports (Consolidate to docs/phases/)
- `PHASE_2_ACCURACY_ANALYSIS.md`
- `PHASE_3A_COMPLETION.md`
- `PHASE3A_COMPLETION_SUMMARY.md`
- `PHASE_3B_COMPLETION.md`
- `PHASE_3B_PLAN.md`
- `PHASE_4A_PLAN.md`

### Accuracy & Testing (Consolidate to docs/testing/)
- `ACCURACY_IMPROVEMENTS_SUMMARY.md`
- `ACCURACY_IMPROVEMENT_PLAN.md`
- `ACCURACY_IMPROVEMENT_POTENTIAL.md`
- `ACCURACY_RETEST_RESULTS.md`
- `AI_CATEGORIZATION_SUCCESS.md`
- `DOCKER_RAG_VALIDATION_SUCCESS.md`
- `DOCUMENT_ACCURACY_VALIDATION_REPORT.md`
- `RAG_VALIDATION_COMPREHENSIVE_REPORT.md`
- `RAG_VALIDATION_INTEGRATION_COMPLETE.md`
- `AUTOMATED_TEST_MAINTENANCE_COMPLETE.md`

### Migration & Updates (Consolidate to docs/migrations/)
- `MIGRATION_SERVICE_RENAME.md`
- `MIGRATION_SUCCESS_REPORT.md`
- `VECTOR_DATABASE_MIGRATION_COMPLETE.md`
- `MODEL_VERSION_PINNING_SUMMARY.md`
- `PROJECT_RENAME_SUMMARY.md`
- `PROJECT_UPDATE_COMPLETE.md`
- `DOCUMENTATION_UPDATE_SUMMARY_2025_10_07.md`

### Analysis & Planning (Consolidate to docs/analysis/)
- `NEXT_STEPS_ANALYSIS.md`
- `PLANNING_TASK_REVIEW.md`
- `PROJECT_ANALYSIS_2025_10_07.md`
- `PROJECT_STATUS_SEPTEMBER_2025.md`
- `IMPLEMENTATION_GUIDE.md`
- `IMPLEMENTATION_RECOMMENDATIONS.md`
- `LINTING_REPORT.md`
- `OCR_METRICS_INTEGRATION_REPORT.md`

### Temporary/Archive Files (Move to archive/)
- `test_acronym_extraction.md`
- `ACRONYM_INDEX.md`
- `PLANNING.md`
- `TASKS.md`

## Consolidation Actions

### Create New Documentation Structure
```
docs/
├── operations/
├── monitoring/  
├── phases/
├── testing/
├── migrations/
├── analysis/
└── archive/
```

### Consolidation Files to Create
1. `docs/phases/DEVELOPMENT_PHASES.md` - Consolidate all phase reports
2. `docs/testing/ACCURACY_IMPROVEMENTS.md` - Consolidate accuracy reports
3. `docs/migrations/SYSTEM_MIGRATIONS.md` - Consolidate migration reports
4. `docs/analysis/PROJECT_ANALYSIS.md` - Consolidate analysis reports
5. `docs/monitoring/OPERATIONS_GUIDE.md` - Consolidate operational guides

## Expected Outcome
- Root directory: 7 core documentation files
- Organized docs/ structure with logical groupings
- Consolidated reports reduce file count by ~60%
- Improved navigation and maintenance