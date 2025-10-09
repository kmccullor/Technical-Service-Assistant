FROM python:3.9-slim

# Install system dependencies required for camelot (ghostscript, tk/GUI libs, opencv runtime) and fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
	ghostscript \
	python3-tk \
	tk \
	libgl1 \
	libglib2.0-0 \
	libsm6 \
	libxext6 \
	libxrender1 \
	fonts-dejavu \
	tesseract-ocr \
	tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy config.py, utils directory, and pdf_processor directory
COPY config.py /app/config.py
COPY utils/ /app/utils/
COPY pdf_processor/ /app/pdf_processor/

RUN pip install --no-cache-dir -r pdf_processor/requirements.txt

# Download NLTK data
RUN python3 -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

CMD ["python", "pdf_processor/process_pdfs_enhanced.py"]
