#!/usr/bin/env python3
"""
RNI Model Training Script

Extracts knowledge from PGVector database and fine-tunes Mistral 7B
on RNI technical documentation for improved domain expertise.
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings
from utils.logging_config import configure_root_logging

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class TrainingExample:
    """Single training example for fine-tuning."""

    instruction: str
    input_text: str
    output: str
    source_document: str
    chunk_index: int


@dataclass
class TrainingDataset:
    """Complete training dataset."""

    examples: List[TrainingExample]
    metadata: Dict[str, Any]


class RNIModelTrainer:
    """Trainer for RNI-specific language models."""

    def __init__(self):
        from config import get_settings

        settings = get_settings()
        # Force localhost for local development
        db_host = "localhost"
        logger.info(f"Using DB_HOST: {db_host}")
        self.db_config = {
            "host": db_host,
            "database": settings.db_name,
            "user": settings.db_user,
            "password": settings.db_password or "postgres",  # Default password for local dev
            "port": settings.db_port,
        }

    def extract_training_data(self) -> TrainingDataset:
        """Extract all document chunks from PGVector for training."""
        logger.info("Extracting training data from PGVector...")

        conn = psycopg2.connect(
            host=self.db_config["host"],
            database=self.db_config["database"],
            user=self.db_config["user"],
            password=self.db_config["password"],
            port=self.db_config["port"],
            cursor_factory=RealDictCursor,
        )
        cursor = conn.cursor()

        try:
            # Get all document chunks with metadata
            cursor.execute(
                """
                SELECT
                    dc.id,
                    dc.document_id,
                    dc.chunk_index,
                    dc.content,
                    dc.page_number,
                    dc.section_title,
                    dc.chunk_type,
                    d.file_name,
                    d.title,
                    d.document_type,
                    d.product_name,
                    d.product_version,
                    d.privacy_level,
                    d.classification_confidence
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE LENGTH(dc.content) > 200  -- Filter out very short chunks
                ORDER BY d.id, dc.chunk_index
                LIMIT 10000  -- Limit for initial testing
            """
            )

            rows = cursor.fetchall()
            logger.info(f"Extracted {len(rows)} document chunks for training")

            # Convert to training examples
            examples = []
            for row in tqdm(rows, desc="Processing chunks"):
                example = self._create_training_example(row)
                if example:
                    examples.append(example)

            # Create metadata
            metadata = {
                "total_chunks": len(rows),
                "training_examples": len(examples),
                "extraction_date": "2025-11-02",
                "source": "PGVector document_chunks",
                "model_target": "mistral:7b",
                "domain": "RNI Technical Documentation",
            }

            dataset = TrainingDataset(examples=examples, metadata=metadata)
            logger.info(f"Created training dataset with {len(examples)} examples")

            return dataset

        finally:
            cursor.close()
            conn.close()

    def _create_training_example(self, row: Dict) -> Optional[TrainingExample]:
        """Convert a database row into a training example."""
        content = row["content"].strip()

        # Skip if content is too short or generic
        if len(content) < 200:
            return None

        # Create instruction based on document type and content
        doc_type = row.get("document_type", "document")
        product = row.get("product_name", "system")
        title = row.get("title", row.get("file_name", "Unknown"))

        # Generate appropriate instruction
        if doc_type == "user_guide":
            instruction = f"You are a technical support specialist for {product}. Provide clear, step-by-step guidance based on the following documentation."
        elif doc_type == "technical_specification":
            instruction = f"You are an expert engineer working with {product}. Explain the technical specifications and requirements clearly."
        elif doc_type == "release_notes":
            instruction = (
                f"You are a product manager for {product}. Explain the changes and improvements in this release."
            )
        elif doc_type == "troubleshooting":
            instruction = f"You are a support engineer for {product}. Help diagnose and resolve technical issues."
        else:
            instruction = (
                f"You are a technical expert for {product}. Provide accurate information based on the documentation."
            )

        # Create input (the question/context)
        section_title = row.get("section_title", "")
        page = row.get("page_number", 0)

        input_text = f"Document: {title}"
        if section_title:
            input_text += f"\nSection: {section_title}"
        if page:
            input_text += f"\nPage: {page}"
        input_text += f"\n\nContent: {content[:1000]}..."  # Truncate for input

        # For now, use the content as both input and expected output
        # In a real scenario, you'd want to create Q&A pairs
        output = content

        return TrainingExample(
            instruction=instruction,
            input_text=input_text,
            output=output,
            source_document=row["file_name"],
            chunk_index=row["chunk_index"],
        )

    def save_training_data(self, dataset: TrainingDataset, output_path: str):
        """Save training dataset to JSONL format for fine-tuning."""
        logger.info(f"Saving training data to {output_path}")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            # Save metadata
            metadata_file = output_path.replace(".jsonl", "_metadata.json")
            with open(metadata_file, "w", encoding="utf-8") as mf:
                json.dump(dataset.metadata, mf, indent=2, ensure_ascii=False)

            # Save training examples in JSONL format
            for example in tqdm(dataset.examples, desc="Saving examples"):
                # Format for Mistral fine-tuning (instruction-response format)
                formatted_example = {
                    "instruction": example.instruction,
                    "input": example.input_text,
                    "output": example.output,
                }
                f.write(json.dumps(formatted_example, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(dataset.examples)} training examples")

    def create_instruction_tuning_data(self, dataset: TrainingDataset) -> TrainingDataset:
        """Create instruction tuning examples from the raw data."""
        logger.info("Creating instruction-response pairs...")

        instruction_examples = []

        # Group chunks by document for context
        doc_chunks = {}
        for example in dataset.examples:
            doc = example.source_document
            if doc not in doc_chunks:
                doc_chunks[doc] = []
            doc_chunks[doc].append(example)

        # Create Q&A pairs from related chunks
        for doc, chunks in doc_chunks.items():
            if len(chunks) < 2:
                continue

            # Sort by chunk index
            chunks.sort(key=lambda x: x.chunk_index)

            for i, chunk in enumerate(chunks):
                # Create questions based on content
                questions = self._generate_questions_from_content(chunk.output)

                for question in questions:
                    # Find relevant context from nearby chunks
                    context_chunks = chunks[max(0, i - 1) : min(len(chunks), i + 2)]
                    context = "\n\n".join([c.output for c in context_chunks])

                    instruction_examples.append(
                        TrainingExample(
                            instruction="You are a technical expert. Answer the following question based on the provided documentation.",
                            input_text=f"Question: {question}\n\nDocumentation:\n{context[:2000]}",
                            output=chunk.output,
                            source_document=doc,
                            chunk_index=chunk.chunk_index,
                        )
                    )

        new_dataset = TrainingDataset(
            examples=instruction_examples,
            metadata={
                **dataset.metadata,
                "tuning_type": "instruction_tuning",
                "instruction_examples": len(instruction_examples),
            },
        )

        logger.info(f"Created {len(instruction_examples)} instruction tuning examples")
        return new_dataset

    def _generate_questions_from_content(self, content: str) -> List[str]:
        """Generate relevant questions from content."""
        questions = []

        # Simple heuristic-based question generation
        sentences = content.split(".")[:3]  # First few sentences

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 50:
                continue

            # Generate different types of questions
            if "how to" in sentence.lower() or "steps" in sentence.lower():
                questions.append(f"How do I {sentence.lower().replace('to ', '')}?")
            elif "configuration" in sentence.lower():
                questions.append("How do I configure this system?")
            elif "troubleshoot" in sentence.lower():
                questions.append("How do I troubleshoot this issue?")
            elif "install" in sentence.lower():
                questions.append("How do I install this software?")
            else:
                # Generic question
                questions.append(f"What is the process for {sentence[:50].lower()}?")

        return questions[:2]  # Limit to 2 questions per chunk


def main():
    """Main training pipeline."""
    configure_root_logging()

    trainer = RNIModelTrainer()

    # Step 1: Extract data
    logger.info("Step 1: Extracting training data from PGVector")
    dataset = trainer.extract_training_data()

    # Step 2: Create instruction tuning data
    logger.info("Step 2: Creating instruction-response pairs")
    tuned_dataset = trainer.create_instruction_tuning_data(dataset)

    # Step 3: Save training data
    output_dir = "training_data"
    raw_data_path = f"{output_dir}/rni_training_raw.jsonl"
    tuned_data_path = f"{output_dir}/rni_training_tuned.jsonl"

    logger.info("Step 3: Saving training datasets")
    trainer.save_training_data(dataset, raw_data_path)
    trainer.save_training_data(tuned_dataset, tuned_data_path)

    logger.info("Training data preparation complete!")
    logger.info(f"Raw dataset: {len(dataset.examples)} examples")
    logger.info(f"Tuned dataset: {len(tuned_dataset.examples)} examples")
    logger.info(f"Files saved to: {output_dir}/")


if __name__ == "__main__":
    main()
