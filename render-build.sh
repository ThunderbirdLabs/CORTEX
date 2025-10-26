#!/usr/bin/env bash
# Build script for Render deployment
# NOTE: System dependencies (Tesseract, Poppler) are installed via Dockerfile

set -o errexit  # Exit on error

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🔥 Pre-downloading reranker model (prevents first-query timeout)..."
python3 -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base')"
echo "✅ Reranker model cached"

# Create Google Cloud credentials file from environment variable
if [ ! -z "$GOOGLE_CLOUD_CREDENTIALS_JSON" ]; then
  echo "🔑 Creating Google Cloud credentials file..."
  echo "$GOOGLE_CLOUD_CREDENTIALS_JSON" > /tmp/google-cloud-key.json
  export GOOGLE_APPLICATION_CREDENTIALS="/tmp/google-cloud-key.json"
  echo "✅ Google Cloud credentials saved to /tmp/google-cloud-key.json"
fi

echo "✅ Build complete!"

