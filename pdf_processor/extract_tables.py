import json
import sys

from utils import extract_tables

if __name__ == "__main__":
    pdf_file_path = sys.argv[1]
    extracted_tables = extract_tables(pdf_file_path)
    print(json.dumps(extracted_tables))
