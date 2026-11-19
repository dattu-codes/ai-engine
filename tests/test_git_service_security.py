import os
import inspect
import tempfile
import shutil
from app.projects.services.git_service import GitService, remove_readonly
import app.projects.services.git_service as gs_module

def test_no_hardcoded_intern_mock_or_antigravity_email_in_git_service():
    """Verify git_service.py contains no ai-engine-intern mock or tester@antigravity.ai email."""
    source = inspect.getsource(gs_module)
    assert "ai-engine-intern" not in source, "Found 'ai-engine-intern' mock in git_service.py"
    assert "tester@antigravity.ai" not in source, "Found 'tester@antigravity.ai' mock in git_service.py"
    assert "Mock Repository" not in source, "Found mock repo synthesis in git_service.py"


def test_git_service_validate_url():
    """Verify GitService URL validation accept and rejects URLs strictly."""
    valid, owner, repo = GitService.validate_url("https://github.com/dattu-codes/ai-engine-intern")
    assert valid is True
    assert owner == "dattu-codes"
    assert repo == "ai-engine-intern"

    valid_git, owner, repo = GitService.validate_url("https://github.com/octocat/Hello-World.git")
    assert valid_git is True
    assert owner == "octocat"
    assert repo == "Hello-World"

    invalid, _, _ = GitService.validate_url("https://malicious.com/repo.git")
    assert invalid is False

    invalid_scheme, _, _ = GitService.validate_url("file:///etc/passwd")
    assert invalid_scheme is False


def test_git_service_is_public_repo_rejects_nonexistent_repo():
    """Verify is_public_repo returns False for non-existent repositories."""
    res = GitService.is_public_repo("https://github.com/nonexistent-org-00000000/nonexistent-repo-99999999.git")
    assert res is False


def test_git_service_clone_fails_on_nonexistent_repo_without_creating_mock_files():
    """Verify clone_repository returns False on invalid repo and does not synthesize dummy files."""
    dest = tempfile.mkdtemp(prefix="ai_engine_test_clone_")
    try:
        res = GitService.clone_repository("https://github.com/nonexistent-org-00000000/nonexistent-repo-99999999.git", dest)
        assert res is False
        # Confirm no mock files (main.py, Engine.java, etc.) were synthesized
        assert not os.path.exists(os.path.join(dest, "main.py"))
        assert not os.path.exists(os.path.join(dest, "Engine.java"))
        assert not os.path.exists(os.path.join(dest, "README.md"))
    finally:
        shutil.rmtree(dest, onerror=remove_readonly)
