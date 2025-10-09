import json
import sys

from utils import extract_images

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_images.py <pdf_file_path> <output_directory>")
        sys.exit(1)
    pdf_file_path = sys.argv[1]
    output_directory = sys.argv[2]
    extracted_images = extract_images(pdf_file_path, output_directory)
    print(json.dumps(extracted_images))
