#!/usr/bin/env bash
# ============================================================
# Đông Đô CS Chatbot - Render Build Script
# Tối ưu hóa bộ nhớ cho Render Free Tier (CPU-only PyTorch)
# ============================================================
set -e

echo "📦 1. Upgrading pip..."
pip install --upgrade pip

echo "⚡ 2. Installing Lightweight CPU-only PyTorch (saves ~3.5GB memory)..."
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

echo "📦 3. Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "📄 4. Ingesting documents into ChromaDB vector store..."
python ingest.py

echo "✅ Build complete successfully!"
