import io
import zipfile
import hashlib
from typing import List, Dict, Any

class ZipProcessor:
    IGNORED_DIRS = {
        ".git", "venv", "node_modules", "__pycache__", 
        ".idea", ".vscode", "dist", "build"
    }

    SUPPORTED_EXTENSIONS = {
        ".py": "Python",
        ".java": "Java",
        ".js": "JavaScript",
        ".ts": "TypeScript"
    }

    @classmethod
    def process_zip(cls, zip_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Processes a raw ZIP archive, extracting file details for supported files.
        Filters out directories and matches against IGNORED_DIRS.
        """
        extracted_files = []

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                for member in z.infolist():
                    # Skip directories
                    if member.is_dir():
                        continue

                    # Split path components to check if any part is ignored
                    path_parts = member.filename.replace("\\", "/").split("/")
                    if any(part in cls.IGNORED_DIRS for part in path_parts):
                        continue

                    # Extract file extension and verify if supported
                    filename = member.filename
                    dot_idx = filename.rfind(".")
                    if dot_idx == -1:
                        continue
                    
                    extension = filename[dot_idx:].lower()
                    if extension not in cls.SUPPORTED_EXTENSIONS:
                        continue

                    language = cls.SUPPORTED_EXTENSIONS[extension]
                    
                    # Read file contents and generate hash
                    content_bytes = z.read(member.filename)
                    file_size = len(content_bytes)
                    file_hash = hashlib.sha256(content_bytes).hexdigest()
                    
                    try:
                        content_str = content_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        content_str = content_bytes.decode("utf-8", errors="replace")

                    extracted_files.append({
                        "filename": filename,
                        "extension": extension,
                        "size": file_size,
                        "language": language,
                        "hash": file_hash,
                        "content": content_str
                    })
        except zipfile.BadZipFile:
            raise ValueError("Invalid ZIP file payload provided.")

        return extracted_files
