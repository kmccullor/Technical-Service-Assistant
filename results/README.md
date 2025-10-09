# Results & Artifacts

This directory contains generated output artifacts, benchmarking results, flaky run logs, and evaluation captures.

## Contents
- Phase accuracy & benchmarking JSON snapshots
- Flaky run diagnostic JSON files
- Test framework or A/B comparison outputs

## Retention Policy
Artifacts older than 30 days should be reviewed and optionally archived or purged unless needed for audit or regression tracking.

## Recommended Workflow
1. Generate evaluation: `python experiments/validate_accuracy.py`
2. Store output JSON here (auto-moved from root during cleanup)
3. Reference in reports or dashboards (never manually modify JSON)

## Excluded From Coverage
These artifacts are not part of test coverage or runtime logic.
