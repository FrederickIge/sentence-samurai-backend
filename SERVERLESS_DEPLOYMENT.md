# RunPod Serverless Deployment

## Quick Start

1. Push code to GitHub
2. Go to RunPod Console → Serverless
3. Click "New Endpoint"
4. Configure:
   - **Name**: mokuro-serverless
   - **Template**: Custom
   - **Container Image**: ghcr.io/runpod/base:python3.10
   - **GitHub**: https://github.com/FrederickIge/sentence-samurai-backend
   - **Handler**: handler.py
5. Select GPU: RTX 4000 Ada (or available)
6. Deploy

## API Usage

### Health Check
```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -d '{
    "input": {
      "type": "health"
    }
  }'
```

### Process Single Page
```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -d '{
    "input": {
      "type": "process_single",
      "image": "base64_encoded_image_here",
      "page_index": 0
    }
  }'
```

### Process Batch
```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_API_KEY' \
  -d '{
    "input": {
      "type": "process_batch",
      "images": ["base64_img1", "base64_img2"],
      "title": "Chapter 1"
    }
  }'
```

## Cost

Serverless pricing:
- RTX 4000 Ada: $0.00019/sec
- Single page: ~$0.01
- Chapter (50 pages): ~$0.50
- Only pay when processing!
