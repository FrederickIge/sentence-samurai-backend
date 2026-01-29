# RunPod Serverless Handler for Mokuro OCR
FROM runpod/base:0.0.1-python3.10

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
