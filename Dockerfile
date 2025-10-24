# CORTEX Dockerfile with OCR Support
# Installs Tesseract OCR and Poppler for image/PDF processing

FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies for OCR and PDF processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Verify Tesseract and Poppler are installed
RUN tesseract --version && pdfinfo -v

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Render sets $PORT env variable)
EXPOSE 8000

# Default start command (overridden by render.yaml startCommand)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
