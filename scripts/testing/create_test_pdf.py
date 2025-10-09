#!/usr/bin/env python3
"""Create a simple test PDF for testing the Technical Service Assistant."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_test_pdf():
    filename = "uploads/test_document.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Add some test content
    c.drawString(100, height - 100, "Test Document for Technical Service Assistant")
    c.drawString(100, height - 130, "")
    c.drawString(100, height - 160, "This is a test document created to verify the PDF ingestion pipeline.")
    c.drawString(100, height - 190, "It contains multiple sentences for testing chunking strategies.")
    c.drawString(100, height - 220, "")
    c.drawString(100, height - 250, "The document should be automatically processed by the pdf_processor worker.")
    c.drawString(100, height - 280, "Text extraction, chunking, and embedding generation should all work correctly.")
    c.drawString(100, height - 310, "")
    c.drawString(100, height - 340, "This content will be stored in the PGVector database for semantic search.")
    c.drawString(100, height - 370, "The reranker service can then improve search quality using BGE models.")

    c.save()
    print(f"Created test PDF: {filename}")


if __name__ == "__main__":
    create_test_pdf()
