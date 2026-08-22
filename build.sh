#!/usr/bin/env bash
# ============================================================
# Đông Đô CS Chatbot - Render Build Script
# Tối ưu hóa siêu nhẹ bằng FastEmbed ONNX
# ============================================================
set -e

echo "📦 1. Upgrading pip..."
pip install --upgrade pip

echo "📦 2. Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "📄 3. Ingesting documents into ChromaDB vector store..."
python ingest.py

echo "✅ Build completed successfully!"
