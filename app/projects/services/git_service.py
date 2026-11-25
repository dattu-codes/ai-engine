import re
import os
import time
import shutil
import stat
import subprocess
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
import httpx
from app.projects.services.zip_processor import ZipProcessor

logger = logging.getLogger(__name__)

GITHUB_URL_PATTERN = re.compile(
    r'^https?://(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$'
)

_repo_accessibility_cache: Dict[str, Tuple[bool, float]] = {}
CACHE_TTL_SECONDS = 300
GITHUB_USER_AGENT = "AI-Engine/1.0"

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
    def _get_git_base_cmd() -> List[str]:
        return ["git", "-c", "credential.helper="]

    @classmethod
    def _get_github_headers(cls) -> Dict[str, str]:
        """
        Returns standard headers for GitHub REST API requests.
        If GITHUB_API_TOKEN environment variable is set, includes Authorization header.
        Never logs or exposes the token in error messages.
        """
        headers = {
            "User-Agent": GITHUB_USER_AGENT,
            "Accept": "application/vnd.github.v3+json"
        }
        token = os.environ.get("GITHUB_API_TOKEN")
        if token and token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
        return headers

    @staticmethod
    def _get_rate_limit_message(resp: httpx.Response) -> str:
        """
        Extracts X-RateLimit-Reset timestamp if present and returns formatted rate limit message.
        Example: 'GitHub rate limit reached, try again at 18:45'
        """
        reset_header = None
        try:
            raw_val = resp.headers.get("X-RateLimit-Reset") or resp.headers.get("x-ratelimit-reset")
            if isinstance(raw_val, (str, int, float)) and str(raw_val).isdigit():
                reset_header = raw_val
        except Exception:
            pass

        if reset_header is not None:
            try:
                reset_ts = int(reset_header)
                # GitHub's X-RateLimit-Reset is in UTC epoch seconds
                reset_time = datetime.fromtimestamp(reset_ts, tz=timezone.utc).strftime("%H:%M")
                return f"GitHub rate limit reached, try again at {reset_time}"
            except Exception:
                pass
        return "GitHub rate limit reached, try again later"

    @classmethod
    def check_public_repo(cls, repo_url: str) -> Dict[str, Any]:
        """
        Validates the GitHub URL and checks repository accessibility using GitHub REST API.
        Distinguishes 404, private repository, rate limits, and network errors.
        """
        is_valid, owner, repo = cls.validate_url(repo_url)
        if not is_valid:
            raise ValueError("Invalid GitHub Repository URL format.")

        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = cls._get_github_headers()

        try:
            resp = httpx.get(
                api_url,
                headers=headers,
                timeout=10.0,
                verify=True,
                follow_redirects=True
            )
        except httpx.TimeoutException as e:
            logger.warning("GitHub API timeout checking repository %s: %s", repo_url, e)
            raise ValueError("GitHub request timed out. Please try again later.")
        except (httpx.NetworkError, httpx.RequestError) as e:
            logger.warning("GitHub API network error checking repository %s: %s", repo_url, e)
            raise ValueError("GitHub network failure. Unable to reach GitHub API.")

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception as e:
                logger.warning("Failed to parse GitHub API JSON response for %s: %s", repo_url, e)
                raise ValueError("Unexpected response from GitHub API.")

            if data.get("private") is True:
                logger.warning("Repository %s is private; rejected for public ingestion.", repo_url)
                raise ValueError("Repository is private. Only public repositories are supported.")

            return data

        elif resp.status_code == 404:
            logger.warning("Repository %s not found on GitHub (HTTP 404).", repo_url)
            raise ValueError("Repository does not exist on GitHub.")

        elif resp.status_code in (403, 429):
            msg = cls._get_rate_limit_message(resp)
            logger.warning("GitHub API rate limit encountered (%s) for %s: %s", resp.status_code, repo_url, msg)
            raise ValueError(msg)

        else:
            logger.warning("GitHub API error (%s) checking %s: %s", resp.status_code, repo_url, resp.text)
            raise ValueError(f"GitHub API error (HTTP {resp.status_code}).")

    @classmethod
    def is_public_repo(cls, repo_url: str) -> bool:
        """
        Checks if the repository is public and accessible.
        Caches result for CACHE_TTL_SECONDS to avoid redundant remote roundtrips.
        """
        clean_url = repo_url.strip()
        now = time.time()
        if clean_url in _repo_accessibility_cache:
            is_pub, cached_at = _repo_accessibility_cache[clean_url]
            if now - cached_at < CACHE_TTL_SECONDS:
                return is_pub

        try:
            data = cls.check_public_repo(clean_url)
            is_public = (data.get("private") is False)
            _repo_accessibility_cache[clean_url] = (is_public, now)
            return is_public
        except Exception:
            _repo_accessibility_cache[clean_url] = (False, now)
            return False

    @classmethod
    def fetch_code_zipball(cls, owner: str, repo: str, branch: str) -> List[Dict[str, Any]]:
        """
        Downloads the repository source archive (zipball) directly from GitHub API and
        extracts supported code files enforcing all security and zip-slip limits.
        """
        zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{branch}"
        headers = cls._get_github_headers()

        try:
            resp = httpx.get(
                zip_url,
                headers=headers,
                timeout=30.0,
                verify=True,
                follow_redirects=True
            )
        except httpx.TimeoutException as e:
            logger.warning("Timeout downloading zipball for %s/%s: %s", owner, repo, e)
            raise ValueError("GitHub zipball download timed out. Please try again.")
        except (httpx.NetworkError, httpx.RequestError) as e:
            logger.warning("Network error downloading zipball for %s/%s: %s", owner, repo, e)
            raise ValueError("GitHub network failure while downloading repository.")

        if resp.status_code == 404:
            logger.warning("Zipball not found for %s/%s branch %s (HTTP 404)", owner, repo, branch)
            raise ValueError("Repository branch or archive does not exist on GitHub.")
        elif resp.status_code in (403, 429):
            msg = cls._get_rate_limit_message(resp)
            logger.warning("GitHub API rate limited downloading zipball for %s/%s (HTTP %s): %s", owner, repo, resp.status_code, msg)
            raise ValueError(msg)
        elif resp.status_code != 200:
            logger.warning("Failed to download zipball for %s/%s (HTTP %s): %s", owner, repo, resp.status_code, resp.text)
            raise ValueError(f"Failed to download repository archive (HTTP {resp.status_code}).")

        if len(resp.content) > ZipProcessor.MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(
                f"Repository archive size ({len(resp.content)} bytes) exceeds maximum limit of {ZipProcessor.MAX_UPLOAD_SIZE_BYTES} bytes."
            )

        return ZipProcessor.process_zip(resp.content, strip_root_dir=True)

    @classmethod
    def fetch_commit_metadata(cls, owner: str, repo: str, branch: str) -> Tuple[str, str]:
        """
        Retrieves the latest commit SHA and message for the branch via GitHub Commits API.
        """
        commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
        headers = cls._get_github_headers()
        try:
            resp = httpx.get(
                commit_url,
                headers=headers,
                timeout=10.0,
                verify=True,
                follow_redirects=True
            )
            if resp.status_code == 200:
                data = resp.json()
                sha = data.get("sha", "")
                msg = data.get("commit", {}).get("message", "Imported from GitHub")
                return sha, msg
            elif resp.status_code in (403, 429):
                rate_msg = cls._get_rate_limit_message(resp)
                logger.warning("GitHub API rate limit encountered fetching commit metadata for %s/%s: %s", owner, repo, rate_msg)
            else:
                logger.warning("GitHub commits endpoint returned HTTP %s for %s/%s", resp.status_code, owner, repo)
        except Exception as e:
            logger.warning("Failed to fetch commit metadata for %s/%s: %s", owner, repo, e)

        return "", "Imported from GitHub"

    @classmethod
    def get_remote_head_sha(cls, repo_url: str, branch: Optional[str] = None) -> Optional[str]:
        """
        Retrieves the latest commit SHA of HEAD (or specific branch) from remote repository.
        Attempts GitHub API first (GET /repos/{owner}/{name}/commits/{branch}); falls back to git ls-remote only when git exists.
        """
        is_valid, owner, repo = cls.validate_url(repo_url)
        if is_valid and owner and repo:
            target_branch = branch
            if not target_branch:
                try:
                    repo_data = cls.check_public_repo(repo_url)
                    target_branch = repo_data.get("default_branch") or "main"
                except Exception as e:
                    logger.warning("Could not determine default branch for %s: %s", repo_url, e)
                    target_branch = "HEAD"

            commit_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{target_branch}"
            headers = cls._get_github_headers()
            try:
                resp = httpx.get(
                    commit_url,
                    headers=headers,
                    timeout=10.0,
                    verify=True,
                    follow_redirects=True
                )
                if resp.status_code == 200:
                    data = resp.json()
                    sha = data.get("sha")
                    if sha:
                        return sha
                elif resp.status_code == 404:
                    logger.warning("Commit endpoint returned 404 for %s/%s branch %s", owner, repo, target_branch)
                elif resp.status_code in (403, 429):
                    rate_msg = cls._get_rate_limit_message(resp)
                    logger.warning("GitHub rate limit encountered fetching commit SHA for %s/%s (HTTP %s): %s", owner, repo, resp.status_code, rate_msg)
                else:
                    logger.warning("GitHub commits endpoint returned HTTP %s for %s/%s", resp.status_code, owner, repo)
            except httpx.TimeoutException as e:
                logger.warning("GitHub API timeout checking commit SHA for %s: %s", repo_url, e)
            except (httpx.NetworkError, httpx.RequestError) as e:
                logger.warning("GitHub API network error checking commit SHA for %s: %s", repo_url, e)
            except Exception as e:
                logger.warning("Could not fetch remote HEAD SHA via API for %s: %s", repo_url, e)

        # Fallback to git binary only if present
        if shutil.which("git"):
            try:
                env = os.environ.copy()
                env["GIT_TERMINAL_PROMPT"] = "0"
                env["GCM_INTERACTIVE"] = "never"
                target_ref = branch if branch else "HEAD"
                cmd = cls._get_git_base_cmd() + ["ls-remote", repo_url.strip(), target_ref]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                    env=env
                )
                if result.returncode == 0 and result.stdout:
                    parts = result.stdout.strip().split()
                    if parts:
                        return parts[0]
            except Exception as ge:
                logger.warning("git ls-remote fallback failed for %s: %s", repo_url, ge)
        return None

    @classmethod
    def clone_repository(cls, repo_url: str, dest_dir: str) -> bool:
        """
        Clones the repository at repo_url into dest_dir with --depth 1.
        """
        try:
            os.makedirs(dest_dir, exist_ok=True)
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            env["GCM_INTERACTIVE"] = "never"
            cmd = cls._get_git_base_cmd() + ["clone", "--depth", "1", repo_url.strip(), dest_dir]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
                env=env
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
        Validates, downloads/clones, parses, and returns repository metadata and files.
        Uses GitHub API & zipball download primarily, falling back to git clone if git binary is present.
        Returns (metadata, files).
        """
        is_valid, owner, repo = cls.validate_url(repo_url)
        if not is_valid:
            raise ValueError("Invalid GitHub Repository URL format.")

        def _attempt_git_clone_fallback(default_br: str) -> Optional[Tuple[Dict[str, str], List[Dict[str, Any]]]]:
            if not shutil.which("git"):
                return None
            logger.info("Attempting git CLI clone fallback for %s", repo_url)
            base_temp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "temp_clones"))
            os.makedirs(base_temp_path, exist_ok=True)
            dest_dir = os.path.join(base_temp_path, str(uuid.uuid4()))
            try:
                success = cls.clone_repository(repo_url, dest_dir)
                if success:
                    metadata = cls.get_repo_metadata(dest_dir)
                    metadata["repo_url"] = repo_url
                    metadata["repo_name"] = repo
                    metadata["repo_owner"] = owner
                    if not metadata.get("default_branch"):
                        metadata["default_branch"] = default_br
                    if not metadata.get("current_branch"):
                        metadata["current_branch"] = default_br
                    files = cls.parse_files(dest_dir)
                    return metadata, files
                else:
                    logger.warning("Git CLI clone command failed for %s", repo_url)
            except Exception as ge:
                logger.warning("Exception during git CLI clone fallback for %s: %s", repo_url, ge)
            finally:
                if os.path.exists(dest_dir):
                    shutil.rmtree(dest_dir, onerror=remove_readonly)
            return None

        # 1. Check repository accessibility via GitHub REST API (distinguishes 404, private, rate limit, network)
        default_branch = "main"
        try:
            repo_data = cls.check_public_repo(repo_url)
            default_branch = repo_data.get("default_branch") or "main"
        except ValueError as e:
            if "GitHub rate limit" in str(e):
                logger.warning("GitHub API rate limit hit checking repo %s: %s", repo_url, e)
                fallback_res = _attempt_git_clone_fallback(default_branch)
                if fallback_res:
                    return fallback_res
                # Only show rate-limit message if both paths fail
                raise e
            else:
                raise e

        # 2. Attempt fetching code via GitHub zipball archive
        zip_error: Optional[Exception] = None
        try:
            files = cls.fetch_code_zipball(owner, repo, default_branch)
            sha, msg = cls.fetch_commit_metadata(owner, repo, default_branch)
            metadata = {
                "repo_url": repo_url,
                "repo_name": repo,
                "repo_owner": owner,
                "default_branch": default_branch,
                "current_branch": default_branch,
                "last_commit_sha": sha,
                "last_commit_message": msg
            }
            return metadata, files
        except Exception as e:
            zip_error = e
            logger.warning("Zipball download/extraction failed for %s/%s: %s", owner, repo, e)

        # 3. Fallback to git binary if available on system
        fallback_res = _attempt_git_clone_fallback(default_branch)
        if fallback_res:
            return fallback_res

        # 4. If zipball failed and git fallback unavailable/failed, raise the specific zip_error
        if isinstance(zip_error, ValueError):
            raise zip_error
        elif zip_error is not None:
            raise ValueError(f"Failed to fetch repository: {zip_error}")
        else:
            raise ValueError("Failed to clone or fetch repository.")
