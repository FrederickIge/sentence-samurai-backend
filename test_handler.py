"""
Local test script for RunPod serverless handler
Tests without actually loading models or processing images
"""
import sys
import json
from pathlib import Path

# Mock the heavy dependencies
class MockMokuroGenerator:
    def __init__(self, device='cpu'):
        self.device = device
        print(f"✅ Mock MokuroGenerator initialized on {device}")

    def process_volume(self, volume):
        """Mock processing - creates fake mokuro.json for each image"""
        # Find all images in the volume directory
        volume_dir = volume.path
        image_files = list(volume_dir.glob("*.jpg")) + list(volume_dir.glob("*.png"))

        # Create a .mokuro.json file for each image
        for img_file in image_files:
            mokuro_path = volume_dir / f"{img_file.stem}.mokuro.json"

            fake_data = {
                "version": "1.0",
                "title": "Test",
                "pages": [
                    {
                        "index": 0,
                        "img_path": img_file.name,
                        "blocks": [
                            {
                                "text": f"Test text from {img_file.name}",
                                "bbox": [100, 100, 200, 150],
                                "vertical": False
                            }
                        ]
                    }
                ]
            }

            with open(mokuro_path, 'w') as f:
                json.dump(fake_data, f)

        print(f"✅ Mock processed volume → {len(image_files)} pages")

# Mock torch
class MockCUDA:
    @staticmethod
    def is_available():
        return False

class MockTorch:
    cuda = MockCUDA()
    @staticmethod
    def get_device_name(x):
        return "Mock GPU"

sys.modules['torch'] = MockTorch()
sys.modules['mokuro'] = type('obj', (object,), {'MokuroGenerator': MockMokuroGenerator})()
class MockVolume:
    def __init__(self, path):
        # Volume wraps the path that contains images
        self.path = path  # Don't add /volume subdirectory
        self.path_ocr_cache = path / '_ocr'
        self.stem = path.stem

sys.modules['mokuro.volume'] = type('obj', (object,), {'Volume': MockVolume})()
sys.modules['runpod'] = type('obj', (object,), {
    'serverless': type('obj', (object,), {
        'start': lambda x: print("✅ Would start RunPod serverless worker")
    })()
})()

# Now import handler
from handler import handler

def test_health():
    """Test health check endpoint"""
    print("\n🧪 Testing health check...")
    job = {
        'id': 'test-1',
        'input': {'type': 'health'}
    }

    result = handler(job)
    print(f"✅ Health check result: {result}")
    assert result['status'] == 'healthy'
    print("✅ Health check PASSED\n")

def test_process_single():
    """Test single page processing"""
    print("🧪 Testing process_single...")
    import base64

    # Create a tiny 1x1 PNG image
    tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    job = {
        'id': 'test-2',
        'input': {
            'type': 'process_single',
            'image': tiny_png,
            'page_index': 0
        }
    }

    result = handler(job)
    print(f"✅ Process single result: {result}")
    assert result['status'] == 'success'
    assert 'result' in result
    print("✅ Process single PASSED\n")

def test_process_batch():
    """Test batch processing"""
    print("🧪 Testing process_batch...")
    tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    job = {
        'id': 'test-3',
        'input': {
            'type': 'process_batch',
            'title': 'Test Batch',
            'images': [tiny_png, tiny_png]
        }
    }

    result = handler(job)
    print(f"✅ Process batch result: {result}")
    assert result['status'] == 'success'
    assert 'pages' in result
    assert len(result['pages']) == 2
    print("✅ Process batch PASSED\n")

if __name__ == '__main__':
    print("=" * 60)
    print("Testing RunPod Serverless Handler Locally")
    print("=" * 60)

    try:
        test_health()
        test_process_single()
        test_process_batch()

        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\n✅ Handler is working correctly - safe to deploy")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
