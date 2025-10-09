#!/usr/bin/env python3
"""
Create demonstration of standardized Log4 logging across all key Python scripts
"""

import sys
from datetime import datetime

# Setup proper paths
sys.path.append("/home/kmccullor/Projects/Technical-Service-Assistant")
from utils.logging_config import setup_logging

# Example usage for each major script category

# 1. Main service scripts (reranker, pdf_processor)
service_logger = setup_logging(
    program_name="technical_service_assistant_service",
    log_level="INFO",
    log_file=f'/home/kmccullor/Projects/Technical-Service-Assistant/logs/service_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True,
)

service_logger.info("Technical Service Assistant service starting up")
service_logger.info("Configuration loaded successfully")
service_logger.debug("Debug mode enabled for development")
service_logger.warning("Warning: This is a sample warning message")
service_logger.error("Error: This is a sample error message")

# 2. Utility scripts (bin/ directory)
util_logger = setup_logging(
    program_name="utility_script", log_level="INFO", console_output=True  # No file logging for utilities
)

util_logger.info("Starting utility script execution")
util_logger.info("Processing embedding benchmarks")
util_logger.info("Benchmark complete - results saved")

# 3. Testing scripts
test_logger = setup_logging(
    program_name="test_runner",
    log_level="DEBUG",
    log_file=f'/home/kmccullor/Projects/Technical-Service-Assistant/logs/tests_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True,
)

test_logger.info("Starting test suite")
test_logger.debug("Database connection test")
test_logger.info("All connectivity tests passed")

# 4. Analysis scripts
analysis_logger = setup_logging(
    program_name="analysis_engine",
    log_level="INFO",
    log_file=f'/home/kmccullor/Projects/Technical-Service-Assistant/logs/analysis_{datetime.now().strftime("%Y%m%d")}.log',
    console_output=True,
)

analysis_logger.info("Starting accuracy analysis")
analysis_logger.info("Enhanced retrieval performance: 92.3% accuracy")
analysis_logger.warning("Model performance below threshold on complex queries")

print("\\n🎯 Log4 Standardization Demo Complete!")
print("\\nKey features implemented:")
print("- Subsecond timestamps (YYYY-MM-DD HH:MM:SS.mmm)")
print("- Program Name | Module | Severity | Message format")
print("- Consistent file and console logging")
print("- Centralized configuration via utils.logging_config")

print("\\nExample log entries generated:")
service_logger.info("Demo complete - all logging systems operational")
analysis_logger.info("Log4 standardization successful across all Python scripts")
