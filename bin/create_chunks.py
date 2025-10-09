import json
import os
import sys

# Use the canonical chunk_text implementation from pdf_processor.utils to avoid
# duplicating tokenization and metadata logic across the repo.
from pdf_processor.utils import chunk_text as chunk_text_impl


def chunk_text(text, document_name):
    # Delegate to the pdf_processor implementation which returns (chunks, next_index)
    chunks, _ = chunk_text_impl(text, document_name)
    return chunks


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_chunks.py <text_file_path>")
        sys.exit(1)

    text_file_path = sys.argv[1]
    document_name = os.path.basename(text_file_path)

    with open(text_file_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    chunked_data = chunk_text(full_text, document_name)

    print(json.dumps(chunked_data, indent=2))
