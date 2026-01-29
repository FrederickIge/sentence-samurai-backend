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

# Copy handler
COPY handler.py .

# Set environment
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0
ENV HF_HOME=/workspace/cache

# Handler entry point
RUN chmod +x handler.py

# RunPod serverless expects handler.py
CMD ["python", "handler.py"]
