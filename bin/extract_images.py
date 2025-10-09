import json
import os
import sys

from pdf_processor.utils import extract_images

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_images.py <pdf_file_path> <output_directory>")
        sys.exit(1)
    pdf_file_path = sys.argv[1]
    output_directory = sys.argv[2]
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    extracted_images = extract_images(pdf_file_path, output_directory)
    print(json.dumps(extracted_images))
