#!/usr/bin/env bash
# Build script for Render deployment
# NOTE: System dependencies (Tesseract, Poppler) are installed via Dockerfile

set -o errexit  # Exit on error

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Build complete!"

