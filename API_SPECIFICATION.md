# Mokuro OCR API Specification

## Base URL

**Development (Local):**
```
https://reliable-webshots-iii-reed.trycloudflare.com
```

**Production (RunPod Serverless):**
```
https://api.runpod.ai/v2/cees37s3ci8vp4/run
```

**Note:** Both endpoints use the same request/response format.

---

## Authentication

**Production only** - Add this header to all requests:
```
Authorization: Bearer YOUR_RUNPOD_API_KEY
```

**Development:** No authentication required.

---

## API Endpoints

### 1. Health Check

Check if the OCR service is running and GPU status.

**Endpoint:** `POST /` or `POST /runsync`

**Request:**
```json
{
  "input": {
    "type": "health"
  }
}
```

**Response:**
```json
{
  "id": "job-id-123",
  "status": "COMPLETED",
  "output": {
    "status": "healthy",
    "gpu": "NVIDIA GeForce RTX 4090",
    "cuda_available": true
  },
  "executionTime": 69
}
```

---

### 2. Process Single Page

Extract text from a single manga page image.

**Endpoint:** `POST /` or `POST /runsync`

**Request:**
```json
{
  "input": {
    "type": "process_single",
    "image": "BASE64_ENCODED_IMAGE_DATA",
    "page_index": 0
  }
}
```

**Fields:**
- `image` (string, required): Base64-encoded image data (no `data:image/...` prefix)
- `page_index` (number, optional): Page number (default: 0)

**Response:**
```json
{
  "id": "job-id-456",
  "status": "COMPLETED",
  "output": {
    "status": "success",
    "result": {
      "page_index": 0,
      "text_blocks": [
        {
          "box": [751, 86, 819, 226],
          "vertical": true,
          "font_size": 31,
          "lines_coords": [[784.0, 87.0], [813.0, 87.0], ...],
          "lines": ["「神童」と", "「オゴ」と呼ばれていたか。。。"]
        }
      ],
      "success": true
    }
  },
  "executionTime": 1500
}
```

**Text Block Fields:**
- `box` (array): Bounding box [x1, y1, x2, y2]
- `vertical` (boolean): Text direction (true = vertical)
- `font_size` (number): Font size in pixels
- `lines_coords` (array): Corner coordinates of text box
- `lines` (array): Extracted text lines

---

### 3. Process Batch

Extract text from multiple manga page images.

**Endpoint:** `POST /` or `POST /runsync`

**Request:**
```json
{
  "input": {
    "type": "process_batch",
    "title": "My Manga Chapter 1",
    "images": [
      "BASE64_IMAGE_1",
      "BASE64_IMAGE_2",
      "BASE64_IMAGE_3"
    ]
  }
}
```

**Fields:**
- `title` (string, optional): Manga title (default: "Manga")
- `images` (array of strings, required): Array of base64-encoded images

**Response:**
```json
{
  "id": "job-id-789",
  "status": "COMPLETED",
  "output": {
    "status": "success",
    "title": "My Manga Chapter 1",
    "pages": [
      {
        "page_index": 0,
        "text_blocks": [
          {
            "box": [751, 86, 819, 226],
            "vertical": true,
            "font_size": 31,
            "lines": ["Text 1"]
          }
        ]
      },
      {
        "page_index": 1,
        "text_blocks": [...]
      }
    ]
  },
  "executionTime": 5000
}
```

---

## Job Status

All requests return immediately with a job ID. For long-running tasks (OCR), you may need to poll for completion.

**Response (when job is IN_QUEUE):**
```json
{
  "id": "job-id-123",
  "status": "IN_QUEUE"
}
```

**Check job status:**
```bash
curl https://api.runpod.ai/v2/cees37s3ci8vp4/status/{job_id} \
  -H "Authorization: Bearer YOUR_KEY"
```

---

## Error Responses

**Format:**
```json
{
  "id": "job-id-error",
  "status": "FAILED",
  "error": "Error message",
  "output": {
    "error": "Error message",
    "traceback": "Stack trace...",
    "code": 500
  }
}
```

---

## Example Integration Code

### JavaScript / TypeScript

```typescript
// Health Check
async function healthCheck() {
  const response = await fetch('https://reliable-webshots-iii-reed.trycloudflare.com/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      input: { type: 'health' }
    })
  });

  const result = await response.json();
  console.log(result.output.status); // "healthy"
  console.log(result.output.gpu); // "NVIDIA GeForce RTX 4090"
}

// Process Single Page
async function processPage(base64Image: string) {
  const response = await fetch('https://reliable-webshots-iii-reed.trycloudflare.com/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      input: {
        type: 'process_single',
        image: base64Image,  // Base64 only, no data:image prefix
        page_index: 0
      }
    })
  });

  const result = await response.json();

  if (result.status === 'COMPLETED') {
    result.output.result.text_blocks.forEach(block => {
      console.log(block.lines); // Array of text lines
      console.log(block.box); // Bounding box [x1, y1, x2, y2]
    });
  }
}

// Process Batch
async function processBatch(base64Images: string[]) {
  const response = await fetch('https://reliable-webshots-iii-reed.trycloudflare.com/', {
    method: 'POST',
    headers: { { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      input: {
        type: 'process_batch',
        title: 'My Manga',
        images: base64Images
      }
    })
  });

  const result = await response.json();

  if (result.status === 'COMPLETED') {
    result.output.pages.forEach(page => {
      console.log(`Page ${page.page_index}:`);
      page.text_blocks.forEach(block => {
        console.log('  Text:', block.lines);
      });
    });
  }
}
```

### React Native Example

```typescript
import { View, Image, Button, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';

export default function MangaScanner() {
  const handlePickImage = async () => {
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 1,
        base64: true,
      });

      if (!result.canceled) {
        const base64Image = result.assets[0].base64 || '';

        // Call API
        const response = await fetch('https://reliable-webshots-iii-reed.trycloudflare.com/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            input: {
              type: 'process_single',
              image: base64Image,
              page_index: 0
            }
          })
        });

        const result = await response.json();

        if (result.status === 'COMPLETED') {
          const textBlocks = result.output.result.text_blocks;
          textBlocks.forEach(block => {
            console.log('Detected text:', block.lines);
          });

          Alert.alert('Success', `Extracted ${textBlocks.length} text blocks`);
        } else {
          Alert.alert('Error', 'Failed to process image');
        }
      }
    } catch (error) {
      Alert.alert('Error', error.message);
    }
  };

  return (
    <View>
      <Button title="Pick Manga Page" onPress={handlePickImage} />
    </View>
  );
}
```

### Python / Requests

```python
import requests
import base64

# Health check
response = requests.post(
    'https://reliable-webshots-iii-reed.trycloudflare.com/',
    json={'input': {'type': 'health'}}
)
result = response.json()
print(f"Status: {result['output']['status']}")
print(f"GPU: {result['output']['gpu']}")

# Process single page
def process_image(image_path):
    with open(image_path, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode()

    response = requests.post(
        'https://reliable-webshots-iii-reed.trycloudflare.com/',
        json={
            'input': {
                'type': 'process_single',
                'image': image_data,
                'page_index': 0
            }
        }
    )

    result = response.json()

    for block in result['output']['result']['text_blocks']:
        print('Text:', ' '.join(block['lines']))
        print('Box:', block['box'])
```

---

## Common Errors

**Error: "No image data provided"**
- Cause: Missing or empty `image` field in `process_single`
- Fix: Ensure `image` field contains base64-encoded image data

**Error: "Animation file, Corrupted file or Unsupported type"**
- Cause: Image file is corrupted or unsupported format
- Fix: Ensure image is a valid JPEG/PNG manga page

**Error: "Job stuck in IN_QUEUE"**
- Cause: Production endpoint, workers not processing
- Fix: Check RunPod dashboard for worker status

---

## Performance Expectations

**Development (Local CPU):**
- Health check: ~1-2 seconds
- Single page: 10-20 seconds (first run: +30s for model loading)
- Batch processing: 15-30 seconds per page

**Production (RunPod GPU):**
- Health check: ~50-100ms
- Single page: ~1-2 seconds
- Batch processing: ~1-3 seconds per page

---

## Notes

1. **Base64 Encoding:** Images must be base64-encoded without the `data:image/...` prefix
2. **Async Processing:** All requests return immediately; poll `/status/{job_id}` for long-running tasks
3. **Rate Limiting:** Development endpoint has no rate limits; Production has RunPod limits
4. **Text Direction:** Manga pages typically have vertical text (Japanese)
5. **Coordinate System:** All coordinates are pixels from top-left corner

---

## Support

For issues or questions, contact the backend team or check:
- RunPod logs in the RunPod console
- Local server logs in your terminal
- GitHub issues: https://github.com/FrederickIge/sentence-samurai-backend
