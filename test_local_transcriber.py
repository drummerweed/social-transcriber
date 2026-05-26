import unittest
from fastapi.testclient import TestClient
import os
import shutil

# Set environment variable if needed before importing app
from main import app

class TestLocalTranscriber(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Create a mock valid file for testing inside /home/admin
        self.test_file_dir = "/home/admin/Downloads"
        os.makedirs(self.test_file_dir, exist_ok=True)
        self.test_file_path = os.path.join(self.test_file_dir, "test_audio_mock.mp3")
        
        # Write dummy content (>1000 bytes as required by transcriber)
        with open(self.test_file_path, "wb") as f:
            f.write(b"0" * 1024)

    def tearDown(self):
        # Clean up mock file
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def test_local_page_get(self):
        """Test that the local transcriber page loads successfully."""
        response = self.client.get("/local")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Local File Transcriber", response.text)

    def test_path_traversal_blocked(self):
        """Test that path traversal outside of /home/admin is forbidden (403)."""
        response = self.client.post("/api/transcribe-local", data={
            "file_path": "/etc/passwd"
        })
        self.assertEqual(response.status_code, 403)
        self.assertIn("Access Denied", response.json().get("error", ""))

    def test_nonexistent_file_blocked(self):
        """Test that a non-existent file path returns 400."""
        response = self.client.post("/api/transcribe-local", data={
            "file_path": "/home/admin/non_existent_file_xyz.mp3"
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("File not found", response.json().get("error", ""))

    def test_unsupported_extension_blocked(self):
        """Test that an unsupported file extension returns 400."""
        invalid_file = os.path.join(self.test_file_dir, "test_invalid.txt")
        with open(invalid_file, "w") as f:
            f.write("dummy text")

        try:
            response = self.client.post("/api/transcribe-local", data={
                "file_path": invalid_file
            })
            self.assertEqual(response.status_code, 400)
            self.assertIn("Unsupported file extension", response.json().get("error", ""))
        finally:
            if os.path.exists(invalid_file):
                os.remove(invalid_file)

    def test_valid_file_path_queued(self):
        """Test that a valid file path is successfully accepted and queued (200)."""
        # Since Whisper is imported/loaded, this might run background task
        # We just check the response of the API endpoint queueing the job
        response = self.client.post("/api/transcribe-local", data={
            "file_path": self.test_file_path
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "processing")
        self.assertIsNotNone(response.json().get("req_id"))

if __name__ == "__main__":
    unittest.main()
