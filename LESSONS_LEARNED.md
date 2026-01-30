# Lessons Learned: Mokuro OCR Serverless Implementation

## Overview
This document captures key lessons learned during the implementation and debugging of the Mokuro OCR serverless handler on RunPod.

---

## 1. Batch Processing Bug Fix

### Problem
Batch processing was returning 0 pages even though images were being processed successfully.

### Root Cause
Mokuro creates **ONE** `.mokuro` file for the entire volume in the parent directory, not individual `.mokuro.json` files per page.

**Incorrect Implementation:**
```python
# This doesn't work - individual page files don't exist
for i, img_path in enumerate(image_paths):
    mokuro_path = temp_path / f"{img_path.stem}.mokuro.json"
    if mokuro_path.exists():
        # Never reaches here
```

**Correct Implementation:**
```python
# Read the single mokuro file created in parent of temp_dir
mokuro_path = temp_path.parent / f"{temp_path.stem}.mokuro"

if mokuro_path.exists():
    with open(mokuro_path, 'r') as f:
        mokuro_data = json.load(f)

    # Extract all pages from the volume
    pages = mokuro_data.get('pages', [])

    for i, page_data in enumerate(pages):
        blocks = page_data.get('blocks', [])
        results.append({
            "page_index": i,
            "text_blocks": blocks
        })
```

### Key Takeaway
- Mokuro's `process_volume()` generates a single JSON file containing all pages
- File location: `{temp_dir_parent}/{temp_dir_name}.mokuro`
- The file structure is: `{ "pages": [ { "blocks": [...] }, ... ] }`

---

## 2. Local Testing with RunPod SDK

### Discovery
RunPod SDK supports local testing with the `--rp_serve_api` flag.

### Usage
```bash
python handler.py --rp_serve_api --rp_log_level DEBUG
```

### Benefits
- Test serverless code locally before deploying
- Same code runs in both development and production
- No need for separate FastAPI/Uvicorn implementation
- Debugging is much faster with real-time logs

### Cloudflare Tunnel Setup
```bash
# Terminal 1: Start local server
python handler.py --rp_serve_api --rp_log_level DEBUG > server.log 2>&1 &

# Terminal 2: Start Cloudflare tunnel
cloudflared tunnel --url http://localhost:8000 > cloudflare.log 2>&1 &

# Get the public URL from cloudflare.log
grep "trycloudflare" cloudflare.log
```

### Key Takeaway
- Use RunPod SDK's local server mode for development
- Don't create separate codebases for local vs production
- Single codebase = fewer bugs, faster iteration

---

## 3. MokuroGenerator Initialization

### Problem
`MokuroGenerator(device=device)` was throwing an error.

### Root Cause
The `device` parameter is not accepted by `Moku roGenerator()`.

### Solution
```python
# Incorrect
mokuro_gen = MokuroGenerator(device=device)

# Correct
mokuro_gen = MokuroGenerator()
```

### Key Takeaway
- Mokuro automatically detects CPU/CUDA availability
- Don't pass device parameter to MokuroGenerator constructor
- Check CUDA availability with `torch.cuda.is_available()` separately

---

## 4. Volume Title Requirement

### Problem
`AttributeError: 'NoneType' object has no attribute 'name'`

### Root Cause
Volume objects require a Title attribute to be set before processing.

### Solution
```python
volume = Volume(temp_path)
volume.title = Title(temp_path)  # Required!
mokuro_gen.process_volume(volume)
```

### Key Takeaway
- Always set `volume.title` before calling `process_volume()`
- Use `Title(path)` to generate the title from the directory path

---

## 5. File Naming and Path Issues

### Problem
Mokuro files were created but not found in expected locations.

### Root Cause
Mokuro creates the `.mokuro` file in the **parent** of the temp directory, not inside it.

### Solution
```python
with TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)

    # Process volume
    volume = Volume(temp_path)
    mokuro_gen.process_volume(volume)

    # File is in PARENT, not inside temp_dir
    mokuro_path = temp_path.parent / f"{temp_path.stem}.mokuro"
```

### Key Takeaway
- Mokuro writes output to parent of input directory
- Temporary directory name becomes the `.mokuro` filename
- Example: `/tmp/abc123/` → `/tmp/abc123.mokuro`

---

## 6. Debugging Techniques

### Heartbeat Monitoring
Created a script to monitor logs every 10 seconds:

```bash
#!/bin/bash
LOG_FILE="server.log"
last_size=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)

while true; do
    sleep 10
    current_size=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)

    if [ "$current_size" -gt "$last_size" ]; then
        echo "📡 $(date '+%Y-%m-%d %H:%M:%S') - New log entries:"
        tail -n $(( (current_size - last_size) / 80 )) "$LOG_FILE"
        last_size=$current_size
    fi
done
```

### Log Analysis Commands
```bash
# Check recent errors
tail -n 100 server.log | grep -i error

# Find specific request types
tail -n 100 server.log | grep -A 20 "process_batch"

# Monitor job completions
tail -f server.log | grep "Successfully processed"
```

### Key Takeaway
- Set up log monitoring early in development
- Use DEBUG log level for detailed troubleshooting
- Save logs to files for post-mortem analysis

---

## 7. Base Docker Image Issues

### Problem
Base image `runpod/base:0.0.1-python3.10` doesn't exist on Docker Hub.

### Solution
Use official Python images:
```dockerfile
FROM python:3.10-slim
```

### Key Takeaway
- Verify base images exist before using them
- Official images are more reliable than vendor-specific ones
- Check Docker Hub: https://hub.docker.com/_/python

---

## 8. Performance Expectations

### Development (Local CPU)
- Health check: ~1-2 seconds
- Single page: 10-20 seconds (first run: +30s for model loading)
- Batch processing: ~1.2-1.9 seconds per page
- 28 pages processed in 34 seconds

### Production (RunPod GPU)
- Health check: ~50-100ms
- Single page: ~1-2 seconds
- Batch processing: ~1-3 seconds per page
- Model loading: ~5-10 seconds on cold start

### Key Takeaway
- CPU processing is usable for testing (1-2s per page)
- GPU processing is 10-20x faster
- Model loading adds overhead on first request
- Batch processing is more efficient than individual requests

---

## 9. API Design Best Practices

### Request Format
```json
{
  "input": {
    "type": "process_batch",
    "title": "Manga Chapter 1",
    "images": ["BASE64_1", "BASE64_2"]
  }
}
```

### Response Format
```json
{
  "status": "success",
  "title": "Manga Chapter 1",
  "pages": [
    {
      "page_index": 0,
      "text_blocks": [...]
    },
    {
      "page_index": 1,
      "text_blocks": [...]
    }
  ]
}
```

### Key Takeaway
- Use nested `input` object for RunPod serverless
- Include page_index for array responses
- Return status messages for debugging
- Keep consistent structure across endpoints

---

## 10. Common Pitfalls

### ❌ Don't
1. Create separate FastAPI and serverless handlers
2. Look for individual page JSON files from Mokuro
3. Pass device parameter to MokuroGenerator
4. Forget to set volume.title
5. Look for .mokuro file inside temp directory
6. Use non-existent base Docker images
7. Push code without local testing

### ✅ Do
1. Use single codebase for local and production
2. Read the single .mokuro file from parent directory
3. Let Mokuro auto-detect device
4. Always set volume.title before processing
5. Look for .mokuro file in parent of temp_dir
6. Use official Python base images
7. Test locally with RunPod SDK before deploying

---

## Summary

The most critical lesson is that **Mokuro creates a single volume-level JSON file**, not per-page files. Understanding this file structure is essential for correctly extracting OCR results from batch processing operations.

Additionally, using the RunPod SDK's local testing capability (`--rp_serve_api`) enables rapid development and debugging without constantly pushing to production.

---

**Last Updated:** 2026-01-29
**Project:** Mokuro OCR Serverless Handler
**Platform:** RunPod Serverless GPU

---

## 11. Cold Start Optimization (Added 2026-01-30)

### Problem
First request on cold start was hanging/stuck while downloading models:
- `comictextdetector.pt` (~85MB) from GitHub releases
- Manga OCR model (~200MB) from Hugging Face
- Download timeout causing requests to fail

### Root Cause
RunPod serverless containers don't persist model downloads between cold starts. Each new container needs to download all models from scratch, which can take 2-5 minutes.

### Solution: Pre-cache Models in Docker Image

**1. Create Model Download Script (`download_models.py`):**
```python
#!/usr/bin/env python3
import os
from pathlib import Path

cache_dir = Path("/workspace/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(cache_dir)

from mokuro import MokuroGenerator
mokuro_gen = MokuroGenerator()
```

**2. Update Dockerfile:**
```dockerfile
# Copy and run model download script during build
COPY download_models.py .
RUN python download_models.py && rm download_models.py
```

**3. Create Startup Script (`start.sh`):**
```bash
#!/bin/bash
export HF_HOME=/workspace/cache
mkdir -p /workspace/cache

# Check if models exist, download if missing
if [ ! -d "/workspace/cache/hub" ]; then
    python -c "from mokuro import MokuroGenerator; MokuroGenerator()"
fi

exec python handler.py
```

**4. Update Dockerfile CMD:**
```dockerfile
COPY start.sh .
RUN chmod +x start.sh
CMD ["./start.sh"]
```

### Benefits
- ✅ Cold start time: 2-5 minutes → 5-10 seconds
- ✅ Models cached in Docker image (~300MB)
- ✅ No download delays during requests
- ✅ Graceful fallback if models missing

### Performance Impact

**Before (with model downloads):**
- Cold start: 120-300 seconds
- First request: Often times out
- Subsequent requests: 1-2 seconds (if container persists)

**After (with pre-cached models):**
- Cold start: 5-10 seconds (container spin-up only)
- First request: 1-2 seconds
- All requests: Consistent 1-2 second performance

### Key Takeaway
Always pre-cache heavy model files in the Docker image for serverless deployments. The ~300MB increase in image size is worth eliminating 2-5 minute cold start delays.

### Docker Build Size
- Base image: ~150MB
- With dependencies: ~800MB
- With cached models: ~1.1GB
- Trade-off: Acceptable for 10x faster cold starts

---

---

## 12. True Cold Start Optimization - Persist Text Detector (Added 2026-01-30)

### Problem: "Models Loaded" Message Was Misleading
The logs showed:
```
✅ Using pre-cached models from /workspace/cache
✅ Models loaded
```

But then immediately:
```
Initializing text detector
Downloading comictextdetector.pt (took ~1.06s)
Loading OCR model from kha-white/manga-ocr-base
```

**Root Cause:** 
- HF models were cached ✅
- Text detector (`comictextdetector.pt`) was NOT cached ❌
- "Models loaded" meant "handler initialized", not "weights ready"
- Weight materialization (264 tensors) still happened on first request

### Solution: Bake Everything Into Docker Image

**1. Explicitly Download Text Detector During Build:**
```python
# In download_models.py
detector_url = "https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.2.1/comictextdetector.pt"
detector_path = cache_dir / "comictextdetector.pt"
urllib.request.urlretrieve(detector_url, detector_path)
```

**2. Preload Models at Worker Startup:**
```python
# In handler.py - at module level, not in handler function
load_models()  # Preload before any requests

def load_models():
    if detector_cached and hf_cached:
        os.environ["HF_HUB_OFFLINE"] = "1"  # Force offline mode
    mokuro_gen = MokuroGenerator()
```

**3. Set HF_TOKEN (Optional but Recommended):**
```dockerfile
# In Dockerfile or RunPod template
# ENV HF_TOKEN=your_token_here
```
- Set as secret env var in RunPod template
- Prevents unauthenticated warnings
- Reduces rate limiting

### Performance Impact

**Before (partial cache):**
- Text detector download: ~1.06s
- HF metadata requests: 50-100 HEAD/GET calls
- Weight materialization: 5-10s on first request
- Total first request: 10-15s

**After (full cache + preload):**
- Text detector: cached in image ✅
- HF models: cached in image ✅
- Preload at startup: 5-10s (worker boot)
- First request: ~1-2s (weights ready!)
- Subsequent requests: ~1-2s

### Key Takeaways

1. **"Models loaded" != "weights in VRAM"**
   - MokuroGenerator() init is fast
   - Weight materialization takes time
   - Preload at worker boot, not first request

2. **Cache EVERYTHING:**
   - HF models: `/workspace/cache/hub/`
   - Text detector: `/workspace/cache/comictextdetector.pt`
   - Both must be in Docker image

3. **Force offline mode when cache exists:**
   ```python
   os.environ["HF_HUB_OFFLINE"] = "1"
   os.environ["TRANSFORMERS_OFFLINE"] = "1"
   ```
   - Prevents HF probing requests
   - Ensures local-only operation

4. **HF_TOKEN is worth it:**
   - Eliminates unauthenticated warnings
   - Faster metadata fetches
   - No rate limiting

5. **Keep 1 Worker Hot (Optional):**
   - Set minimum instances = 1 in RunPod
   - Completely eliminates cold starts
   - Higher cost but instant response

### Validation Checklist

Good state shows:
- ✅ No "Downloading comictextdetector.pt"
- ✅ No "Initializing text detector"
- ✅ No "Loading OCR model from kha-white/manga-ocr-base"
- ✅ No "Warning: unauthenticated requests..."
- ✅ No HF request storm on new worker
- ✅ "Models loaded and ready" appears BEFORE first request
- ✅ First request processes immediately in 1-2s

### Docker Image Size Impact

- Base image: ~150MB
- With Python deps: ~800MB
- With HF models: ~1.0GB
- With text detector: ~1.1GB
- **Total: ~1.1GB** (acceptable for 10x faster cold starts)

---
