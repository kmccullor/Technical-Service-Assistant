#!/usr/bin/env python3
import argparse
import json
import os
import sys

import requests

# Add parent directory to path to import from other modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from pdf_processor.extract_text import extract_text

OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_questions_from_text(text, num_questions=10):
    """
    Uses a local LLM to generate questions from the given text.
    """
    prompt = f"""
    Based on the following text, generate {num_questions} relevant and insightful questions.
    The questions should cover a range of topics from the text.
    Return the questions as a numbered list.

    Text:
    ---
    {text}
    ---

    Questions:
    """

    payload = {"model": "gemma:2b", "prompt": prompt, "stream": False}  # Using a general purpose model for generation

    try:
        print("Generating questions using local LLM...")
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()

        generated_text = response.json().get("response")
        questions = [q.strip() for q in generated_text.strip().split("\n") if q.strip()]
        # Filter for lines that start with a number and a period
        questions = [q.split(".", 1)[1].strip() for q in questions if "." in q and q.split(".", 1)[0].isdigit()]

        return questions
    except requests.exceptions.RequestException as e:
        print(f"Error calling Ollama API: {e}")
        if "response" in locals() and response is not None:
            print(f"Response status code: {response.status_code}")
            print(f"Response body: {response.text}")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Generate questions from a PDF document.")
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    parser.add_argument("--num_questions", type=int, default=10, help="Number of questions to generate.")
    args = parser.parse_args()

    pdf_path = args.pdf_path
    document_name = os.path.basename(pdf_path)

    print(f"Generating questions from {document_name}...")

    # 1. Extract text
    full_text = extract_text(pdf_path)
    if not full_text:
        print("No text extracted from the PDF. Exiting.")
        return

    # 2. Generate questions
    questions = generate_questions_from_text(full_text, args.num_questions)

    if questions:
        questions_file = "generated_questions.json"
        with open(questions_file, "w") as f:
            json.dump(questions, f, indent=2)
        print(f"\nSuccessfully generated {len(questions)} questions and saved them to {questions_file}")
        for i, q in enumerate(questions):
            print(f"  {i+1}. {q}")
    else:
        print("Failed to generate questions.")


if __name__ == "__main__":
    main()
