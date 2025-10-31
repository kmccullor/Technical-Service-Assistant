#!/usr/bin/env python3
"""
Fix common linting issues in Python files: trailing whitespace and blank line whitespace.
"""

from pathlib import Path


def fix_whitespace_issues(file_path: Path):
    """Fix whitespace issues in a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        fixed_lines = []
        changes_made = 0

        for line_num, line in enumerate(lines, 1):
            original_line = line

            # Remove trailing whitespace
            line = line.rstrip() + "\n" if line.endswith("\n") else line.rstrip()

            # Fix blank lines with whitespace (make them truly blank)
            if line.strip() == "" and line != "\n":
                line = "\n"

            if line != original_line:
                changes_made += 1
                print(f"  Line {line_num}: Fixed whitespace")

            fixed_lines.append(line)

        # Ensure file ends with newline
        if fixed_lines and not fixed_lines[-1].endswith("\n"):
            fixed_lines[-1] += "\n"
            changes_made += 1
            print(f"  Added newline at end of file")

        if changes_made > 0:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(fixed_lines)
            print(f"Fixed {changes_made} whitespace issues in {file_path}")
        else:
            print(f"No whitespace issues found in {file_path}")

        return changes_made

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return 0


def main():
    """Fix whitespace issues in specified Python files."""
    files_to_fix = ["test_security_patterns.py", "test_query_expansion.py", "pdf_processor/pdf_utils_enhanced.py"]

    total_changes = 0

    for file_path in files_to_fix:
        path = Path(file_path)
        if path.exists():
            print(f"\nFixing whitespace in {file_path}...")
            changes = fix_whitespace_issues(path)
            total_changes += changes
        else:
            print(f"File not found: {file_path}")

    print(f"\nTotal changes made: {total_changes}")


if __name__ == "__main__":
    main()
