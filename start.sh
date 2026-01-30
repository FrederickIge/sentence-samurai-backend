#!/bin/bash
# RunPod Serverless startup script
# Ensures models are loaded before accepting requests

echo "🚀 Starting Mokuro OCR Serverless Handler"

# Set cache directory
export HF_HOME=/workspace/cache
export PYTHONUNBUFFERED=1
export CUDA_VISIBLE_DEVICES=0

# Create cache directory if it doesn't exist
mkdir -p /workspace/cache

# Check if models are cached, if not, download them
if [ ! -d "/workspace/cache/hub" ] || [ ! -d "$HOME/.cache/mokuro" ]; then
    echo "📥 Models not cached, downloading..."
    python -c "from mokuro import MokuroGenerator; MokuroGenerator()"
    echo "✅ Models cached"
fi

echo "✅ Handler module loaded successfully"
echo "📊 Cache directory: /workspace/cache"

# Start the RunPod serverless handler
exec python handler.py
