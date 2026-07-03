import io
import zipfile
from typing import List
from app.projects.models.project_models import ProjectVersionFile

class SnapshotService:
    @staticmethod
    def create_zip_archive(files: List[ProjectVersionFile]) -> bytes:
        """
        Creates a raw ZIP archive in memory containing all the version files.
        """
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                # Store the file in the zip under its original path/filename
                content = f.content or ""
                zf.writestr(f.filename, content)
        return zip_buffer.getvalue()
