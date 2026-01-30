#!/usr/bin/env python3
"""
Pre-download and cache Mokuro models for faster cold starts.
Run during Docker build to cache models in the container image.
"""
import os
import sys
import urllib.request
from pathlib import Path

# Set ALL cache environment variables before importing mokuro
cache_dir = Path("/workspace/cache")
cache_dir.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"] = str(cache_dir)
os.environ["HF_DATASETS_CACHE"] = str(cache_dir / "datasets")
os.environ["TRANSFORMERS_CACHE"] = str(cache_dir / "transformers")
os.environ["HUGGINGFACE_HUB_CACHE"] = str(cache_dir / "hub")
os.environ["XDG_CACHE_HOME"] = str(cache_dir)  # For mokuro text detector

print("🔧 Pre-downloading Mokuro models...")
print(f"📁 Cache directory: {cache_dir}")
print(f"   HF_HOME={os.environ['HF_HOME']}")
print(f"   XDG_CACHE_HOME={os.environ['XDG_CACHE_HOME']}")

try:
    # 1. Download comictextdetector.pt explicitly
    print("\n📥 Downloading text detector model...")
    detector_url = "https://github.com/zyddnys/manga-image-translator/releases/download/beta-0.2.1/comictextdetector.pt"
    detector_path = cache_dir / "comictextdetector.pt"

    if not detector_path.exists():
        print(f"   Downloading from {detector_url}")
        urllib.request.urlretrieve(detector_url, detector_path)
        size_mb = detector_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Downloaded comictextdetector.pt ({size_mb:.1f} MB)")
    else:
        print(f"   ✅ comictextdetector.pt already cached")

    # 2. Import mokuro and download HF models
    print("\n📥 Initializing MokuroGenerator (downloads HF models)...")
    from mokuro import MokuroGenerator

    mokuro_gen = MokuroGenerator()

    print("\n✅ All models downloaded successfully!")
    print("\n📊 Cached files:")

    # List cached files
    total_size = 0
    for root, dirs, files in os.walk(cache_dir):
        level = root.replace(str(cache_dir), '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            file_path = Path(root) / file
            size_mb = file_path.stat().st_size / (1024 * 1024)
            total_size += size_mb
            print(f"{subindent}{file} ({size_mb:.1f} MB)")

    print(f"\n📦 Total cache size: {total_size:.1f} MB")
    print("✅ Model caching complete!")

except Exception as e:
    print(f"❌ Error downloading models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
