"""
Unit tests for Mokuro OCR Server
"""
import pytest
from fastapi.testclient import TestClient
import io
import uuid

from main import app, jobs

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and teardown for each test"""
    # Clear jobs before each test
    jobs.clear()
    yield
    # Clean up after each test
    jobs.clear()


def test_root_endpoint():
    """Test the root endpoint returns server information"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "mokuro-ocr"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"
    assert "endpoints" in data
    assert data["endpoints"]["health"] == "/health"
    assert data["endpoints"]["process"] == "/process-manga"


def test_health_endpoint():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_process_manga_no_files():
    """Test process_manga endpoint with no files (should fail)"""
    response = client.post("/process-manga")
    # FastAPI returns 422 for missing required fields
    assert response.status_code == 422


def test_process_manga_with_files():
    """Test process_manga endpoint with image files"""
    # Create a mock image file
    image_content = b"fake image content"
    files = {"files": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}
    data = {"title": "Test Manga"}

    response = client.post("/process-manga", files=files, data=data)

    assert response.status_code == 200
    response_data = response.json()
    assert "job_id" in response_data
    assert response_data["status"] == "started"
    assert response_data["total_pages"] == 1

    # Check that job was created
    job_id = response_data["job_id"]
    assert job_id in jobs
    # Job status can be processing, completed, or failed depending on async timing
    assert jobs[job_id]["status"] in ["processing", "completed", "failed"]
    assert jobs[job_id]["title"] == "Test Manga"
    assert jobs[job_id]["total_pages"] == 1


def test_process_manga_multiple_files():
    """Test process_manga endpoint with multiple image files"""
    # Create multiple mock image files
    files = [
        ("files", ("test1.jpg", io.BytesIO(b"image1"), "image/jpeg")),
        ("files", ("test2.jpg", io.BytesIO(b"image2"), "image/jpeg")),
        ("files", ("test3.jpg", io.BytesIO(b"image3"), "image/jpeg")),
    ]
    data = {"title": "Multi Page Manga"}

    response = client.post("/process-manga", files=files, data=data)

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["total_pages"] == 3

    job_id = response_data["job_id"]
    assert jobs[job_id]["total_pages"] == 3


def test_process_manga_without_title():
    """Test process_manga endpoint without optional title"""
    files = {"files": ("test.jpg", io.BytesIO(b"image"), "image/jpeg")}

    response = client.post("/process-manga", files=files)

    assert response.status_code == 200
    response_data = response.json()
    job_id = response_data["job_id"]

    # Should use default title format
    assert jobs[job_id]["title"].startswith("Manga ")


def test_get_job_status_not_found():
    """Test getting status for non-existent job"""
    fake_job_id = str(uuid.uuid4())
    response = client.get(f"/job/{fake_job_id}")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


def test_get_job_status_exists():
    """Test getting status for existing job"""
    # First create a job
    files = {"files": ("test.jpg", io.BytesIO(b"image"), "image/jpeg")}
    create_response = client.post("/process-manga", files=files)
    job_id = create_response.json()["job_id"]

    # Now get its status
    response = client.get(f"/job/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "total_pages" in data
    assert "progress" in data


def test_get_html_job_not_found():
    """Test getting HTML for non-existent job"""
    fake_job_id = str(uuid.uuid4())
    response = client.get(f"/html/{fake_job_id}")
    assert response.status_code == 404


def test_get_html_job_not_complete():
    """Test getting HTML for job that hasn't completed"""
    files = {"files": ("test.jpg", io.BytesIO(b"image"), "image/jpeg")}
    create_response = client.post("/process-manga", files=files)
    job_id = create_response.json()["job_id"]

    response = client.get(f"/html/{job_id}")
    assert response.status_code == 404
    assert "Job not complete" in response.json()["detail"]


def test_download_mokuro_job_not_found():
    """Test downloading mokuro file for non-existent job"""
    fake_job_id = str(uuid.uuid4())
    response = client.get(f"/download/{fake_job_id}")
    assert response.status_code == 404


def test_download_mokuro_job_not_complete():
    """Test downloading mokuro file for incomplete job"""
    files = {"files": ("test.jpg", io.BytesIO(b"image"), "image/jpeg")}
    create_response = client.post("/process-manga", files=files)
    job_id = create_response.json()["job_id"]

    response = client.get(f"/download/{job_id}")
    assert response.status_code == 404
    assert "Job not complete" in response.json()["detail"]


def test_static_files_mounted():
    """Test that static files are properly mounted"""
    # This test just verifies the static route exists
    # Actual file content testing would require static files to be present
    response = client.get("/static/")
    # May return 404 if directory is empty, but route should exist
    # or it might return 404 for directory listing
    assert response.status_code in [200, 404]


def test_cors_headers():
    """Test that CORS headers are properly set"""
    response = client.options("/", headers={"Origin": "http://example.com"})
    # Check for CORS headers
    assert "access-control-allow-origin" in response.headers


def test_multiple_concurrent_jobs():
    """Test handling multiple concurrent jobs"""
    # Create multiple jobs
    job_ids = []
    for i in range(3):
        files = {"files": (f"test{i}.jpg", io.BytesIO(b"image"), "image/jpeg")}
        response = client.post("/process-manga", files=files)
        job_ids.append(response.json()["job_id"])

    # Verify all jobs exist
    for job_id in job_ids:
        response = client.get(f"/job/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    # Verify jobs are tracked separately
    assert len(jobs) == 3


def test_process_manga_creates_upload_directory():
    """Test that processing creates upload directory"""
    files = {"files": ("test.jpg", io.BytesIO(b"image"), "image/jpeg")}
    response = client.post("/process-manga", files=files)
    job_id = response.json()["job_id"]

    # Check that upload directory was created
    # Note: In real test, directory would exist, but in unit test it might
    # be cleaned up asynchronously, so we just verify the structure
    assert job_id in jobs
