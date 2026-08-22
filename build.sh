#!/usr/bin/env bash
# ============================================================
# Đông Đô CS Chatbot - Render Build Script
# Chạy khi deploy: cài dependencies + ingest tài liệu vào vector store
# ============================================================
set -e

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "📄 Ingesting documents into vector store..."
python ingest.py

echo "✅ Build complete!"
