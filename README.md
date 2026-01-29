# Sentence Samurai Backend - Mokuro OCR Server

High-performance manga OCR server powered by Mokuro and optimized for GPU acceleration.

## Features

- ⚡ **Fast OCR** - 1-2 seconds per page with GPU
- 🎯 **Manga Specialized** - Japanese text extraction
- 🚀 **GPU Accelerated** - NVIDIA CUDA / Apple Silicon MPS
- 📦 **Batch Processing** - Process entire chapters
- 📊 **Progress Tracking** - Real-time updates
- 💾 **JSON Response** - Easy integration

## Quick Start

```bash
# Install dependencies
pip install -r requirements-cuda.txt

# Run server
python main.py
```

Server: http://localhost:8000

## Documentation

- [RunPod Deployment](RUNPOD_DEPLOYMENT.md)
- [Deployment Summary](DEPLOYMENT_SUMMARY.md)

## License

MIT
