#!/usr/bin/env bash
# ============================================================
# Đông Đô CS Chatbot - Render Build Script
# 1. Cài dependencies
# 2. Ingest tài liệu .docx vào ChromaDB
# 3. Học từ chat history (PostgreSQL) nếu có
# ============================================================
set -e

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "📄 Ingesting documents into vector store..."
python ingest.py

echo ""
echo "🧠 Learning from chat history..."
python learn.py

echo ""
echo "✅ Build complete!"
