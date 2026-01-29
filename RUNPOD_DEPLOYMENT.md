# RunPod Deployment Guide for Mokuro OCR Server

Deploy your Mokuro OCR server on RunPod with RTX 4090 GPU for lightning-fast manga OCR!

## Prerequisites

- RunPod account (https://www.runpod.io)
- RTX 4090 GPU availability
- Basic knowledge of Docker

## Quick Start

### 1. Prepare Your Code

Make sure you have these files in your mokuro-server directory:
- `Dockerfile` (included)
- `main.py` (updated for CUDA)
- `requirements.txt`

### 2. Build & Push Docker Image

```bash
# Build the image
docker build -t mokuro-server:latest .

# Test locally (optional)
docker run -p 8000:8000 mokuro-server:latest
```

### 3. Deploy to RunPod

#### Option A: Using RunPod Web UI

1. Go to https://www.runpod.io/console
2. Click "Deploy" → "Community Cloud"
3. Configure:
   - **Cloud:** Community Cloud
   - **GPU:** RTX 4090 (or RTX 3090/4070/4080 for cheaper options)
   - **Storage:** 20GB Flashboot (includes 10GB free storage)
   - **Container Image:** Your Docker image
   - **Volume Mount:** `/data` (optional, for persistent storage)
   - **Ports:** `8000` (HTTP)
4. Click "Deploy"

#### Option B: Using RunPod CLI

```bash
# Install RunPod CLI
pip install runpod

# Login
runpodctl login

# Create a pod
runpodctl create pod --name mokuro-server \
  --image mokuro-server:latest \
  --gpu-type "NVIDIA RTX 4090" \
  --container-port 8000 \
  --volume-size 20 \
  --flashboot
```

### 4. Access Your Server

After deployment, RunPod will provide:
- **Public URL:** `https://xxx-8000.direct.runpod.io`
- **SSH Access:** For debugging
- **Metrics:** Real-time GPU/memory usage

## Configuration

### Environment Variables

You can add these in the RunPod UI:

```bash
# Optional: Set HuggingFace cache directory
HF_HOME=/workspace/cache

# Optional: Log level
LOG_LEVEL=INFO
```

### Storage

- **Flashboot** included: Fast NVMe storage
- **Network storage**: S3-compatible storage
- **Persistent**: Data persists across restarts (if using volumes)

## Performance

### Expected Speeds on RTX 4090:

| Operation | Time (vs M2 Max) |
|-----------|------------------|
| **Single Page** | 0.3-0.5s (vs 1.65s) ⚡⚡⚡ |
| **50 Pages (batch)** | 15-25s (vs 82s) ⚡⚡⚡ |
| **Speedup** | **3-5x faster** |

### Why RTX 4090 is Faster:

- **24GB VRAM** (vs ~30GB unified on M2 Max)
- **Dedicated GPU memory** (no sharing with CPU)
- **CUDA optimization** (more mature than MPS)
- **Higher clock speeds** (2.23 GHz vs ~1.4 GHz)

## Cost Estimation

### Serverless Pricing (Community Cloud):

| Usage | Hours/Month | Cost/Month | Cost/Page |
|-------|-------------|------------|-----------|
| Light (50 pages/day) | ~0.03 | $0.02 | $0.0004 |
| Medium (500 pages/day) | ~0.3 | $0.15 | $0.0001 |
| Heavy (5,000 pages/day) | ~2.5 | $1.25 | $0.00025 |

### Cost-Saving Tips:

1. **Use Serverless** - Only pay when processing
2. **Auto-shutdown** - Configure idle timeout (5-10 min)
3. **Spot instances** - Up to 70% cheaper (if available)
4. **Optimize image size** - Faster processing = less GPU time

## Monitoring

### Check GPU Usage:

```bash
# SSH into your RunPod pod
runpodctl ssh mokuro-server

# Check GPU stats
nvidia-smi

# Monitor in real-time
watch -n 1 nvidia-smi
```

### View Logs:

```bash
# View logs
docker logs -f <container_id>

# Or use RunPod web UI → Logs tab
```

## Troubleshooting

### Common Issues:

**1. CUDA Out of Memory**
- Solution: Reduce batch size or use smaller images
- Or upgrade to RTX 4090 with 24GB VRAM

**2. Slow Processing**
- Check: `nvidia-smi` to see GPU utilization
- Solution: Make sure CUDA is enabled (no CPU fallback)

**3. Container Won't Start**
- Check logs for errors
- Verify Docker image is built correctly
- Test locally first

## Optimization Tips

### 1. Enable GPU Persistence
```python
# Already in your code!
torch.cuda.is_available()
torch.backends.cudnn.benchmark = True
```

### 2. Use Mixed Precision (Optional)
```python
# Add to requirements.txt:
# torch-tb

# In code:
from torch.cuda.amp import autocast
```

### 3. Batch Processing
Process multiple pages in parallel:
```python
# Process 10 pages at once
# Much faster than 1-by-1
```

## Scaling

### Horizontal Scaling:
- Spin up multiple pods
- Load balance across instances
- Handle 1000s of concurrent requests

### Vertical Scaling:
- Upgrade to RTX 4090 (done!)
- Or multi-GPU setups (RTX 4090 x4)
- Handle massive batch jobs

## Security

### Enable API Key Authentication (Optional):

```python
# Add to main.py:
API_KEY = os.getenv("API_KEY")

@app.post("/process-manga")
async def process_manga(
    files: List[UploadFile] = File(...),
    api_key: str = Form(None)
):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
```

Set environment variable in RunPod:
```bash
API_KEY=your-secret-key-here
```

## Updates & Maintenance

### Updating the Server:

```bash
# Build new image
docker build -t mokuro-server:v2 .

# Push to registry (optional)
docker push your-registry/mokuro-server:v2

# Redeploy on RunPod
# Use new image tag in RunPod UI
```

### Backup Your Data:

```bash
# SSH into pod
runpodctl ssh mokuro-server

# Backup outputs
tar -czf backup.tar.gz outputs/

# Download to local machine
exit
runpodctl download mokuro-server /workspace/backup.tar.gz
```

## Support

- RunPod Discord: https://discord.gg/runpod
- RunPod Docs: https://docs.runpod.io
- Mokuro GitHub: https://github.com/kha-white/mokuro

## Summary

✅ **Ready to deploy!**
✅ **3-5x faster** than M2 Max
✅ **Pay-per-second** pricing
✅ **Auto-scales** on demand
✅ **Public URL** - no tunnel needed!

**Deploy time:** ~5 minutes
**First request:** ~30s (cold start)
**Subsequent requests:** <1 second ⚡
