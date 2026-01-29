#!/bin/bash

# RunPod Deployment Script for Mokuro OCR Server

set -e

echo "🚀 Mokuro OCR Server - RunPod Deployment"
echo "======================================"

# Configuration
IMAGE_NAME="mokuro-server:latest"
CONTAINER_PORT=8000
GPU_TYPE="NVIDIA RTX 4090"
STORAGE_SIZE=20

echo ""
echo "📋 Step 1: Check prerequisites..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi
echo "✅ Docker found"

echo ""
echo "📦 Step 2: Build Docker image..."
cd "$(dirname "$0")"

# Use requirements-cuda.txt for RunPod
if [ -f "requirements-cuda.txt" ]; then
    cp requirements-cuda.txt requirements.txt
    echo "✅ Using CUDA-optimized requirements"
fi

docker build -t $IMAGE_NAME .
echo "✅ Docker image built successfully"

echo ""
echo "🧪 Step 3: Test locally (optional)..."
read -p "Test locally first? (y/n): " test_local
if [ "$test_local" = "y" ]; then
    echo "Starting server locally..."
    docker run -p $CONTAINER_PORT:$CONTAINER_PORT $IMAGE_NAME &
    LOCAL_PID=$!
    echo "Server started at http://localhost:$CONTAINER_PORT"
    echo "Press Ctrl+C to stop..."
    wait $LOCAL_PID
fi

echo ""
echo "☁️ Step 4: Deploy to RunPod..."
echo ""
echo "OPTIONS:"
echo "  a) Web UI: Go to https://www.runpod.io/console"
echo "  b) CLI: Run the following command:"
echo ""
echo "    runpodctl create pod \\"
echo "      --name mokuro-server \\"
echo "      --image $IMAGE_NAME \\"
echo "      --gpu-type \"$GPU_TYPE\" \\"
echo "      --container-port $CONTAINER_PORT \\"
echo "      --volume-size $STORAGE_SIZE \\"
echo "      --flashboot"
echo ""
echo "After deployment, you'll get a public URL like:"
echo "  https://xxx-8000.direct.runpod.io"
echo ""

read -p "Open RunPod console in browser? (y/n): " open_browser
if [ "$open_browser" = "y" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "https://www.runpod.io/console"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open "https://www.runpod.io/console"
    else
        start "https://www.runpod.io/console"
    fi
fi

echo ""
echo "✅ Setup complete! Follow the deployment guide for detailed instructions."
echo "📖 See RUNPOD_DEPLOYMENT.md for full documentation."
