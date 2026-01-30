#!/usr/bin/env python3
"""
Pre-download and cache Mokuro models for faster cold starts.
Run during Docker build to cache models in the container image.
"""
import os
import sys
from pathlib import Path

# Set cache directory before importing mokuro
cache_dir = Path("/workspace/cache")
cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(cache_dir)

print("🔧 Pre-downloading Mokuro models...")
print(f"📁 Cache directory: {cache_dir}")

try:
    # Import after setting cache directory
    from mokuro import MokuroGenerator

    print("📥 Initializing MokuroGenerator (this will download models)...")
    mokuro_gen = MokuroGenerator()

    print("✅ Models downloaded successfully!")
    print()
    print("📊 Cached models:")

    # List cached files
    for root, dirs, files in os.walk(cache_dir):
        level = root.replace(str(cache_dir), '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            file_path = Path(root) / file
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"{subindent}{file} ({size_mb:.1f} MB)")

    print()
    print("✅ Model caching complete!")

except Exception as e:
    print(f"❌ Error downloading models: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
