#!/usr/bin/env bash
# ============================================================
# Đông Đô CS Chatbot - Render Build Script
# 1. Cài đặt thư viện dependencies
# 2. Ingest tài liệu .docx vào Vector Database (ChromaDB)
# ============================================================
set -e

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "📄 Ingesting documents into vector store..."
python ingest.py

echo ""
echo "✅ Build complete successfully!"
