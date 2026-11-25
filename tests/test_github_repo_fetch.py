import io
import zipfile
from unittest.mock import patch, MagicMock
import pytest
import httpx
from app.projects.services.git_service import GitService, GITHUB_USER_AGENT


def _make_sample_zip(prefix: str = "testowner-testrepo-1234567") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{prefix}/main.py", "def add(a, b):\n    return a + b\n")
    return buf.getvalue()


def test_public_repo_ok():
    """Verify successful public repo fetching via GitHub REST API and zipball download."""
    repo_url = "https://github.com/testowner/testrepo"
    sample_zip = _make_sample_zip()

    def mock_httpx_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "commits" in url:
            resp.json.return_value = {
                "sha": "1234567890abcdef1234567890abcdef12345678",
                "commit": {"message": "Initial commit"}
            }
        elif "zipball" in url:
            resp.content = sample_zip
        else:
            resp.json.return_value = {
                "private": False,
                "default_branch": "main",
                "name": "testrepo"
            }
        return resp

    with patch("httpx.get", side_effect=mock_httpx_get):
        metadata, files = GitService.clone_and_parse_repository(repo_url)

    assert metadata["repo_owner"] == "testowner"
    assert metadata["repo_name"] == "testrepo"
    assert metadata["default_branch"] == "main"
    assert metadata["current_branch"] == "main"
    assert metadata["last_commit_sha"] == "1234567890abcdef1234567890abcdef12345678"
    assert metadata["last_commit_message"] == "Initial commit"
    assert len(files) == 1
    assert files[0]["filename"] == "main.py"
    assert "def add" in files[0]["content"]


def test_repo_404_not_found(caplog):
    """Verify 404 response raises clear 'does not exist' error and logs at WARNING level."""
    repo_url = "https://github.com/testowner/nonexistent-repo"

    resp = MagicMock()
    resp.status_code = 404
    resp.text = "Not Found"

    with patch("httpx.get", return_value=resp):
        with pytest.raises(ValueError, match="Repository does not exist on GitHub."):
            GitService.check_public_repo(repo_url)

    assert any(
        record.levelname == "WARNING" and "404" in record.message
        for record in caplog.records
    )


def test_repo_private(caplog):
    """Verify private repository raises 'Repository is private' and logs at WARNING level."""
    repo_url = "https://github.com/testowner/private-repo"

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"private": True, "name": "private-repo"}

    with patch("httpx.get", return_value=resp):
        with pytest.raises(ValueError, match="Repository is private. Only public repositories are supported."):
            GitService.check_public_repo(repo_url)

    assert any(
        record.levelname == "WARNING" and "private" in record.message
        for record in caplog.records
    )


def test_repo_rate_limited(caplog):
    """Verify rate limits (403 and 429) raise specific rate limit error and log at WARNING level."""
    repo_url = "https://github.com/testowner/ratelimited-repo"

    for status_code in (403, 429):
        caplog.clear()
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = "rate limit exceeded"

        with patch("httpx.get", return_value=resp):
            with pytest.raises(ValueError, match="GitHub rate limit reached, try again later"):
                GitService.check_public_repo(repo_url)

        assert any(
            record.levelname == "WARNING" and "rate limit" in record.message.lower()
            for record in caplog.records
        )


def test_repo_network_error(caplog):
    """Verify network failures and timeouts raise distinct errors and log at WARNING level."""
    repo_url = "https://github.com/testowner/network-fail-repo"

    # 1. Network / Connect Error
    caplog.clear()
    with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(ValueError, match="GitHub network failure. Unable to reach GitHub API."):
            GitService.check_public_repo(repo_url)

    assert any(
        record.levelname == "WARNING" and "network error" in record.message.lower()
        for record in caplog.records
    )

    # 2. Timeout Exception
    caplog.clear()
    with patch("httpx.get", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(ValueError, match="GitHub request timed out. Please try again later."):
            GitService.check_public_repo(repo_url)

    assert any(
        record.levelname == "WARNING" and "timeout" in record.message.lower()
        for record in caplog.records
    )


def test_ssl_verification_is_enabled():
    """Verify SSL verification (verify=True) and User-Agent are strictly enforced in all httpx calls."""
    repo_url = "https://github.com/testowner/ssl-test"
    sample_zip = _make_sample_zip()

    calls = []

    def mock_httpx_get(url, *args, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        resp = MagicMock()
        resp.status_code = 200
        if "commits" in url:
            resp.json.return_value = {"sha": "sha123", "commit": {"message": "msg"}}
        elif "zipball" in url:
            resp.content = sample_zip
        else:
            resp.json.return_value = {"private": False, "default_branch": "main"}
        return resp

    with patch("httpx.get", side_effect=mock_httpx_get):
        GitService.clone_and_parse_repository(repo_url)

    assert len(calls) >= 2
    for call in calls:
        assert call["kwargs"].get("verify") is True, f"verify=True not passed for {call['url']}"
        headers = call["kwargs"].get("headers", {})
        assert headers.get("User-Agent") == GITHUB_USER_AGENT, f"User-Agent not set properly for {call['url']}"


def test_git_fallback_when_available():
    """Verify fallback to git clone occurs when zipball fails but git binary is present."""
    repo_url = "https://github.com/testowner/fallback-repo"

    def mock_httpx_get(url, *args, **kwargs):
        resp = MagicMock()
        if "zipball" in url:
            resp.status_code = 500
            resp.text = "Internal Server Error"
        else:
            resp.status_code = 200
            resp.json.return_value = {"private": False, "default_branch": "main"}
        return resp

    mock_metadata = {
        "repo_url": repo_url,
        "repo_name": "fallback-repo",
        "repo_owner": "testowner",
        "default_branch": "main",
        "current_branch": "main",
        "last_commit_sha": "git-cli-sha-777",
        "last_commit_message": "Commit via git CLI"
    }
    mock_files = [{"filename": "app.py", "content": "print('hello')", "extension": ".py", "size": 14, "language": "Python"}]

    with patch("httpx.get", side_effect=mock_httpx_get):
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch.object(GitService, "clone_repository", return_value=True):
                with patch.object(GitService, "get_repo_metadata", return_value=mock_metadata):
                    with patch.object(GitService, "parse_files", return_value=mock_files):
                        metadata, files = GitService.clone_and_parse_repository(repo_url)

    assert metadata["last_commit_sha"] == "git-cli-sha-777"
    assert len(files) == 1
    assert files[0]["filename"] == "app.py"


def test_git_unavailable_re_raises_zipball_error():
    """Verify that when git binary is not present, the real zipball failure is raised directly."""
    repo_url = "https://github.com/testowner/no-git-repo"

    def mock_httpx_get(url, *args, **kwargs):
        resp = MagicMock()
        if "zipball" in url:
            resp.status_code = 404
            resp.text = "Not Found"
        else:
            resp.status_code = 200
            resp.json.return_value = {"private": False, "default_branch": "main"}
        return resp

    with patch("httpx.get", side_effect=mock_httpx_get):
        with patch("shutil.which", return_value=None):
            with pytest.raises(ValueError, match="Repository branch or archive does not exist on GitHub."):
                GitService.clone_and_parse_repository(repo_url)


def test_git_base_cmd_flags():
    """Verify _get_git_base_cmd() returns only ['git', '-c', 'credential.helper='] and has no sslBackend/sslCAInfo/sslVerify."""
    cmd = GitService._get_git_base_cmd()
    assert cmd == ["git", "-c", "credential.helper="]
    cmd_str = " ".join(cmd)
    assert "http.sslBackend" not in cmd_str
    assert "http.sslCAInfo" not in cmd_str
    assert "sslVerify" not in cmd_str


def test_get_remote_head_sha_via_api():
    """Verify get_remote_head_sha retrieves commit SHA via GitHub API with exact httpx settings."""
    repo_url = "https://github.com/testowner/testrepo"
    calls = []

    def mock_httpx_get(url, *args, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        resp = MagicMock()
        resp.status_code = 200
        if "commits" in url:
            resp.json.return_value = {"sha": "head-sha-1234567890"}
        else:
            resp.json.return_value = {"private": False, "default_branch": "main"}
        return resp

    with patch("httpx.get", side_effect=mock_httpx_get):
        sha = GitService.get_remote_head_sha(repo_url)

    assert sha == "head-sha-1234567890"
    commit_calls = [c for c in calls if "commits" in c["url"]]
    assert len(commit_calls) == 1
    call = commit_calls[0]
    assert call["url"] == "https://api.github.com/repos/testowner/testrepo/commits/main"
    assert call["kwargs"].get("verify") is True
    assert call["kwargs"].get("follow_redirects") is True
    assert call["kwargs"].get("timeout") == 10.0
    headers = call["kwargs"].get("headers", {})
    assert headers.get("User-Agent") == GITHUB_USER_AGENT


def test_get_remote_head_sha_fallback_to_git_ls_remote():
    """Verify get_remote_head_sha falls back to git ls-remote when GitHub API fails and git exists."""
    repo_url = "https://github.com/testowner/testrepo"

    with patch("httpx.get", side_effect=httpx.ConnectError("Network offline")):
        with patch("shutil.which", return_value="/usr/bin/git"):
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "git-ls-remote-sha-999\trefs/heads/main\n"
            with patch("subprocess.run", return_value=mock_proc) as mock_run:
                sha = GitService.get_remote_head_sha(repo_url)

    assert sha == "git-ls-remote-sha-999"
    assert mock_run.called
    cmd_run = mock_run.call_args[0][0]
    assert cmd_run[:3] == ["git", "-c", "credential.helper="]
    assert "ls-remote" in cmd_run


def test_get_remote_head_sha_no_git_fallback_when_git_missing():
    """Verify get_remote_head_sha returns None without error when API fails and git binary is absent."""
    repo_url = "https://github.com/testowner/testrepo"

    with patch("httpx.get", side_effect=httpx.ConnectError("Network offline")):
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run") as mock_run:
                sha = GitService.get_remote_head_sha(repo_url)

    assert sha is None
    assert not mock_run.called


def test_github_token_header_present_when_env_set(monkeypatch):
    """Verify Authorization header is included in GitHub API requests when GITHUB_API_TOKEN is set."""
    monkeypatch.setenv("GITHUB_API_TOKEN", "ghp_secrettoken123456789")
    repo_url = "https://github.com/testowner/testrepo"
    captured_headers = []

    def mock_httpx_get(url, *args, **kwargs):
        captured_headers.append(kwargs.get("headers", {}))
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"private": False, "default_branch": "main"}
        return resp

    with patch("httpx.get", side_effect=mock_httpx_get):
        GitService.check_public_repo(repo_url)

    assert len(captured_headers) == 1
    assert captured_headers[0].get("Authorization") == "Bearer ghp_secrettoken123456789"


def test_github_token_header_absent_when_env_not_set(monkeypatch):
    """Verify Authorization header is absent when GITHUB_API_TOKEN is not set."""
    monkeypatch.delenv("GITHUB_API_TOKEN", raising=False)
    repo_url = "https://github.com/testowner/testrepo"
    captured_headers = []

    def mock_httpx_get(url, *args, **kwargs):
        captured_headers.append(kwargs.get("headers", {}))
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"private": False, "default_branch": "main"}
        return resp

    with patch("httpx.get", side_effect=mock_httpx_get):
        GitService.check_public_repo(repo_url)

    assert len(captured_headers) == 1
    assert "Authorization" not in captured_headers[0]


def test_repo_rate_limited_with_reset_time():
    """Verify rate limit (403/429) reads X-RateLimit-Reset and shows HH:MM reset time in error."""
    repo_url = "https://github.com/testowner/ratelimited-repo"
    # Epoch 1700000000 corresponds to 22:13 UTC
    resp = MagicMock()
    resp.status_code = 403
    resp.headers = {"X-RateLimit-Reset": "1700000000"}

    with patch("httpx.get", return_value=resp):
        with pytest.raises(ValueError) as excinfo:
            GitService.check_public_repo(repo_url)

    assert "GitHub rate limit reached, try again at 22:13" in str(excinfo.value)

    # Also test 429 status code
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"X-RateLimit-Reset": "1700003600"}  # 23:13 UTC

    with patch("httpx.get", return_value=resp_429):
        with pytest.raises(ValueError) as excinfo:
            GitService.check_public_repo(repo_url)

    assert "GitHub rate limit reached, try again at 23:13" in str(excinfo.value)


def test_rate_limited_git_fallback_when_git_available():
    """Verify that when API is rate limited and git binary is available, clone_and_parse_repository falls back to git clone --depth 1."""
    repo_url = "https://github.com/testowner/fallback-repo"

    resp = MagicMock()
    resp.status_code = 403
    resp.headers = {"X-RateLimit-Reset": "1700000000"}

    mock_metadata = {
        "repo_url": repo_url,
        "repo_name": "fallback-repo",
        "repo_owner": "testowner",
        "default_branch": "main",
        "current_branch": "main",
        "last_commit_sha": "git-clone-sha-12345",
        "last_commit_message": "Fetched via git fallback"
    }
    mock_files = [{"filename": "app.py", "content": "print('hello')", "extension": ".py", "size": 14, "language": "Python"}]

    with patch("httpx.get", return_value=resp):
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch.object(GitService, "clone_repository", return_value=True):
                with patch.object(GitService, "get_repo_metadata", return_value=mock_metadata):
                    with patch.object(GitService, "parse_files", return_value=mock_files):
                        metadata, files = GitService.clone_and_parse_repository(repo_url)

    assert metadata["last_commit_sha"] == "git-clone-sha-12345"
    assert len(files) == 1
    assert files[0]["filename"] == "app.py"


def test_rate_limited_git_fallback_fails_shows_rate_limit_error():
    """Verify that if API is rate limited and git clone fallback fails, the rate limit message with reset time is shown."""
    repo_url = "https://github.com/testowner/fallback-repo"

    resp = MagicMock()
    resp.status_code = 403
    resp.headers = {"X-RateLimit-Reset": "1700000000"}

    with patch("httpx.get", return_value=resp):
        with patch("shutil.which", return_value="/usr/bin/git"):
            with patch.object(GitService, "clone_repository", return_value=False):
                with pytest.raises(ValueError) as excinfo:
                    GitService.clone_and_parse_repository(repo_url)

    assert "GitHub rate limit reached, try again at 22:13" in str(excinfo.value)


