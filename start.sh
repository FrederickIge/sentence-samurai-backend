#!/bin/bash
# RunPod Serverless startup script
# Ensures models are loaded before accepting requests

echo "🚀 Starting Mokuro OCR Serverless Handler"

# Set ALL cache environment variables
export HF_HOME=/workspace/cache
export HF_DATASETS_CACHE=/workspace/cache/datasets
export TRANSFORMERS_CACHE=/workspace/cache/transformers
export HUGGINGFACE_HUB_CACHE=/workspace/cache/hub
export XDG_CACHE_HOME=/workspace/cache
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES=0

# Create cache directory if it doesn't exist
mkdir -p /workspace/cache/{hub,transformers,datasets}

# Verify models are cached
if [ ! -d "/workspace/cache/hub" ]; then
    echo "⚠️  WARNING: Models not found in cache!"
    echo "📥 Downloading models..."
    python -c "from mokuro import MokuroGenerator; MokuroGenerator()"
    echo "✅ Models cached"
else
    echo "✅ Using pre-cached models from /workspace/cache"
fi

echo "✅ Handler module loaded successfully"
echo "📊 Cache directory: /workspace/cache"

# Start the RunPod serverless handler
exec python handler.py
