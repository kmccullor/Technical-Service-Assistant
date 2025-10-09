#!/usr/bin/env python3
"""
Script to update all Python files to use standardized Log4 logging
"""
import os
import re
import sys
from pathlib import Path

# Add utils to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from logging_config import setup_logging

logger = setup_logging(program_name="update_logging", log_level="INFO", console_output=True)


def find_python_files(directory: str) -> list:
    """Find all Python files in directory and subdirectories."""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    return python_files


def has_logging_import(content: str) -> bool:
    """Check if file already imports logging."""
    return re.search(r"^import logging|^from logging", content, re.MULTILINE) is not None


def has_standard_logging_import(content: str) -> bool:
    """Check if file already imports our standard logging."""
    return "from utils.logging_config import" in content


def add_standard_logging(file_path: str) -> bool:
    """Add standardized logging to a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Skip if already has standard logging
        if has_standard_logging_import(content):
            logger.info(f"SKIP | {file_path} | already has standard logging")
            return False

        # Skip if no logging imports at all (might not need logging)
        if not has_logging_import(content):
            logger.info(f"SKIP | {file_path} | no logging imports found")
            return False

        lines = content.split("\n")

        # Find import section
        import_end_idx = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith("#") and not line.startswith('"""') and not line.startswith("'''"):
                if line.startswith("import ") or line.startswith("from "):
                    import_end_idx = i + 1
                else:
                    break

        # Add standard logging import
        program_name = Path(file_path).stem

        # Insert imports
        new_lines = lines[:import_end_idx]
        new_lines.append("from datetime import datetime")
        new_lines.append("from utils.logging_config import setup_logging")
        new_lines.append("")

        # Add logging setup
        log_setup = f"""# Setup standardized Log4 logging
logger = setup_logging(
    program_name='{program_name}',
    log_level='INFO',
    log_file=f'/app/logs/{program_name}_{{datetime.now().strftime("%Y%m%d")}}.log',
    console_output=True
)"""

        new_lines.append(log_setup)
        new_lines.append("")
        new_lines.extend(lines[import_end_idx:])

        # Replace old logging patterns
        new_content = "\n".join(new_lines)

        # Replace basic logging setup patterns
        old_patterns = [
            r"logging\.basicConfig\([^)]*\)",
            r"logger = logging\.getLogger\([^)]*\)",
            r"import logging\n",
            r"from logging import [^\n]*\n",
        ]

        for pattern in old_patterns:
            new_content = re.sub(pattern, "", new_content)

        # Clean up multiple empty lines
        new_content = re.sub(r"\n\n\n+", "\n\n", new_content)

        # Write back
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(f"UPDATE | {file_path} | standardized logging added")
        return True

    except Exception as e:
        logger.error(f"ERROR | {file_path} | {str(e)}")
        return False


def main():
    """Main function to update all Python files."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    logger.info(f"Starting logging standardization in {base_dir}")

    # Key directories to process
    key_dirs = ["pdf_processor", "reranker", "bin", "scripts", "tests"]

    # Individual files to process
    key_files = [
        "test_connectivity.py",
        "config.py",
        "enhanced_retrieval.py",
        "hybrid_search.py",
        "semantic_chunking.py",
    ]

    updated_count = 0
    total_count = 0

    # Process directories
    for dir_name in key_dirs:
        dir_path = os.path.join(base_dir, dir_name)
        if os.path.exists(dir_path):
            python_files = find_python_files(dir_path)
            for file_path in python_files:
                total_count += 1
                if add_standard_logging(file_path):
                    updated_count += 1

    # Process individual files
    for file_name in key_files:
        file_path = os.path.join(base_dir, file_name)
        if os.path.exists(file_path):
            total_count += 1
            if add_standard_logging(file_path):
                updated_count += 1

    logger.info(f"Logging standardization complete: {updated_count}/{total_count} files updated")


if __name__ == "__main__":
    main()
