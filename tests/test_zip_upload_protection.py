import io
import zipfile
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.database.connection import SessionLocal
from app.auth.models.auth_models import User
from app.auth.services.auth_service import AuthService
from app.projects.models.project_models import Project
from app.projects.services.zip_processor import (
    ZipProcessor,
    ZipUploadTooLargeError,
    ZipBombDetectedError,
    ZipFileCountLimitError
)

client = TestClient(app)

def get_test_user_and_project():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "zip_sec_user").first()
        if not user:
            user = User(
                username="zip_sec_user",
                hashed_password=AuthService.hash_password("zippass123"),
                role="user",
                is_active=True,
                is_verified=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        project = db.query(Project).filter(Project.name == "Zip Sec Test Project", Project.user_id == user.id).first()
        if not project:
            project = Project(name="Zip Sec Test Project", user_id=user.id)
            db.add(project)
            db.commit()
            db.refresh(project)

        token, _, _, _ = AuthService.create_jwt_pair(user.id, user.role)
        return token, project.id
    finally:
        db.close()


def create_zip_with_n_files(n: int) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i in range(n):
            z.writestr(f"module_{i}.py", f"# Python module {i}\ndef f_{i}(): pass\n")
    return buf.getvalue()


def test_zip_upload_exceeding_max_size_returns_413():
    """Verify raw upload size exceeding max limit raises ZipUploadTooLargeError and returns 413."""
    token, proj_id = get_test_user_and_project()

    # Temporarily lower MAX_UPLOAD_SIZE_BYTES to 10KB for rapid testing
    orig_limit = ZipProcessor.MAX_UPLOAD_SIZE_BYTES
    ZipProcessor.MAX_UPLOAD_SIZE_BYTES = 10 * 1024  # 10 KB
    try:
        large_content = b"x" * (15 * 1024)  # 15 KB
        res = client.post(
            f"/projects/{proj_id}/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("large.zip", large_content, "application/zip")}
        )
        assert res.status_code == 413, f"Expected 413, got {res.status_code}: {res.text}"
        assert "exceeds" in res.json()["detail"].lower()
    finally:
        ZipProcessor.MAX_UPLOAD_SIZE_BYTES = orig_limit


def test_zip_archive_exceeding_max_file_count_returns_400():
    """Verify archive containing more than MAX_FILE_COUNT files is rejected with 400."""
    token, proj_id = get_test_user_and_project()

    orig_limit = ZipProcessor.MAX_FILE_COUNT
    ZipProcessor.MAX_FILE_COUNT = 10  # Lower to 10 for rapid testing
    try:
        zip_bytes = create_zip_with_n_files(15)
        res = client.post(
            f"/projects/{proj_id}/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("many_files.zip", zip_bytes, "application/zip")}
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "too many files" in res.json()["detail"].lower() or "exceeds maximum allowed limit" in res.json()["detail"].lower()
    finally:
        ZipProcessor.MAX_FILE_COUNT = orig_limit


def test_zip_bomb_uncompressed_size_exceeded_returns_400():
    """Verify zip archive exceeding uncompressed size limit is rejected with 400."""
    token, proj_id = get_test_user_and_project()

    orig_limit = ZipProcessor.MAX_TOTAL_EXTRACTED_BYTES
    ZipProcessor.MAX_TOTAL_EXTRACTED_BYTES = 1000  # 1000 bytes
    try:
        # Create zip with 5000 bytes uncompressed
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("big.py", "x" * 5000)
        zip_bytes = buf.getvalue()

        res = client.post(
            f"/projects/{proj_id}/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("bomb.zip", zip_bytes, "application/zip")}
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "exceeds maximum allowed extraction limit" in res.json()["detail"].lower() or "bomb" in res.json()["detail"].lower()
    finally:
        ZipProcessor.MAX_TOTAL_EXTRACTED_BYTES = orig_limit


def test_zip_bomb_extreme_compression_ratio_returns_400():
    """Verify zip archive with abnormal compression ratio (>100:1) is rejected with 400."""
    token, proj_id = get_test_user_and_project()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Repeating zeroes compresses extremely well (~1000:1 ratio)
        z.writestr("zeroes.py", "0" * 200000)
    zip_bytes = buf.getvalue()

    # Verify high compression ratio
    ratio = 200000 / len(zip_bytes)
    assert ratio > ZipProcessor.MAX_COMPRESSION_RATIO

    res = client.post(
        f"/projects/{proj_id}/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("bomb_ratio.zip", zip_bytes, "application/zip")}
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    assert "zip bomb" in res.json()["detail"].lower()


def test_valid_zip_upload_succeeds():
    """Verify normal valid zip archive processes successfully."""
    token, proj_id = get_test_user_and_project()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("main.py", "def hello(): return 'world'\n")
        z.writestr("Engine.java", "public class Engine {}\n")
    zip_bytes = buf.getvalue()

    res = client.post(
        f"/projects/{proj_id}/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("valid.zip", zip_bytes, "application/zip")}
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data["source_type"] == "zip"
    assert data["status"] == "completed"
