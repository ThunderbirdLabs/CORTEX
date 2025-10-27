.PHONY: setup install dev ingest clean help

# Default target
help:
	@echo "Cortex Development Commands"
	@echo "==========================="
	@echo ""
	@echo "Setup (first time):"
	@echo "  make setup      Create Python 3.12 virtual environment"
	@echo "  make install    Install dependencies into venv"
	@echo ""
	@echo "Development:"
	@echo "  make dev        Run FastAPI server (with hot reload)"
	@echo "  make ingest     Run document ingestion script"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean      Remove venv and cache files"
	@echo ""

setup:
	@echo "🔧 Creating virtual environment..."
	@command -v python3.12 >/dev/null 2>&1 || { echo "❌ Python 3.12 not found. Install: brew install python@3.12"; exit 1; }
	python3.12 -m venv .venv-test
	@echo "✅ Virtual environment created at .venv-test"
	@echo ""
	@echo "Next: run 'make install' to install dependencies"

install:
	@echo "📥 Installing dependencies..."
	@test -d .venv-test || { echo "❌ Virtual environment not found. Run 'make setup' first."; exit 1; }
	.venv-test/bin/pip install --upgrade pip --quiet
	.venv-test/bin/pip install -r requirements.txt
	@echo "✅ Dependencies installed"
	@echo ""
	@echo "Ready! Run 'make dev' to start server"

dev:
	@test -d .venv-test || { echo "❌ Virtual environment not found. Run 'make setup && make install' first."; exit 1; }
	@echo "🚀 Starting FastAPI server on http://localhost:8001"
	@echo "   Press Ctrl+C to stop"
	@echo ""
	.venv-test/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --reload

ingest:
	@test -d .venv-test || { echo "❌ Virtual environment not found. Run 'make setup && make install' first."; exit 1; }
	@echo "📥 Running document ingestion..."
	.venv-test/bin/python scripts/production/ingest_from_documents_table.py

clean:
	@echo "🧹 Cleaning up..."
	rm -rf .venv-test
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleaned"
