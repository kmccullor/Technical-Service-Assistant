#!/usr/bin/env python3
"""
Technical Service Assistant - Installation Setup
==============================================

This setup script creates a deployable package for the Technical Service Assistant
that can be installed on other servers with all necessary dependencies and configuration.
"""

from setuptools import setup, find_packages
import os
import sys

# Read version from config.py
version = "1.0.0"

# Read README for long description
def read_readme():
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Technical Service Assistant - AI-powered PDF processing and search system"

# Read requirements
def read_requirements(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return []

# Core dependencies
install_requires = read_requirements("requirements.txt")

# Development dependencies
dev_requires = read_requirements("requirements-dev.txt")

setup(
    name="technical-service-assistant",
    version=version,
    description="AI-powered PDF processing and hybrid search system with intelligent routing",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Technical Service Assistant Team",
    author_email="support@technical-service-assistant.local",
    url="https://github.com/technical-service-assistant/technical-service-assistant",
    
    # Package discovery
    packages=find_packages(exclude=["tests*", "backup*", "logs*", "uploads*", "htmlcov*"]),
    include_package_data=True,
    
    # Dependencies
    install_requires=install_requires,
    extras_require={
        "dev": dev_requires,
        "monitoring": [
            "prometheus-client>=0.17.0",
            "grafana-api>=1.0.3",
        ],
        "enterprise": [
            "python-ldap>=3.4.0",
            "cryptography>=41.0.0",
        ],
    },
    
    # Python version requirement
    python_requires=">=3.9",
    
    # Entry points for command-line scripts
    entry_points={
        "console_scripts": [
            "tsa-server=reranker.app:main",
            "tsa-processor=pdf_processor.process_pdfs:main",
            "tsa-monitor=monitoring.performance_monitor.performance_monitor:main",
            "tsa-setup=scripts.install:main",
            "tsa-migrate=migrations.run_migrations:main",
        ],
    },
    
    # Package data
    package_data={
        "": [
            "*.md", "*.txt", "*.yml", "*.yaml", "*.json", "*.sql",
            "*.html", "*.css", "*.js", "*.conf", "*.ini",
            "docs/**/*", "migrations/**/*", "ollama_config/**/*",
            "deployment/**/*", "frontend/**/*",
        ],
    },
    
    # Classifiers
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Text Processing :: Indexing",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
    ],
    
    # Keywords
    keywords="ai pdf search rag vector-database ollama embeddings nlp",
    
    # Project URLs
    project_urls={
        "Documentation": "https://github.com/technical-service-assistant/technical-service-assistant/docs",
        "Source": "https://github.com/technical-service-assistant/technical-service-assistant",
        "Tracker": "https://github.com/technical-service-assistant/technical-service-assistant/issues",
    },
    
    # Zip safe
    zip_safe=False,
)