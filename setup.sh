#!/usr/bin/env bash
#
# Cortex Development Setup
# Creates Python 3.12 virtual environment and installs dependencies
#
set -e

echo "🔧 Cortex Development Setup"
echo "================================"

# Check Python version
if ! command -v python3.12 &> /dev/null; then
    echo "❌ Python 3.12 not found"
    echo ""
    echo "Install Python 3.12:"
    echo "  macOS:  brew install python@3.12"
    echo "  Linux:  sudo apt install python3.12 python3.12-venv"
    echo ""
    exit 1
fi

echo "✅ Found Python 3.12: $(python3.12 --version)"

# Create venv if doesn't exist
if [ ! -d ".venv-test" ]; then
    echo ""
    echo "📦 Creating virtual environment (.venv-test)..."
    python3.12 -m venv .venv-test
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate and install
echo ""
echo "📥 Installing dependencies..."
source .venv-test/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate venv:     source .venv-test/bin/activate"
echo "  2. Configure .env:    cp .env.example .env (then edit)"
echo "  3. Run server:        uvicorn main:app --host 0.0.0.0 --port 8001 --reload"
echo "  4. Run ingestion:     python scripts/production/ingest_from_documents_table.py"
echo ""
