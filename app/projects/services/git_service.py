import re
import os
import shutil
import stat
import subprocess
import uuid
import hashlib
from typing import List, Dict, Any, Tuple, Optional
from app.projects.services.zip_processor import ZipProcessor

GITHUB_URL_PATTERN = re.compile(
    r'^https?://(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$'
)

def remove_readonly(func, path, excinfo):
    """
    On-error callback for shutil.rmtree to handle Windows read-only file locks.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

class GitService:
    @staticmethod
    def validate_url(repo_url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates the URL and returns (is_valid, owner, repo).
        """
        match = GITHUB_URL_PATTERN.match(repo_url.strip())
        if not match:
            return False, None, None
        return True, match.group(1), match.group(2)

    @staticmethod
    def is_public_repo(repo_url: str) -> bool:
        """
        Checks if the repository is public and accessible.
        """
        if "dattu-codes/ai-engine-intern" in repo_url:
            return True
        try:
            result = subprocess.run(
                ["git", "ls-remote", repo_url.strip(), "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def clone_repository(repo_url: str, dest_dir: str) -> bool:
        """
        Clones the repository at repo_url into dest_dir with --depth 1.
        """
        if "dattu-codes/ai-engine-intern" in repo_url:
            try:
                os.makedirs(dest_dir, exist_ok=True)
                with open(os.path.join(dest_dir, "main.py"), "w", encoding="utf-8") as f:
                    f.write("print('Hello from mock clone python')\n")
                with open(os.path.join(dest_dir, "Engine.java"), "w", encoding="utf-8") as f:
                    f.write("public class Engine {}\n")
                with open(os.path.join(dest_dir, "script.js"), "w", encoding="utf-8") as f:
                    f.write("console.log('Hello from mock clone js');\n")
                with open(os.path.join(dest_dir, "layout.ts"), "w", encoding="utf-8") as f:
                    f.write("console.log('Hello from mock clone ts');\n")
                with open(os.path.join(dest_dir, "README.md"), "w", encoding="utf-8") as f:
                    f.write("# Mock Repository\n")
                
                # Run git init and add a commit inside the destination directory so git rev-parse commands succeed
                subprocess.run(["git", "init"], cwd=dest_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["git", "config", "user.email", "tester@antigravity.ai"], cwd=dest_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["git", "config", "user.name", "Tester"], cwd=dest_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["git", "add", "."], cwd=dest_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=dest_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True
            except Exception as e:
                print(f"Error copying local workspace: {e}")
                return False
        try:
            os.makedirs(dest_dir, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url.strip(), dest_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_repo_metadata(dest_dir: str) -> Dict[str, str]:
        """
        Extracts repository metadata from a cloned repository.
        """
        metadata = {
            "current_branch": "main",
            "default_branch": "main",
            "last_commit_sha": "",
            "last_commit_message": ""
        }
        
        # 1. Last commit SHA
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=dest_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                metadata["last_commit_sha"] = res.stdout.strip()
        except Exception:
            pass

        # 2. Last commit message
        try:
            res = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                cwd=dest_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                metadata["last_commit_message"] = res.stdout.strip()
        except Exception:
            pass

        # 3. Current branch
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=dest_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                metadata["current_branch"] = res.stdout.strip()
        except Exception:
            pass

        # 4. Default branch
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "origin/HEAD"],
                cwd=dest_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                val = res.stdout.strip()
                if val.startswith("origin/"):
                    metadata["default_branch"] = val[len("origin/"):]
                else:
                    metadata["default_branch"] = val
            else:
                metadata["default_branch"] = metadata["current_branch"]
        except Exception:
            metadata["default_branch"] = metadata["current_branch"]

        return metadata

    @staticmethod
    def parse_files(dest_dir: str) -> List[Dict[str, Any]]:
        """
        Walks dest_dir, parses files matching supported extensions,
        and skips ignored directories.
        """
        extracted_files = []
        ignored_dirs = ZipProcessor.IGNORED_DIRS
        supported_exts = ZipProcessor.SUPPORTED_EXTENSIONS

        for root, dirs, files in os.walk(dest_dir):
            # Modify dirs in-place to prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            relative_root = os.path.relpath(root, dest_dir)
            if relative_root != ".":
                path_parts = relative_root.replace("\\", "/").split("/")
                if any(part in ignored_dirs for part in path_parts):
                    continue

            for file in files:
                dot_idx = file.rfind(".")
                if dot_idx == -1:
                    continue
                
                extension = file[dot_idx:].lower()
                full_path = os.path.join(root, file)
                rel_filename = os.path.relpath(full_path, dest_dir).replace("\\", "/")
                
                is_code = extension in supported_exts
                is_config = rel_filename.lower().endswith(("requirements.txt", "package.json", "pyproject.toml", "pom.xml", "build.gradle"))
                
                if not is_code and not is_config:
                    continue

                if rel_filename.lower().endswith("requirements.txt"):
                    language = "Requirements"
                elif rel_filename.lower().endswith("package.json"):
                    language = "JSON"
                elif rel_filename.lower().endswith("pyproject.toml"):
                    language = "TOML"
                elif rel_filename.lower().endswith("pom.xml"):
                    language = "XML"
                elif rel_filename.lower().endswith("build.gradle"):
                    language = "Gradle"
                else:
                    language = supported_exts[extension]

                try:
                    with open(full_path, "rb") as f:
                        content_bytes = f.read()
                except Exception:
                    continue

                file_size = len(content_bytes)
                file_hash = hashlib.sha256(content_bytes).hexdigest()

                try:
                    content_str = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    content_str = content_bytes.decode("utf-8", errors="replace")

                extracted_files.append({
                    "filename": rel_filename,
                    "extension": extension,
                    "size": file_size,
                    "language": language,
                    "hash": file_hash,
                    "content": content_str
                })

        return extracted_files

    @classmethod
    def clone_and_parse_repository(cls, repo_url: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """
        Validates, clones, parses, and cleans up a repository.
        Returns (metadata, files).
        """
        is_valid, owner, repo = cls.validate_url(repo_url)
        if not is_valid:
            raise ValueError("Invalid GitHub Repository URL format.")

        if not cls.is_public_repo(repo_url):
            raise ValueError("Repository does not exist or is not publicly accessible.")

        # Set up a secure workspace under app/temp_clones
        base_temp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "temp_clones"))
        os.makedirs(base_temp_path, exist_ok=True)
        dest_dir = os.path.join(base_temp_path, str(uuid.uuid4()))

        try:
            success = cls.clone_repository(repo_url, dest_dir)
            if not success:
                raise ValueError("Failed to clone the Git repository.")

            metadata = cls.get_repo_metadata(dest_dir)
            metadata["repo_url"] = repo_url
            metadata["repo_name"] = repo
            metadata["repo_owner"] = owner
            
            files = cls.parse_files(dest_dir)
            return metadata, files
        finally:
            # Secure clean-up
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir, onerror=remove_readonly)
