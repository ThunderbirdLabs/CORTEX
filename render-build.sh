#!/usr/bin/env bash
# Build script for Render deployment with Tesseract OCR support

set -o errexit  # Exit on error

echo "📦 Installing system dependencies for OCR..."

# Check if running on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS (local development) - use Homebrew
    echo "🍎 Detected macOS, checking Homebrew dependencies..."
    if ! command -v tesseract &> /dev/null; then
        echo "Installing Tesseract via Homebrew..."
        brew install tesseract poppler
    else
        echo "✅ Tesseract already installed"
    fi
else
    # Linux (Render deployment) - use apt-get with sudo
    echo "🐧 Detected Linux (Render), installing via apt-get..."

    # Render provides sudo access for apt-get during build
    sudo apt-get update -y
    sudo apt-get install -y tesseract-ocr tesseract-ocr-eng poppler-utils
fi

# Verify installations
echo "✅ Tesseract OCR installed: $(tesseract --version | head -n 1)"
echo "✅ Poppler installed: $(pdfinfo -v 2>&1 | head -n 1)"

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build complete!"

