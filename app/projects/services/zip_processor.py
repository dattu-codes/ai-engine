import io
import os
import zipfile
import hashlib
from typing import List, Dict, Any

class ZipUploadTooLargeError(ValueError):
    """Raised when the raw uploaded ZIP archive exceeds the maximum upload size limit."""
    pass

class ZipBombDetectedError(ValueError):
    """Raised when an uncompressed size or compression ratio indicates a zip bomb."""
    pass

class ZipFileCountLimitError(ValueError):
    """Raised when a ZIP archive contains more files than the allowed limit."""
    pass

class ZipProcessor:
    MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024      # 25 MB
    MAX_FILE_COUNT = 500                          # 500 files
    MAX_TOTAL_EXTRACTED_BYTES = 100 * 1024 * 1024 # 100 MB
    MAX_COMPRESSION_RATIO = 100                   # 100:1 ratio limit

    IGNORED_DIRS = {
        ".git", "venv", "node_modules", "__pycache__", 
        ".idea", ".vscode", "dist", "build"
    }

    SUPPORTED_EXTENSIONS = {
        ".py": "Python",
        ".java": "Java",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".go": "Go"
    }

    @classmethod
    def process_zip(cls, zip_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Processes a raw ZIP archive, extracting file details for supported files.
        Enforces upload size limit, file count limit, and zip-bomb decompression protection.
        """
        if len(zip_bytes) > cls.MAX_UPLOAD_SIZE_BYTES:
            raise ZipUploadTooLargeError(
                f"Uploaded ZIP size ({len(zip_bytes)} bytes) exceeds maximum allowed limit of {cls.MAX_UPLOAD_SIZE_BYTES} bytes (25MB)."
            )

        extracted_files = []

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                members = z.infolist()
                non_dir_members = [m for m in members if not m.is_dir()]

                # 1. Enforce max file count
                if len(non_dir_members) > cls.MAX_FILE_COUNT:
                    raise ZipFileCountLimitError(
                        f"ZIP archive contains {len(non_dir_members)} files, which exceeds maximum allowed limit of {cls.MAX_FILE_COUNT} files."
                    )

                # 2. Enforce declared uncompressed size limit
                total_declared_uncompressed = sum(m.file_size for m in non_dir_members)
                if total_declared_uncompressed > cls.MAX_TOTAL_EXTRACTED_BYTES:
                    raise ZipBombDetectedError(
                        f"Total uncompressed size ({total_declared_uncompressed} bytes) exceeds maximum allowed extraction limit of {cls.MAX_TOTAL_EXTRACTED_BYTES} bytes (100MB)."
                    )

                # 3. Enforce compression ratio threshold (zip bomb guard)
                if len(zip_bytes) > 0 and (total_declared_uncompressed / len(zip_bytes)) > cls.MAX_COMPRESSION_RATIO:
                    raise ZipBombDetectedError("Potential ZIP bomb detected: compression ratio exceeds 100:1 safe threshold.")

                running_extracted_bytes = 0

                for member in non_dir_members:
                    # Path traversal (Zip Slip) security protection
                    raw_name = member.filename.replace("\\", "/")
                    norm_path = os.path.normpath(raw_name).replace("\\", "/")
                    if (
                        norm_path.startswith("..") or 
                        norm_path.startswith("/") or 
                        "://" in raw_name or
                        ".." in norm_path.split("/")
                    ):
                        # Block malicious archive paths attempting directory traversal
                        continue

                    # Split path components to check if any part is ignored
                    path_parts = norm_path.split("/")
                    if any(part in cls.IGNORED_DIRS for part in path_parts):
                        continue

                    # Extract file extension and verify if supported
                    filename = norm_path
                    dot_idx = filename.rfind(".")
                    if dot_idx == -1:
                        continue
                    
                    extension = filename[dot_idx:].lower()
                    is_code = extension in cls.SUPPORTED_EXTENSIONS
                    is_config = filename.lower().endswith(("requirements.txt", "package.json", "pyproject.toml", "pom.xml", "build.gradle"))
                    
                    if not is_code and not is_config:
                        continue

                    if filename.lower().endswith("requirements.txt"):
                        language = "Requirements"
                    elif filename.lower().endswith("package.json"):
                        language = "JSON"
                    elif filename.lower().endswith("pyproject.toml"):
                        language = "TOML"
                    elif filename.lower().endswith("pom.xml"):
                        language = "XML"
                    elif filename.lower().endswith("build.gradle"):
                        language = "Gradle"
                    else:
                        language = cls.SUPPORTED_EXTENSIONS[extension]
                    
                    # Read file contents and verify running extracted size
                    content_bytes = z.read(member.filename)
                    running_extracted_bytes += len(content_bytes)
                    if running_extracted_bytes > cls.MAX_TOTAL_EXTRACTED_BYTES:
                        raise ZipBombDetectedError(
                            f"Total extracted size exceeded maximum safe limit of {cls.MAX_TOTAL_EXTRACTED_BYTES} bytes."
                        )

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
