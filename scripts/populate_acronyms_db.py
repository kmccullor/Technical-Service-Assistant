#!/usr/bin/env python3
"""
Populate the acronyms database table with curated technical acronyms.

This script inserts a comprehensive list of technical acronyms and their definitions
into the database for use by the RAG system.
"""

import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_settings
import psycopg2


def get_curated_acronyms():
    """Return a curated dictionary of technical acronyms and definitions."""
    return {
        # AI/ML acronyms
        "AI": "Artificial Intelligence",
        "ML": "Machine Learning",
        "NLP": "Natural Language Processing",
        "LLM": "Large Language Model",
        "RAG": "Retrieval-Augmented Generation",
        "BERT": "Bidirectional Encoder Representations from Transformers",
        "GPT": "Generative Pre-trained Transformer",
        "CNN": "Convolutional Neural Network",
        "RNN": "Recurrent Neural Network",
        "LSTM": "Long Short-Term Memory",
        "GAN": "Generative Adversarial Network",
        "RL": "Reinforcement Learning",
        "DL": "Deep Learning",

        # Software Development
        "API": "Application Programming Interface",
        "REST": "Representational State Transfer",
        "JSON": "JavaScript Object Notation",
        "XML": "Extensible Markup Language",
        "SQL": "Structured Query Language",
        "NoSQL": "Not Only SQL",
        "ORM": "Object-Relational Mapping",
        "MVC": "Model-View-Controller",
        "CRUD": "Create, Read, Update, Delete",
        "CI": "Continuous Integration",
        "CD": "Continuous Deployment",
        "DevOps": "Development Operations",
        "TDD": "Test-Driven Development",
        "BDD": "Behavior-Driven Development",

        # Web Technologies
        "HTTP": "Hypertext Transfer Protocol",
        "HTTPS": "Hypertext Transfer Protocol Secure",
        "HTML": "Hypertext Markup Language",
        "CSS": "Cascading Style Sheets",
        "JS": "JavaScript",
        "DOM": "Document Object Model",
        "AJAX": "Asynchronous JavaScript and XML",
        "SPA": "Single Page Application",
        "PWA": "Progressive Web Application",

        # Databases
        "DB": "Database",
        "RDBMS": "Relational Database Management System",
        "ACID": "Atomicity, Consistency, Isolation, Durability",
        "CAP": "Consistency, Availability, Partition Tolerance",
        "BASE": "Basically Available, Soft State, Eventually Consistent",
        "OLTP": "Online Transaction Processing",
        "OLAP": "Online Analytical Processing",
        "ETL": "Extract, Transform, Load",

        # Cloud Computing
        "IaaS": "Infrastructure as a Service",
        "PaaS": "Platform as a Service",
        "SaaS": "Software as a Service",
        "AWS": "Amazon Web Services",
        "GCP": "Google Cloud Platform",
        "Azure": "Microsoft Azure",
        "Docker": "Container Platform",
        "Kubernetes": "Container Orchestration System",

        # Networking
        "TCP": "Transmission Control Protocol",
        "UDP": "User Datagram Protocol",
        "IP": "Internet Protocol",
        "DNS": "Domain Name System",
        "VPN": "Virtual Private Network",
        "LAN": "Local Area Network",
        "WAN": "Wide Area Network",
        "NAT": "Network Address Translation",
        "DHCP": "Dynamic Host Configuration Protocol",

        # Security
        "SSL": "Secure Sockets Layer",
        "TLS": "Transport Layer Security",
        "OAuth": "Open Authorization",
        "JWT": "JSON Web Token",
        "RBAC": "Role-Based Access Control",
        "ACL": "Access Control List",
        "PKI": "Public Key Infrastructure",
        "AES": "Advanced Encryption Standard",

        # Data Formats
        "CSV": "Comma-Separated Values",
        "YAML": "YAML Ain't Markup Language",
        "TOML": "Tom's Obvious Minimal Language",
        "PDF": "Portable Document Format",
        "OCR": "Optical Character Recognition",

        # Technical Service Assistant specific
        "RNI": "Radio Network Interface",
        "AMI": "Advanced Metering Infrastructure",
        "ESM": "Energy Services Module",
        "MDM": "Meter Data Management",
        "HAN": "Home Area Network",
        "AMI": "Advanced Metering Infrastructure",
        "DA": "Distribution Automation",
        "DER": "Distributed Energy Resources",
        "DR": "Demand Response",
        "EMS": "Energy Management System",
        "FDIR": "Fault Detection, Isolation and Restoration",
        "GIS": "Geographic Information System",
        "HMI": "Human-Machine Interface",
        "IEC": "International Electrotechnical Commission",
        "IoT": "Internet of Things",
        "PLC": "Programmable Logic Controller",
        "SCADA": "Supervisory Control and Data Acquisition",
        "SOE": "Sequence of Events",
        "TMR": "Trip Matrix Recorder",
        "VVO": "Volt-VAR Optimization",
    }


def populate_acronyms_database():
    """Populate the acronyms table with curated technical acronyms."""
    settings = get_settings()
    acronyms = get_curated_acronyms()

    conn = None
    cursor = None
    try:
        print(f"Connecting to database: {settings.db_host}:{settings.db_port}/{settings.db_name}")
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password
        )
        cursor = conn.cursor()

        # Check if acronyms table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'acronyms'
            )
        """)
        result = cursor.fetchone()
        table_exists = result[0] if result else False

        if not table_exists:
            print("Acronyms table does not exist. Please run the migration first:")
            print("psql -h pgvector -U postgres -d vector_db -f migrations/20251030_add_acronym_synonym_tables.sql")
            return

        # Get existing acronyms to avoid duplicates
        cursor.execute("SELECT acronym FROM acronyms")
        existing_acronyms = {row[0] for row in cursor.fetchall()}

        inserted_count = 0
        skipped_count = 0

        for acronym, definition in acronyms.items():
            if acronym in existing_acronyms:
                skipped_count += 1
                continue

            # Insert new acronym
            cursor.execute("""
                INSERT INTO acronyms (acronym, definition, confidence_score, source_documents, is_verified)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                acronym,
                definition,
                0.9,  # High confidence for curated acronyms
                ['curated_technical_terms'],  # Source document
                True   # Mark as verified
            ))
            inserted_count += 1

        conn.commit()
        print(f"Database update complete:")
        print(f"  - {inserted_count} acronyms inserted")
        print(f"  - {skipped_count} acronyms already existed")
        print(f"  - Total acronyms in database: {len(existing_acronyms) + inserted_count}")

    except Exception as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return True


def main():
    """Main function to populate acronyms database."""
    print("Starting acronym database population...")
    print(f"Loading {len(get_curated_acronyms())} curated technical acronyms...")

    success = populate_acronyms_database()

    if success:
        print("Acronym database population completed successfully!")
    else:
        print("Acronym database population failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()