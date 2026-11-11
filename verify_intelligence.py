import os
import sys
import json
import time
import io
import zipfile
from typing import Tuple, Optional

# In-memory test client runner
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from test_client_helper import make_request, make_multipart_request


def create_springboot_zip() -> bytes:
    """Creates a ZIP with a Java Spring Boot layout."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pom.xml", """<project>
            <dependencies>
                <dependency>
                    <groupId>org.springframework.boot</groupId>
                    <artifactId>spring-boot-starter-web</artifactId>
                    <version>3.1.0</version>
                </dependency>
                <dependency>
                    <groupId>org.springframework.boot</groupId>
                    <artifactId>spring-boot-starter-data-jpa</artifactId>
                    <version>3.1.0</version>
                </dependency>
            </dependencies>
        </project>""")
        
        zf.writestr("src/main/java/com/example/demo/DemoApplication.java", """package com.example.demo;
        import org.springframework.boot.SpringApplication;
        import org.springframework.boot.autoconfigure.SpringBootApplication;
        
        @SpringBootApplication
        public class DemoApplication {
            public static void main(String[] args) {
                SpringApplication.run(DemoApplication.class, args);
            }
        }""")
        
        zf.writestr("src/main/java/com/example/demo/controller/UserController.java", """package com.example.demo.controller;
        public class UserController {}""")
        
        zf.writestr("src/main/java/com/example/demo/service/UserService.java", """package com.example.demo.service;
        public class UserService {}""")
        
        zf.writestr("src/main/java/com/example/demo/repository/UserRepository.java", """package com.example.demo.repository;
        public class UserRepository {}""")
        
    return zip_buffer.getvalue()


def create_fastapi_zip() -> bytes:
    """Creates a ZIP with a Python FastAPI layout."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("requirements.txt", "fastapi==0.100.0\nuvicorn>=0.22.0\nsqlalchemy\n")
        zf.writestr("main.py", """from fastapi import FastAPI
        app = FastAPI()
        """)
        zf.writestr("app/routes/users.py", """# routes for users""")
        zf.writestr("app/models/user.py", """# database models""")
        
    return zip_buffer.getvalue()


def run_tests():
    print("=========================================================")
    print("   Starting Automated Code Intelligence Verification    ")
    print("=========================================================")
    print()

    # Generate unique credentials
    timestamp = int(time.time())
    username = f"intel_user_{timestamp}"
    password = "securepassword123"

    # --- 1. Signup & Signin ---
    print("[1] Registering and signing in test user...")
    make_request("POST", "/auth/signup", {"username": username, "password": password, "role": "user"})
    status, token_res = make_request("POST", "/auth/login", {"username": username, "password": password})
    assert status == 200, "User login failed."
    token = token_res["access_token"]
    print("    Access Token acquired successfully.")

    # --- 2. Create Project ---
    print("[2] Creating a new project...")
    status, project = make_request("POST", "/projects", {"name": "Test Code Intelligence"}, token=token)
    assert status == 201, f"Project creation failed with status {status}"
    project_id = project["id"]
    print(f"    Project created ID: {project_id}")

    # --- 3. Ingest Spring Boot Project ZIP ---
    print("[3] Uploading Spring Boot project ZIP...")
    sb_zip = create_springboot_zip()
    files = {"file": ("springboot.zip", sb_zip)}
    status, upload_res = make_multipart_request(f"/projects/{project_id}/upload", fields={}, files=files, token=token)
    assert status == 200, f"Upload failed: {upload_res}"
    print("    ZIP ingested successfully.")

    # --- 4. Verify Code Intelligence ---
    print("[4] Checking Code Intelligence metadata via details API...")
    status, details = make_request("GET", f"/projects/{project_id}", token=token)
    assert status == 200, f"Get details failed: {details}"
    
    # Assertions
    assert details["has_intelligence"] is True, "has_intelligence should be True"
    assert details["project_type"] == "Java Spring Boot Application", f"Expected Java Spring Boot Application, got '{details['project_type']}'"
    assert details["framework"] == "Spring Boot", f"Expected Spring Boot, got '{details['framework']}'"
    assert details["entry_point"] == "src/main/java/com/example/demo/DemoApplication.java", f"Expected DemoApplication.java entry point, got '{details['entry_point']}'"
    assert "Repository Pattern" in details["architecture"], f"Expected Repository Pattern in architecture, got '{details['architecture']}'"
    assert "Layered Architecture" in details["architecture"], f"Expected Layered Architecture, got '{details['architecture']}'"
    
    # Verify languages distribution
    lang_dist = json.loads(details["languages_distribution"])
    assert "Java" in lang_dist, "Java should be in languages distribution"
    
    # Verify dependencies
    deps = json.loads(details["dependencies_json"])
    dep_names = {d["name"] for d in deps}
    assert "org.springframework.boot:spring-boot-starter-web" in dep_names, "Starter Web dependency should be extracted"
    assert "org.springframework.boot:spring-boot-starter-data-jpa" in dep_names, "Starter Data JPA dependency should be extracted"
    print("    Spring Boot metadata and dependencies validated successfully.")

    # --- 5. Verify File Prioritization ---
    priorities = json.loads(details["file_priorities"])
    assert priorities["src/main/java/com/example/demo/controller/UserController.java"] == "high", "Controllers should be high priority"
    assert priorities["src/main/java/com/example/demo/service/UserService.java"] == "high", "Services should be high priority"
    assert priorities["src/main/java/com/example/demo/repository/UserRepository.java"] == "high", "Repositories should be high priority"
    print("    File prioritization values validated successfully.")

    # --- 6. Ingest FastAPI Project ZIP & Invalidation ---
    print("[5] Uploading FastAPI project ZIP to test cache invalidation...")
    fa_zip = create_fastapi_zip()
    files = {"file": ("fastapi.zip", fa_zip)}
    status, upload_res = make_multipart_request(f"/projects/{project_id}/upload", fields={}, files=files, token=token)
    assert status == 200, f"Upload failed: {upload_res}"
    
    # Check details immediately - should be re-analyzing on first retrieve
    status, details = make_request("GET", f"/projects/{project_id}", token=token)
    assert status == 200, f"Get details failed: {details}"
    
    assert details["has_intelligence"] is True, "has_intelligence should be True after re-analysis"
    assert details["project_type"] == "Python FastAPI Service", f"Expected Python FastAPI Service, got '{details['project_type']}'"
    assert details["framework"] == "FastAPI", f"Expected FastAPI, got '{details['framework']}'"
    assert details["entry_point"] == "main.py", f"Expected main.py entry point, got '{details['entry_point']}'"
    
    fa_deps = json.loads(details["dependencies_json"])
    fa_dep_names = {d["name"] for d in fa_deps}
    assert "fastapi" in fa_dep_names, "fastapi package should be in dependencies"
    
    fa_priorities = json.loads(details["file_priorities"])
    assert fa_priorities["app/routes/users.py"] == "high", "Routes should be high priority"
    assert fa_priorities["app/models/user.py"] == "medium", "Models should be medium priority"
    
    print("    FastAPI metadata, cache invalidation, and custom priorities validated successfully.")

    # --- 7. Paste Code & Invalidation ---
    print("[6] Ingesting pasted code snippet...")
    paste_fields = {
        "pasted_filename": "app/utils/helper.py",
        "pasted_content": "def calculate():\n    return 42"
    }
    status, upload_res = make_multipart_request(f"/projects/{project_id}/upload", fields=paste_fields, files={}, token=token)
    assert status == 200, f"Paste upload failed: {upload_res}"
    
    status, details = make_request("GET", f"/projects/{project_id}", token=token)
    assert status == 200, f"Get details failed: {details}"
    
    fa_priorities_new = json.loads(details["file_priorities"])
    assert fa_priorities_new["app/utils/helper.py"] == "medium", "Helpers should be medium priority"
    print("    Pasted code cache invalidation verified successfully.")

    print()
    print("=========================================================")
    print("   Code Intelligence Verification Passed Successfully!  ")
    print("=========================================================")


if __name__ == "__main__":
    run_tests()
