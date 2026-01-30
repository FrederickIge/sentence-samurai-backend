# RunPod Serverless Handler for Mokuro OCR
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy requirements
COPY requirements-serverless.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements-serverless.txt

# Copy model download script
COPY download_models.py .

# Pre-download and cache models in Docker image
# This eliminates cold start delays from downloading models
RUN python download_models.py && rm download_models.py

# Copy handler
COPY handler.py .

# Copy startup script
COPY start.sh .

# Set environment
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0
ENV HF_HOME=/workspace/cache

# Make scripts executable
RUN chmod +x start.sh handler.py

# RunPod serverless - use startup script
CMD ["./start.sh"]
