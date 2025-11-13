#!/usr/bin/env python3
"""
Export acronyms from the database to ACRONYM_INDEX.md file.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings
import psycopg2


def export_acronyms_to_markdown():
    """Export all acronyms from database to ACRONYM_INDEX.md."""
    settings = get_settings()

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password
        )
        cursor = conn.cursor()

        # Get all acronyms ordered by acronym
        cursor.execute("""
            SELECT acronym, definition, confidence_score, source_documents, is_verified
            FROM acronyms
            ORDER BY acronym
        """)

        acronyms = cursor.fetchall()

        # Generate markdown content
        lines = []
        lines.append("# Technical Acronyms & Definitions")
        lines.append("")
        lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")
        lines.append(f"*Total acronyms: {len(acronyms)}*")
        lines.append("")

        current_letter = ""
        for acronym, definition, confidence, sources, verified in acronyms:
            # Add letter section headers
            if acronym[0] != current_letter:
                current_letter = acronym[0]
                lines.append(f"## {current_letter}")
                lines.append("")

            # Format as definition list
            lines.append(f"**{acronym}**")
            lines.append(f": {definition}")

            # Add metadata if not verified or low confidence
            if not verified or confidence < 0.8:
                metadata = []
                if confidence < 0.8:
                    metadata.append(f"Confidence: {confidence:.1f}")
                if not verified:
                    metadata.append("Not verified")
                if sources:
                    metadata.append(f"Sources: {', '.join(sources[:2])}")  # Show first 2 sources
                if metadata:
                    lines.append(f"  _{'; '.join(metadata)}_")

            lines.append("")

        # Write to file
        content = "\n".join(lines)
        with open("ACRONYM_INDEX.md", "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Exported {len(acronyms)} acronyms to ACRONYM_INDEX.md")

    except Exception as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def main():
    """Main function."""
    print("Exporting acronyms from database to ACRONYM_INDEX.md...")
    export_acronyms_to_markdown()
    print("Export completed successfully!")


if __name__ == "__main__":
    main()