import json
import sys

from pdf_processor.utils import extract_tables

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_tables.py <pdf_path>")
        sys.exit(1)
    pdf_file_path = sys.argv[1]
    extracted_tables = extract_tables(pdf_file_path)
    print(json.dumps(extracted_tables))
