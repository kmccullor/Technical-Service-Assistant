import json
import sys

from pdf_processor.utils import extract_text

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_text.py <pdf_path>")
        sys.exit(1)
    pdf_file_path = sys.argv[1]
    extracted_text = extract_text(pdf_file_path)
    print(json.dumps({"text": extracted_text}))
