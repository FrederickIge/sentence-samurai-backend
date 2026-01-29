"""
RunPod Serverless Handler for Mokuro OCR
"""
import os
import sys
import json
import base64
from typing import Dict, Any
import asyncio
from io import BytesIO
from tempfile import TemporaryDirectory
from pathlib import Path

# RunPod SDK
import runpod
import torch
from mokuro import MokuroGenerator
from mokuro.volume import Volume

# GPU Detection
CUDA_AVAILABLE = torch.cuda.is_available()
if CUDA_AVAILABLE:
    device = 'cuda'
    print(f"🚀 NVIDIA CUDA GPU detected: {torch.cuda.get_device_name(0)}")
else:
    device = 'cpu'
    print("⚠️  CUDA not available, using CPU")

# Global generator (cached across requests)
mokuro_gen = None


def load_models():
    """Load Mokuro models once and cache them"""
    global mokuro_gen
    if mokuro_gen is None:
        print("Loading Mokuro models...")
        mokuro_gen = MokuroGenerator()
        print("✅ Models loaded")


def decode_base64_images(base64_data: str) -> list:
    """Decode base64 string to image bytes"""
    images = []
    # Split by comma if multiple images
    parts = base64_data.split(',')

    for i, part in enumerate(parts):
        # Remove data URL prefix if present
        if ',' in part:
            part = part.split(',', 1)[1]

        # Decode base64
        img_bytes = base64.b64decode(part)
        images.append(BytesIO(img_bytes))

    return images


def process_single_page(image_data: bytes, page_index: int) -> Dict[str, Any]:
    """Process a single image and return OCR results"""
    global mokuro_gen

    # Create temp file
    with TemporaryDirectory() as temp_dir:
        # Save image
        img_path = Path(temp_dir) / f"page_{page_index}.jpg"
        with open(img_path, 'wb') as f:
            f.write(image_data)

        # Process with Mokuro (create Volume object)
        volume = Volume(Path(temp_dir))
        mokuro_gen.process_volume(volume)

        # Read results
        mokuro_path = Path(temp_dir) / f"page_{page_index}.mokuro.json"

        if not mokuro_path.exists():
            return {
                "error": "Failed to process page",
                "page_index": page_index
            }

        with open(mokuro_path, 'r') as f:
            mokuro_data = json.load(f)

        # Extract text blocks for this page
        pages = mokuro_data.get('pages', [])
        if pages:
            blocks = pages[0].get('blocks', [])
        else:
            blocks = []

        return {
            "page_index": page_index,
            "text_blocks": blocks,
            "success": True
        }


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    RunPod Serverless Handler

    Args:
        job: RunPod job object with 'input' key containing the request data

    Returns:
        Dict with processing results
    """
    print(f"📥 Received job: {job.get('id', 'unknown')}")

    # Load models on first request
    load_models()

    # Parse input (safe access)
    input_data = job.get("input", {})
    print(f"🔍 Input type: {input_data.get('type', 'unknown')}")

    # Get request type
    request_type = input_data.get('type', 'process_single')

    try:
        if request_type == 'health':
            print("✅ Health check requested")
            return {
                "status": "healthy",
                "gpu": torch.cuda.get_device_name(0) if CUDA_AVAILABLE else "cpu",
                "cuda_available": CUDA_AVAILABLE
            }

        elif request_type == 'process_single':
            # Single page processing
            image_b64 = input_data.get('image')
            page_index = input_data.get('page_index', 0)

            if not image_b64:
                return {
                    "error": "No image data provided",
                    "code": 400
                }

            # Decode image
            image_bytes = base64.b64decode(image_b64)

            # Process
            result = process_single_page(image_bytes, page_index)

            print(f"✅ Successfully processed page {page_index}")
            return {
                "status": "success",
                "result": result
            }

        elif request_type == 'process_batch':
            # Batch processing
            images_b64 = input_data.get('images', [])
            title = input_data.get('title', 'Manga')

            if not images_b64:
                return {
                    "error": "No images provided",
                    "code": 400
                }

            # Process all images
            results = []
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Save all images
                image_paths = []
                for i, img_b64 in enumerate(images_b64):
                    img_path = temp_path / f"page_{i:04d}.jpg"
                    with open(img_path, 'wb') as f:
                        f.write(base64.b64decode(img_b64))
                    image_paths.append(img_path)

                # Process with Mokuro (create Volume object)
                volume = Volume(temp_path)
                mokuro_gen.process_volume(volume)

                # Collect results
                for i, img_path in enumerate(image_paths):
                    mokuro_path = temp_path / f"{img_path.stem}.mokuro.json"

                    if mokuro_path.exists():
                        with open(mokuro_path, 'r') as f:
                            mokuro_data = json.load(f)

                        pages = mokuro_data.get('pages', [])
                        blocks = pages[0].get('blocks', []) if pages else []

                        results.append({
                            "page_index": i,
                            "text_blocks": blocks
                        })

            print(f"✅ Successfully processed batch of {len(results)} pages")
            return {
                "status": "success",
                "title": title,
                "pages": results
            }

        else:
            return {
                "error": f"Unknown request type: {request_type}",
                "code": 400
            }

    except Exception as e:
        import traceback
        print(f"❌ Error processing job: {str(e)}")
        print(traceback.format_exc())
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "code": 500
        }


# Start RunPod Serverless
if __name__ == "__main__":
    print("🚀 Starting Mokuro OCR Serverless Handler")
    print("✅ Handler module loaded successfully")
    try:
        runpod.serverless.start({"handler": handler})
    except Exception as e:
        print(f"❌ Failed to start serverless worker: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
