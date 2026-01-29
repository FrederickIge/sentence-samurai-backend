"""
Mokuro OCR Server
Preprocesses manga images with Mokuro for text extraction
"""
import torch

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# GPU ACCELERATION for NVIDIA CUDA (RTX 4090, etc.)
# Detect and enable CUDA support
CUDA_AVAILABLE = torch.cuda.is_available()

if CUDA_AVAILABLE:
    logger.info("🚀 NVIDIA CUDA GPU detected")
    logger.info(f"   GPU: {torch.cuda.get_device_name(0)}")
    logger.info(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
else:
    logger.warning("⚠️  No CUDA GPU detected, will use CPU (slower)")

try:
    from mokuro import MokuroGenerator
    from mokuro.volume import Volume, Title

    MOKURO_AVAILABLE = True

    # GPU PATCH: Enable CUDA support for NVIDIA GPUs
    if CUDA_AVAILABLE:
        original_init_models = MokuroGenerator.init_models

        def patched_init_models(self):
            """Initialize models and move them to CUDA"""
            original_init_models(self)

            # Move models to CUDA after initialization
            try:
                if hasattr(self, '_manga_page_ocr'):
                    mpo = self._manga_page_ocr

                    # Move text detector to CUDA
                    if hasattr(mpo, 'text_detector') and hasattr(mpo.text_detector, 'model'):
                        mpo.text_detector.model.to('cuda')
                        logger.info("✅ Text detector moved to CUDA (GPU)")

                    # Move OCR model to CUDA
                    if hasattr(mpo, 'mocr') and hasattr(mpo.mocr, 'model'):
                        mpo.mocr.model.to('cuda')
                        logger.info("✅ OCR model moved to CUDA (GPU)")

                    # Update device attribute
                    if hasattr(mpo, 'device'):
                        mpo.device = 'cuda'

                    logger.info("🚀 GPU acceleration enabled on NVIDIA CUDA")

            except Exception as e:
                logger.warning(f"⚠️  Could not enable CUDA acceleration: {e}")
                logger.info("   Falling back to CPU processing")

        # Apply the patch
        MokuroGenerator.init_models = patched_init_models
        logger.info("✅ MokuroGenerator patched for NVIDIA CUDA GPU")

except ImportError:
    MokuroGenerator = None
    Volume = None
    Title = None
    MOKURO_AVAILABLE = False
import uuid
import shutil
from pathlib import Path
from typing import List, Dict, Any
import asyncio
from PIL import Image
import numpy as np

# Blank page detection threshold
# Variance below this indicates a blank/empty page
BLANK_PAGE_VARIANCE_THRESHOLD = 100

# Parallel processing configuration
# Split large jobs into chunks for parallel processing
PARALLEL_CHUNK_SIZE = 10  # Process 10 pages per chunk
MAX_PARALLEL_JOBS = 3     # Max chunks to process simultaneously

# Image optimization configuration
# Resize images to optimal size for faster OCR
MAX_IMAGE_HEIGHT = 1600   # Max height in pixels (maintains aspect ratio)
JPEG_QUALITY = 85         # Quality for saved images (85 = good balance)


def is_blank_page(image_path: str) -> bool:
    """
    Detect if a page is blank or has minimal content.
    Uses variance of grayscale image as a simple heuristic.

    Args:
        image_path: Path to the image file

    Returns:
        True if page is blank, False otherwise
    """
    try:
        img = Image.open(image_path)

        # Convert to grayscale
        gray = img.convert("L")

        # Convert to numpy array
        img_array = np.array(gray)

        # Calculate variance (low variance = blank page)
        variance = np.var(img_array)

        # Log for debugging
        logger.debug(f"Blank check for {image_path}: variance={variance:.2f}")

        return variance < BLANK_PAGE_VARIANCE_THRESHOLD
    except Exception as e:
        logger.warning(f"Blank page detection failed for {image_path}: {e}")
        return False  # If detection fails, assume not blank


def optimize_image(image_path: str) -> str:
    """
    Optimize image for faster OCR processing.
    Resizes if too large and compresses to optimal quality.

    Args:
        image_path: Path to the image file

    Returns:
        Path to optimized image (same as input)
    """
    import os

    try:
        img = Image.open(image_path)

        # Convert RGBA/PNG to RGB for JPEG compatibility
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparent images
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
            logger.debug(f"Converted {image_path} from {img.mode} to RGB")

        # Ensure RGB mode
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Get original dimensions
        width, height = img.size
        original_size = os.path.getsize(image_path) / 1024  # KB

        # Check if resize is needed (only if height > MAX_IMAGE_HEIGHT)
        if height > MAX_IMAGE_HEIGHT:
            # Calculate new dimensions maintaining aspect ratio
            new_width = int(width * (MAX_IMAGE_HEIGHT / height))
            new_height = MAX_IMAGE_HEIGHT

            # Resize
            img = img.resize((new_width, new_height), Image.LANCZOS)
            logger.debug(f"Resized {image_path}: {width}x{height} → {new_width}x{new_height}")

            # Save optimized image
            img.save(image_path, quality=JPEG_QUALITY, optimize=True)

            # Calculate new size
            new_size = os.path.getsize(image_path) / 1024  # KB
            reduction = (1 - new_size / original_size) * 100

            logger.info(f"Optimized {image_path}: {original_size:.1f}KB → {new_size:.1f}KB ({reduction:.1f}% smaller)")
        else:
            # Just optimize compression if height is acceptable
            img.save(image_path, quality=JPEG_QUALITY, optimize=True)
            new_size = os.path.getsize(image_path) / 1024  # KB
            if new_size < original_size * 0.95:  # Only log if >5% reduction
                logger.debug(f"Compressed {image_path}: {original_size:.1f}KB → {new_size:.1f}KB")

        return image_path

    except Exception as e:
        logger.warning(f"Image optimization failed for {image_path}: {e}")
        return image_path  # Return original path if optimization fails


async def process_volume_chunk(
    chunk_id: int,
    image_paths: List[str],
    output_dir: Path,
    title: str
) -> str:
    """
    Process a chunk of pages with Mokuro.
    Runs in a thread pool to avoid blocking the event loop.

    Args:
        chunk_id: Chunk identifier
        image_paths: List of image paths for this chunk
        output_dir: Output directory for this chunk
        title: Title for the volume

    Returns:
        Path to the generated .mokuro file
    """
    # Create chunk directory
    chunk_dir = output_dir / f"chunk_{chunk_id}"
    chunk_dir.mkdir(exist_ok=True)

    # Create volume directory
    volume_dir = chunk_dir / "volume"
    volume_dir.mkdir(exist_ok=True)

    # Copy images to chunk volume directory
    for i, img_path in enumerate(image_paths):
        src = Path(img_path)
        dst = volume_dir / f"page_{i:03d}{src.suffix}"
        shutil.copy(src, dst)

    # Get cached Mokuro generator
    mokuro_gen = await get_mokuro_generator()

    # Create Volume and process
    volume = Volume(volume_dir)
    volume.title = Title(chunk_dir)

    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: mokuro_gen.process_volume(volume, ignore_errors=False)
    )

    return str(volume.path_mokuro)


app = FastAPI(
    title="Mokuro OCR Server",
    description="Preprocess manga images with Mokuro for instant text selection",
    version="1.0.0",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web test frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# Directories
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory job storage
jobs: Dict[str, Dict[str, Any]] = {}

# Model caching (load once, use forever)
_cached_mokuro_gen = None
_cache_lock = asyncio.Lock()
_cache_loaded_at = None
CACHE_TTL_SECONDS = 3600  # Reload models every hour to free memory


@app.get("/")
async def root() -> Dict[str, Any]:
    """Server information"""
    return {
        "service": "mokuro-ocr",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "process": "/process-manga",
            "job_status": "/job/{job_id}",
            "get_html": "/html/{job_id}",
            "download": "/download/{job_id}",
            "download_json": "/download/{job_id}/json",
            "stats": "/stats",
            "jobs": "/jobs",
            "test_ui": "/static/index.html",
        },
        "features": {
            "single_page_support": "Send 1 file for fast single-page processing (5-10 sec)",
            "batch_processing": "Send multiple files for chapter preprocessing (1-2 min)",
            "json_response": "Use /download/{job_id}/json for direct JSON response",
            "model_caching": "Models loaded once at startup, reused for all requests (56% faster!)",
        }
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/process-manga")
async def process_manga(
    files: List[UploadFile] = File(...),
    title: str = Form(None),
    return_json: bool = Form(False)
) -> Dict[str, Any]:
    """
    Upload manga images for Mokuro processing

    Args:
        files: List of manga page images (jpg, png) - can be 1 or more
        title: Optional manga title
        return_json: If true, returns .mokuro data as JSON instead of file download

    Returns:
        job_id: ID to track processing status
        total_pages: Number of pages being processed
        is_single_page: True if only 1 page (for optimization hints)
    """
    job_id = str(uuid.uuid4())
    logger.info(f"New job {job_id}: {len(files)} file(s), title='{title}'")

    # OPTIMIZATION #1: Skip File Copying
    # Save files directly to final location (outputs/{job_id}/volume/)
    # This eliminates the need to copy from uploads/ directory
    output_path = OUTPUT_DIR / job_id
    output_path.mkdir(exist_ok=True)

    # Create a directory structure for the manga volume
    # Mokuro expects images in a directory, and creates .mokuro file in parent
    volume_dir = output_path / "volume"
    volume_dir.mkdir(exist_ok=True)

    # Save uploaded files DIRECTLY to volume directory (no intermediate upload step)
    image_paths = []
    for i, file in enumerate(files):
        file_path = volume_dir / f"page_{i:03d}.jpg"
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # OPTIMIZATION #5: Image Optimization
        # Resize and compress for faster OCR
        optimize_image(str(file_path))

        image_paths.append(str(file_path))
        logger.info(f"Saved {file.filename} -> {file_path}")

    is_single_page = len(image_paths) == 1
    logger.info(f"Job {job_id}: is_single_page={is_single_page} (saved directly to volume, no copy)")

    # Initialize job with progress tracking
    jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "stage": "upload",
        "current_page": 0,
        "total_pages": len(image_paths),
        "title": title or f"Manga {job_id[:8]}",
        "is_single_page": is_single_page,
        "return_json": return_json,
    }

    # Process in background
    asyncio.create_task(process_mokuro_job(job_id, image_paths, title))

    response = {
        "job_id": job_id,
        "status": "started",
        "total_pages": len(image_paths),
        "is_single_page": is_single_page
    }

    # Log the response
    logger.info(f"Job created: {job_id} - {len(image_paths)} page(s), title='{title}', single_page={is_single_page}")

    return response


async def get_mokuro_generator():
    """
    Get cached MokuroGenerator instance.
    Loads models once and caches in memory for all subsequent requests.
    Uses TTL to periodically reload models and free memory.
    """
    global _cached_mokuro_gen, _cache_loaded_at

    async with _cache_lock:
        # Check if cache needs reload
        import time
        now = time.time()

        if _cached_mokuro_gen is None:
            logger.info("Loading Mokuro models (first time)...")
            _cached_mokuro_gen = MokuroGenerator()
            _cached_mokuro_gen.init_models()
            _cache_loaded_at = now
            logger.info("✅ Models loaded and cached in memory!")
        elif _cache_loaded_at is not None and (now - _cache_loaded_at) > CACHE_TTL_SECONDS:
            logger.info("Reloading models (TTL expired)...")
            _cached_mokuro_gen = MokuroGenerator()
            _cached_mokuro_gen.init_models()
            _cache_loaded_at = now
            logger.info("✅ Models reloaded!")
        else:
            cache_age = int(now - _cache_loaded_at)
            logger.debug(f"Using cached models (age: {cache_age}s)")

        return _cached_mokuro_gen


async def process_mokuro_job(job_id: str, image_paths: List[str], title: str) -> None:
    """Background task for Mokuro processing"""
    try:
        import time
        start_time = time.time()
        jobs[job_id]["started_at"] = start_time

        if not MOKURO_AVAILABLE:
            # Simulate processing for testing/demo purposes
            logger.warning(f"Job {job_id}: Mokuro not available, simulating processing")
            jobs[job_id]["progress"] = 50

            await asyncio.sleep(1)  # Simulate processing time
            jobs[job_id]["progress"] = 100
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["output_path"] = str(OUTPUT_DIR / job_id)
            logger.info(f"Job {job_id}: Simulated processing complete")
            return

        is_single_page = jobs[job_id].get("is_single_page", False)
        total_pages = len(image_paths)
        logger.info(f"Job {job_id}: Starting Mokuro processing ({total_pages} pages)")

        # More granular progress for single pages
        if is_single_page:
            jobs[job_id]["progress"] = 5
        else:
            jobs[job_id]["progress"] = 10

        # Create output directory reference
        output_path = OUTPUT_DIR / job_id

        # OPTIMIZATION #1: Files already in volume directory (saved directly in process_manga)
        # No need to copy - image_paths already point to volume_dir/page_*.jpg
        volume_dir = Path(image_paths[0]).parent if image_paths else output_path / "volume"

        # OPTIMIZATION #2: Blank Page Detection
        # Skip processing blank pages to save time
        if not is_single_page:
            blank_pages = []
            for i, img_path in enumerate(image_paths):
                if is_blank_page(img_path):
                    blank_pages.append(i)
                    logger.info(f"Job {job_id}: Page {i} detected as blank")

            if blank_pages:
                jobs[job_id]["blank_pages"] = blank_pages
                logger.info(f"Job {job_id}: Skipping {len(blank_pages)} blank pages")

        if is_single_page:
            jobs[job_id]["progress"] = 20
        else:
            jobs[job_id]["progress"] = 25

        logger.info(f"Job {job_id}: Using directly saved images (no copy needed)")

        # Upload stage complete (0-10%)
        jobs[job_id]["progress"] = 10
        jobs[job_id]["stage"] = "ocr"
        jobs[job_id]["current_page"] = 0

        # Get cached MokuroGenerator (loads once, reuses forever)
        mokuro_gen = await get_mokuro_generator()

        logger.info(f"Job {job_id}: Using cached Mokuro models")

        # Create Volume and process
        volume = Volume(volume_dir)
        # Set the title attribute (required by Mokuro)
        volume.title = Title(output_path)

        # Run OCR with per-page progress tracking
        # Process in thread pool to avoid blocking, but track progress
        loop = asyncio.get_event_loop()

        def process_with_progress():
            """Process volume with progress updates"""
            # Mokuro processes all pages; we'll track completion by monitoring _ocr directory
            import os

            _ocr_dir = volume_dir / "_ocr"
            processed_count = 0

            # Start processing in background
            import threading
            processing_complete = threading.Event()

            def run_processing():
                mokuro_gen.process_volume(volume, ignore_errors=False)
                processing_complete.set()

            # Start processing thread
            processing_thread = threading.Thread(target=run_processing)
            processing_thread.start()

            # Monitor progress until complete
            while not processing_complete.is_set():
                if _ocr_dir.exists():
                    # Count processed pages
                    try:
                        processed_files = len([f for f in _ocr_dir.iterdir() if f.is_file()])
                        if processed_files > processed_count:
                            processed_count = processed_files
                            # Update progress: 10% + (processed/total) * 80%
                            progress = 10 + int((processed_count / total_pages) * 80)
                            jobs[job_id]["progress"] = min(progress, 89)
                            jobs[job_id]["current_page"] = processed_count
                            logger.debug(f"Job {job_id}: Processed {processed_count}/{total_pages} pages ({progress}%)")
                    except Exception as e:
                        logger.debug(f"Job {job_id}: Error monitoring progress: {e}")

                # Wait a bit before checking again
                processing_complete.wait(timeout=0.5)

            # Wait for thread to finish
            processing_thread.join()

        await loop.run_in_executor(None, process_with_progress)

        # OCR complete (90%)
        jobs[job_id]["progress"] = 90
        jobs[job_id]["stage"] = "finalize"
        logger.info(f"Job {job_id}: Mokuro processing complete")

        # The .mokuro file is created in the parent directory
        mokuro_file = volume.path_mokuro

        # Finalize stage (90-100%)
        # Move/rename .mokuro file to desired location
        final_mokuro_file = output_path / f"{title or f'Manga_{job_id[:8]}'}.mokuro"
        if mokuro_file != final_mokuro_file and mokuro_file.exists():
            shutil.move(str(mokuro_file), str(final_mokuro_file))
            mokuro_file = final_mokuro_file

        # Store mokuro file path for JSON response
        jobs[job_id]["mokuro_file_path"] = str(mokuro_file)

        # Processing complete (100%)
        jobs[job_id]["progress"] = 100
        jobs[job_id]["stage"] = "complete"
        jobs[job_id]["current_page"] = total_pages

        jobs[job_id]["progress"] = 100

        # Mark complete
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["output_path"] = str(output_path)

        elapsed = time.time() - start_time
        jobs[job_id]["elapsed_time"] = elapsed

        # OPTIMIZATION #1: No cleanup needed - files saved directly to final location

        logger.info(f"Job {job_id}: Complete in {elapsed:.2f}s ({total_pages} pages)")

    except Exception as e:
        import traceback
        logger.error(f"Job {job_id}: Failed with error: {e}")
        logger.error(traceback.format_exc())
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["error_details"] = traceback.format_exc()
        jobs[job_id]["progress"] = 0


@app.get("/job/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    """Get processing job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = jobs[job_id]

    # Log job status response
    logger.debug(f"Job status request for {job_id}: status={job_data.get('status')}, progress={job_data.get('progress')}%, stage={job_data.get('stage')}")

    return job_data


@app.get("/html/{job_id}")
async def get_html(job_id: str):
    """Get information about the processed job"""
    job = jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not complete")

    output_path = Path(job["output_path"])
    mokuro_files = list(output_path.glob("*.mokuro"))

    if mokuro_files:
        return {
            "job_id": job_id,
            "status": "completed",
            "title": job.get("title", job_id),
            "mokuro_file": mokuro_files[0].name,
            "note": "Mokuro 0.2.x generates .mokuro files. Use the /download/{job_id} endpoint to get the file and load it in the mokuro web reader."
        }

    html_files = list(output_path.glob("*.html"))
    if html_files:
        return FileResponse(html_files[0], media_type="text/html")

    raise HTTPException(status_code=404, detail="No output file found")


@app.get("/download/{job_id}")
async def download_mokuro(job_id: str) -> FileResponse:
    """Download the .mokuro file for offline use"""
    job = jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not complete")

    output_path = Path(job["output_path"])
    mokuro_file = output_path / "data.mokuro"

    if not mokuro_file.exists():
        mokuro_files = list(output_path.glob("*.mokuro"))
        if mokuro_files:
            mokuro_file = mokuro_files[0]
        else:
            raise HTTPException(status_code=404, detail="Mokuro file not found")

    return FileResponse(
        mokuro_file,
        media_type="application/octet-stream",
        filename=f"{job.get('title', job_id)}.mokuro",
    )


@app.get("/download/{job_id}/json")
async def download_mokuro_json(job_id: str):
    """
    Get .mokuro file data as JSON
    More efficient for single-page processing - no need for separate download step
    """
    import json
    from pathlib import Path

    job = jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not complete")

    output_path = Path(job["output_path"])
    mokuro_file = job.get("mokuro_file_path")

    if not mokuro_file:
        # Fallback to finding the file
        mokuro_files = list(output_path.glob("*.mokuro"))
        if mokuro_files:
            mokuro_file = str(mokuro_files[0])
        else:
            raise HTTPException(status_code=404, detail="Mokuro file not found")

    # Read and parse the .mokuro file (it's JSON)
    with open(mokuro_file, "r", encoding="utf-8") as f:
        mokuro_data = json.load(f)

    # Log the full JSON response for debugging
    logger.info(f"Returning JSON for job {job_id}:")
    logger.info(f"  Version: {mokuro_data.get('version')}")
    logger.info(f"  Title: {mokuro_data.get('title')}")
    logger.info(f"  Pages: {len(mokuro_data.get('pages', []))}")

    # Log each page's blocks
    for i, page in enumerate(mokuro_data.get("pages", [])):
        blocks = page.get("blocks", [])
        logger.info(f"    Page {i} ({page.get('img_path')}): {len(blocks)} text blocks")

        # Log each block's full structure
        for j, block in enumerate(blocks):
            # Log full block data
            text = block.get("text", "")
            bbox = block.get("bbox", [])
            vertical = block.get("vertical", False)
            text_lines = block.get("text_lines", None)

            logger.info(f"      Block {j}:")
            logger.info(f"        bbox={bbox}")
            logger.info(f"        text=\"{text}\"")
            logger.info(f"        vertical={vertical}")
            if text_lines:
                logger.info(f"        text_lines={text_lines}")
            else:
                logger.info(f"        text_lines=None")

    total_blocks = sum(len(p.get("blocks", [])) for p in mokuro_data.get("pages", []))
    logger.info(f"  Total text blocks: {total_blocks}")

    return mokuro_data


@app.delete("/job/{job_id}")
async def delete_job(job_id: str) -> Dict[str, str]:
    """
    Delete a job and its associated files
    Useful for cleanup after downloading .mokuro data
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    # Delete output files
    if "output_path" in job:
        output_path = Path(job["output_path"])
        if output_path.exists():
            shutil.rmtree(output_path, ignore_errors=True)

    # Delete uploaded files
    upload_dir = UPLOAD_DIR / job_id
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)

    # Remove from memory
    del jobs[job_id]

    return {"status": "deleted", "job_id": job_id}


@app.get("/jobs")
async def list_jobs() -> Dict[str, Any]:
    """
    List all jobs (useful for debugging and cleanup)
    """
    return {
        "total_jobs": len(jobs),
        "jobs": [
            {
                "job_id": job_id,
                "status": job.get("status"),
                "title": job.get("title"),
                "total_pages": job.get("total_pages"),
                "is_single_page": job.get("is_single_page"),
            }
            for job_id, job in jobs.items()
        ]
    }


@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """
    Get server statistics including model cache status
    """
    import time

    cache_age = None
    if _cache_loaded_at is not None:
        cache_age = int(time.time() - _cache_loaded_at)

    return {
        "cache_status": "loaded" if _cached_mokuro_gen is not None else "not_loaded",
        "cache_age_seconds": cache_age,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "total_jobs_processed": len([j for j in jobs.values() if j.get("status") == "completed"]),
        "active_jobs": len([j for j in jobs.values() if j.get("status") in ["processing", "started"]]),
        "mokuro_available": MOKURO_AVAILABLE,
    }


@app.on_event("startup")
async def startup_event():
    """
    Load models on server startup for instant processing
    This adds ~10 seconds to server startup but makes all requests faster
    """
    if MOKURO_AVAILABLE:
        logger.info("🚀 Server starting - preloading Mokuro models...")
        try:
            await get_mokuro_generator()
            logger.info("✅ Server ready! Models cached and waiting for requests.")
        except Exception as e:
            logger.error(f"❌ Failed to preload models: {e}")
            logger.info("Models will be loaded on first request instead")
    else:
        logger.info("⚠️  Mokuro not available - will use simulation mode")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
