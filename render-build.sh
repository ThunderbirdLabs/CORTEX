#!/usr/bin/env bash
# Build script for Render deployment with Tesseract OCR support

set -o errexit  # Exit on error

echo "📦 Installing system dependencies for OCR..."

# Install Tesseract OCR and Poppler for PDF rendering
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-eng poppler-utils

echo "✅ Tesseract OCR installed: $(tesseract --version | head -n 1)"
echo "✅ Poppler installed: $(pdfinfo -v 2>&1 | head -n 1)"

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build complete!"

