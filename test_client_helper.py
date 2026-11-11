import os
import sys
import json
from typing import Tuple, Optional, Dict, Any
from fastapi.testclient import TestClient

# Ensure ai-engine root is in sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.main import app

client = TestClient(app)

def make_request(
    method: str, 
    path: str, 
    data: Optional[Any] = None, 
    token: Optional[str] = None
) -> Tuple[int, dict]:
    """In-memory HTTP request executor using FastAPI TestClient."""
    if isinstance(data, str) and token is None and not (data.strip().startswith("{") or data.strip().startswith("[")):
        token = data
        data = None

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    resp = client.request(method, path, json=data, headers=headers)
    try:
        res_json = resp.json()
    except Exception:
        res_json = {"detail": resp.text}
    return resp.status_code, res_json

def make_multipart_request(
    path: str,
    fields: Optional[dict] = None,
    files: Optional[Any] = None,
    token: Optional[str] = None
) -> Tuple[int, dict]:
    """In-memory multipart/form-data upload using FastAPI TestClient."""
    if isinstance(files, str) and token is None:
        token = files
        files = None

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    upload_files = {}
    if files:
        for key, val in files.items():
            if isinstance(val, tuple):
                if len(val) == 2:
                    filename, content = val
                    mime = "application/octet-stream"
                else:
                    filename, content, mime = val[0], val[1], val[2]
                upload_files[key] = (filename, content, mime)
            else:
                upload_files[key] = val

    resp = client.post(path, data=fields or {}, files=upload_files or None, headers=headers)
    try:
        res_json = resp.json()
    except Exception:
        res_json = {"detail": resp.text}
    return resp.status_code, res_json
