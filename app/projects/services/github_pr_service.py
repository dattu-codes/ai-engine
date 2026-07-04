import json
import urllib.request
import urllib.error
import os
from typing import Dict, List, Any, Tuple, Optional

class GitHubPRService:
    @staticmethod
    def _make_github_request(url: str, token: Optional[str] = None) -> Tuple[int, Any]:
        """Helper to make GitHub API calls using urllib."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AIEngine-PR-Service"
        }
        if token:
            headers["Authorization"] = f"token {token}"
        elif os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = f"token {os.getenv('GITHUB_TOKEN')}"
            
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.status
                body = response.read().decode("utf-8")
                return status, json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8")
            try:
                err_json = json.loads(body)
            except Exception:
                err_json = {"message": body}
            return status, err_json
        except Exception as e:
            return 500, {"message": str(e)}

    @classmethod
    def fetch_pr_details(
        cls, 
        owner: str, 
        repo: str, 
        pr_number: int, 
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetches PR details from GitHub REST API or returns simulated offline mock data.
        """
        is_mock = (
            owner.lower() in ("mock-owner", "test-owner", "example-owner") or
            repo.lower() in ("mock-repo", "test-repo", "example-repo") or
            int(pr_number) == 999  # Special test case PR
        )
        
        if not is_mock:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            status, data = cls._make_github_request(url, api_key)
            if status == 200:
                # Successfully loaded live GitHub PR details
                return {
                    "title": data.get("title", f"Pull Request #{pr_number}"),
                    "author": data.get("user", {}).get("login", "anonymous"),
                    "base_branch": data.get("base", {}).get("ref", "main"),
                    "head_branch": data.get("head", {}).get("ref", "feature"),
                    "status": data.get("state", "open"),
                    "files_changed": data.get("changed_files", 0),
                    "additions": data.get("additions", 0),
                    "deletions": data.get("deletions", 0),
                    "commits": data.get("commits", 0),
                    "last_commit_sha": data.get("head", {}).get("sha", "")
                }
                
        # OFFLINE SIMULATOR FALLBACK
        # Standard simulated PR scenarios
        if int(pr_number) == 15:
            return {
                "title": "Resolve session vulnerability in auth.py",
                "author": "security_engineer",
                "base_branch": "main",
                "head_branch": "feature/fix-auth",
                "status": "open",
                "files_changed": 1,
                "additions": 2,
                "deletions": 1,
                "commits": 1,
                "last_commit_sha": "sha_pr_15_head_commit_abc123"
            }
        elif int(pr_number) == 16:
            return {
                "title": "Refactor sum algorithms in utils.py",
                "author": "math_wizard",
                "base_branch": "main",
                "head_branch": "feature/optimize-math",
                "status": "open",
                "files_changed": 1,
                "additions": 3,
                "deletions": 1,
                "commits": 2,
                "last_commit_sha": "sha_pr_16_head_commit_def456"
            }
        else:
            return {
                "title": f"Simulated Pull Request #{pr_number}",
                "author": "mock_author",
                "base_branch": "main",
                "head_branch": f"feature/pr-{pr_number}",
                "status": "open",
                "files_changed": 1,
                "additions": 5,
                "deletions": 2,
                "commits": 1,
                "last_commit_sha": f"sha_pr_{pr_number}_head_commit"
            }

    @classmethod
    def fetch_pr_files(
        cls, 
        owner: str, 
        repo: str, 
        pr_number: int, 
        api_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches PR files and patches from GitHub REST API or returns simulated offline mock data.
        """
        is_mock = (
            owner.lower() in ("mock-owner", "test-owner", "example-owner") or
            repo.lower() in ("mock-repo", "test-repo", "example-repo") or
            int(pr_number) == 999
        )
        
        if not is_mock:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
            status, data = cls._make_github_request(url, api_key)
            if status == 200 and isinstance(data, list):
                files_list = []
                for f in data:
                    files_list.append({
                        "filename": f.get("filename", ""),
                        "additions": f.get("additions", 0),
                        "deletions": f.get("deletions", 0),
                        "status": f.get("status", "modified"),
                        "patch": f.get("patch", ""),
                        "raw_url": f.get("raw_url", "")
                    })
                return files_list
                
        # OFFLINE SIMULATOR FALLBACK
        if int(pr_number) == 15:
            return [
                {
                    "filename": "app/auth.py",
                    "additions": 2,
                    "deletions": 1,
                    "status": "modified",
                    "patch": '@@ -11,4 +11,5 @@\n def check_session(token):\n-    eval("arbitrary_string")\n+    # Secured session check using secure lookup logic\n+    validate_token_structure(token)\n+    pass',
                    "content": 'def check_session(token):\n    eval(token)\n    pass\n' + '\n' * 15
                }
            ]
        elif int(pr_number) == 16:
            return [
                {
                    "filename": "app/utils.py",
                    "additions": 3,
                    "deletions": 1,
                    "status": "modified",
                    "patch": '@@ -1,3 +1,5 @@\n def add_nums(a, b):\n-    return a + b\n+    # Optimized addition utility\n+    print("Calculating sum")\n+    return a + b',
                    "content": 'def add_nums(a, b):\n    # Optimized addition utility\n    print("Calculating sum")\n    return a + b\n'
                }
            ]
        else:
            return [
                {
                    "filename": "app/main.py",
                    "additions": 5,
                    "deletions": 2,
                    "status": "modified",
                    "patch": '@@ -10,3 +10,6 @@\n def main():\n-    pass\n+    # Simulated update\n+    print("Main process running")\n+    TODO: add logging\n+    pass',
                    "content": 'def main():\n    # Simulated update\n    print("Main process running")\n    TODO: add logging\n    pass\n'
                }
            ]
