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
