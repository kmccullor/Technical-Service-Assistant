#!/usr/bin/env python3
"""
Acronym and definition extraction for technical documents.
Identifies acronyms, abbreviations, and their definitions from document text.
"""

import re
from datetime import datetime
from typing import Dict, Optional, Set


class AcronymExtractor:
    """Extract acronyms and their definitions from document text."""

    def __init__(self):
        """Initialize the acronym extractor with patterns and filters."""

        # Pattern for acronyms in parentheses: "Full Name (ACRONYM)"
        self.parentheses_pattern = re.compile(r"\b([A-Z][a-zA-Z\s&-]{3,50}?)\s*\(([A-Z]{2,8})\)", re.MULTILINE)

        # Pattern for standalone acronyms (2-8 uppercase letters)
        self.standalone_pattern = re.compile(r"\b([A-Z]{2,8})\b")

        # Pattern for definitions with colon: "ACRONYM: definition"
        self.colon_pattern = re.compile(r"\b([A-Z]{2,8})\s*:\s*([A-Z][a-zA-Z\s,.-]{5,80})(?:[.!?]|\s|$)", re.MULTILINE)

        # Pattern for definitions with dash: "ACRONYM - definition"
        self.dash_pattern = re.compile(
            r"\b([A-Z]{2,8})\s*[-–—]\s*([A-Z][a-zA-Z\s,.-]{5,80})(?:[.!?]|\s|$)", re.MULTILINE
        )

        # Common words to filter out (not real acronyms)
        self.filter_words = {
            "THE",
            "AND",
            "FOR",
            "ARE",
            "BUT",
            "NOT",
            "YOU",
            "ALL",
            "CAN",
            "HAD",
            "HER",
            "WAS",
            "ONE",
            "OUR",
            "OUT",
            "DAY",
            "GET",
            "USE",
            "MAN",
            "NEW",
            "NOW",
            "WAY",
            "MAY",
            "SAY",
            "SEE",
            "HIM",
            "TWO",
            "HOW",
            "ITS",
            "WHO",
            "DID",
            "YES",
            "HIS",
            "HAS",
            "LET",
            "PUT",
            "TOO",
            "OLD",
            "ANY",
            "APP",
            "SUN",
            "SET",
            "RUN",
            "HOT",
            "CUT",
            "LET",
            "FUN",
            "END",
            "WHY",
            "OFF",
        }

        # Technical domain indicators (increase confidence for acronyms)
        self.technical_indicators = {
            "protocol",
            "interface",
            "system",
            "network",
            "service",
            "application",
            "database",
            "server",
            "client",
            "API",
            "SDK",
            "framework",
            "library",
            "standard",
            "specification",
            "technology",
            "platform",
            "architecture",
        }

    def extract_from_text(self, text: str, document_name: str = "") -> Dict[str, str]:
        """
        Extract acronyms and definitions from text.

        Args:
            text: Document text to analyze
            document_name: Name of source document for context

        Returns:
            Dictionary mapping acronyms to their definitions
        """
        acronyms = {}

        # Method 1: Extract from parentheses patterns
        for match in self.parentheses_pattern.finditer(text):
            definition, acronym = match.groups()
            if self._is_valid_acronym(acronym) and self._is_valid_definition(definition):
                # Clean up definition
                clean_def = self._clean_definition(definition.strip())
                if clean_def:
                    acronyms[acronym] = clean_def

        # Method 2: Extract from colon patterns
        for match in self.colon_pattern.finditer(text):
            acronym, definition = match.groups()
            if self._is_valid_acronym(acronym) and self._is_valid_definition(definition):
                clean_def = self._clean_definition(definition.strip())
                if clean_def:
                    acronyms[acronym] = clean_def

        # Method 3: Extract from dash patterns
        for match in self.dash_pattern.finditer(text):
            acronym, definition = match.groups()
            if self._is_valid_acronym(acronym) and self._is_valid_definition(definition):
                clean_def = self._clean_definition(definition.strip())
                if clean_def:
                    acronyms[acronym] = clean_def

        # Method 4: Context-based extraction for standalone acronyms
        standalone_acronyms = self._extract_contextual_acronyms(text)
        acronyms.update(standalone_acronyms)

        return acronyms

    def _is_valid_acronym(self, acronym: str) -> bool:
        """Check if a string is a valid acronym."""
        if not acronym or len(acronym) < 2 or len(acronym) > 8:
            return False

        if acronym in self.filter_words:
            return False

        # Must be mostly uppercase letters
        if not re.match(r"^[A-Z][A-Z0-9]*$", acronym):
            return False

        # Avoid single letter repetitions like "AAA", "BBB"
        if len(set(acronym)) == 1 and len(acronym) > 2:
            return False

        return True

    def _is_valid_definition(self, definition: str) -> bool:
        """Check if a string is a valid definition."""
        if not definition or len(definition.strip()) < 5:
            return False

        # Must start with uppercase letter
        if not definition.strip()[0].isupper():
            return False

        # Should contain some lowercase letters (not all caps)
        if definition.isupper() and len(definition) > 20:
            return False

        # Filter out definitions that are just lists of acronyms
        words = definition.split()
        if len(words) > 1 and sum(1 for w in words if w.isupper() and len(w) > 1) > len(words) * 0.7:
            return False

        return True

    def _clean_definition(self, definition: str) -> str:
        """Clean up extracted definitions by removing common prefixes and artifacts."""
        if not definition:
            return ""

        # Remove common prefixes that get captured
        prefixes_to_remove = ["the ", "The ", "a ", "A ", "an ", "An "]
        for prefix in prefixes_to_remove:
            if definition.startswith(prefix):
                definition = definition[len(prefix) :]
                break

        # Remove trailing punctuation artifacts
        definition = definition.rstrip(".,;:-")

        # Ensure it starts with capital letter
        if definition and definition[0].islower():
            definition = definition[0].upper() + definition[1:]

        return definition.strip()

    def _extract_contextual_acronyms(self, text: str) -> Dict[str, str]:
        """Extract acronyms based on context and surrounding text."""
        contextual = {}

        # Look for patterns like "The XYZ system" or "using ABC protocol"
        context_patterns = [
            re.compile(
                r"\b(?:the|a|an)\s+([A-Z]{2,6})\s+(system|protocol|interface|service|application|network|database|server|platform)\b",
                re.IGNORECASE,
            ),
            re.compile(r"\b([A-Z]{2,6})\s+(is|are|was|were)\s+(?:a|an|the)\s+([a-zA-Z\s]{5,30})\b", re.IGNORECASE),
            re.compile(r"\busing\s+([A-Z]{2,6})\s+(?:for|to|as)\s+([a-zA-Z\s]{5,30})\b", re.IGNORECASE),
        ]

        for pattern in context_patterns:
            for match in pattern.finditer(text):
                if len(match.groups()) >= 2:
                    acronym = match.group(1).upper()
                    context = match.group(2) if len(match.groups()) == 2 else match.group(3)

                    if self._is_valid_acronym(acronym) and context:
                        # Create a contextual definition
                        definition = f"{context.strip().title()}"
                        if self._is_valid_definition(definition):
                            contextual[acronym] = definition

        return contextual

    def merge_acronyms(self, existing: Dict[str, str], new_acronyms: Dict[str, str]) -> Dict[str, str]:
        """
        Merge new acronyms with existing ones, preferring more detailed definitions.

        Args:
            existing: Current acronym dictionary
            new_acronyms: Newly extracted acronyms

        Returns:
            Merged dictionary with best definitions
        """
        merged = existing.copy()

        for acronym, definition in new_acronyms.items():
            if acronym not in merged:
                merged[acronym] = definition
            else:
                # Prefer longer, more detailed definitions
                if len(definition) > len(merged[acronym]):
                    merged[acronym] = definition

        return merged

    def format_for_markdown(self, acronyms: Dict[str, str], source_docs: Optional[Set[str]] = None) -> str:
        """
        Format acronyms as markdown content for ACRONYM_INDEX.md.

        Args:
            acronyms: Dictionary of acronyms and definitions
            source_docs: Set of source document names

        Returns:
            Formatted markdown string
        """
        if not acronyms:
            return ""

        # Sort alphabetically
        sorted_acronyms = sorted(acronyms.items())

        lines = []
        lines.append("# Technical Acronyms & Definitions")
        lines.append("")
        lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")

        if source_docs:
            lines.append(f"*Extracted from {len(source_docs)} technical documents*")
            lines.append("")

        current_letter = ""
        for acronym, definition in sorted_acronyms:
            # Add letter section headers
            if acronym[0] != current_letter:
                current_letter = acronym[0]
                lines.append(f"## {current_letter}")
                lines.append("")

            # Format as definition list
            lines.append(f"**{acronym}**")
            lines.append(f": {definition}")
            lines.append("")

        return "\n".join(lines)


def load_existing_acronyms(file_path: str) -> Dict[str, str]:
    """Load existing acronyms from ACRONYM_INDEX.md file."""
    acronyms = {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse existing markdown format
        pattern = re.compile(r"\*\*([A-Z]{2,8})\*\*\s*:\s*([^\n]+)", re.MULTILINE)
        for match in pattern.finditer(content):
            acronym, definition = match.groups()
            acronyms[acronym.strip()] = definition.strip()

    except FileNotFoundError:
        pass  # File doesn't exist yet
    except Exception as e:
        print(f"Warning: Could not load existing acronyms: {e}")

    return acronyms


def save_acronyms_to_file(acronyms: Dict[str, str], file_path: str, source_docs: Optional[Set[str]] = None):
    """Save acronyms dictionary to ACRONYM_INDEX.md file."""
    extractor = AcronymExtractor()
    markdown_content = extractor.format_for_markdown(acronyms, source_docs)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"Updated {file_path} with {len(acronyms)} acronyms")
    except Exception as e:
        print(f"Error saving acronyms to {file_path}: {e}")


if __name__ == "__main__":
    # Test the extractor
    test_text = """
    The Remote Network Interface (RNI) system uses Advanced Metering Infrastructure (AMI)
    to communicate with smart meters. The API provides RESTful services for data access.
    DNS: Domain Name System is used for address resolution.
    HTTP - Hypertext Transfer Protocol for web communication.
    """

    extractor = AcronymExtractor()
    acronyms = extractor.extract_from_text(test_text)

    print("Extracted acronyms:")
    for acronym, definition in acronyms.items():
        print(f"  {acronym}: {definition}")
