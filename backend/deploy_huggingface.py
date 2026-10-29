#!/usr/bin/env python3
"""
Autonomous Hugging Face Spaces Deployment Script
Deploys the Indian Family Law Assistant backend to Hugging Face Spaces Docker container (16GB RAM Free Tier).
"""

import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
from dotenv import dotenv_values
from huggingface_hub import HfApi, create_repo, upload_folder

BACKEND_DIR = Path(__file__).resolve().parent

def deploy(token: str, space_name: str = "indian-family-law-api"):
    print("=" * 65)
    print("🚀 STEP 1: AUTHENTICATING WITH HUGGING FACE")
    print("=" * 65)
    api = HfApi(token=token)
    user_info = api.whoami()
    username = user_info.get("name")
    print(f"✓ Authenticated as: {username}")

    repo_id = f"{username}/{space_name}"
    print(f"\n🚀 STEP 2: CREATING/VERIFYING SPACE: {repo_id} (SDK: docker)")
    try:
        url = create_repo(
            repo_id=repo_id,
            token=token,
            repo_type="space",
            space_sdk="docker",
            private=False,
            exist_ok=True
        )
        print(f"✓ Space ready at: {url}")
    except Exception as e:
        print(f"  Space existence check: {e}")

    # Set up README.md with Docker space configuration
    print("\n🚀 STEP 3: PREPARING DOCKER CONFIGURATION")
    readme_path = BACKEND_DIR / "README_HF.md"
    readme_content = f"""---
title: Indian Family Law Assistant API
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Indian Family Law Assistant API
High-performance LangGraph + FastAPI legal assistance backend.
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    # Set secrets from .env
    print("\n🚀 STEP 4: INJECTING PRODUCTION SECRETS")
    env_vals = dotenv_values(str(BACKEND_DIR / ".env"))
    secrets_to_set = [
        "GROQ_API_KEY", "DAHL_API_KEY", "DAHL_API_KEY_2", "DAHL_BASE_URL",
        "OPENROUTER_API_KEYS", "JWT_SECRET_KEY"
    ]
    for sec_key in secrets_to_set:
        val = env_vals.get(sec_key)
        if val:
            try:
                api.add_space_secret(repo_id=repo_id, key=sec_key, value=val)
                print(f"  ✓ Secret injected: {sec_key}")
            except Exception as e:
                print(f"  - Note for {sec_key}: {e}")

    # Inject ALLOWED_ORIGINS=*
    try:
        api.add_space_variable(repo_id=repo_id, key="ALLOWED_ORIGINS", value="*")
        print("  ✓ Space variable set: ALLOWED_ORIGINS=*")
    except Exception as e:
        pass

    # Upload files
    print("\n🚀 STEP 5: UPLOADING APPLICATION FILES TO SPACE")
    ignore_patterns = [
        "*.pyc", "__pycache__", ".venv", ".venv/*", ".git", ".git/*",
        "*.db-journal", "logs/*", ".pytest_cache", ".pytest_cache/*",
        ".env", "*.png", "*.jpg"
    ]

    upload_folder(
        folder_path=str(BACKEND_DIR),
        repo_id=repo_id,
        repo_type="space",
        token=token,
        ignore_patterns=ignore_patterns,
        path_in_repo=""
    )
    print("  ✓ Application source files uploaded.")

    # Upload README_HF.md as README.md
    api.upload_file(
        path_or_fileobj=str(readme_path),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="space",
        token=token
    )
    print("  ✓ Docker Space metadata (README.md) uploaded.")

    # Upload Dockerfile.hf as Dockerfile
    hf_dockerfile = BACKEND_DIR / "Dockerfile.hf"
    if hf_dockerfile.exists():
        api.upload_file(
            path_or_fileobj=str(hf_dockerfile),
            path_in_repo="Dockerfile",
            repo_id=repo_id,
            repo_type="space",
            token=token
        )
        print("  ✓ Production Dockerfile (Port 7860, UID 1000) uploaded.")

    public_host = f"{username.lower()}-{space_name.lower().replace('_', '-')}.hf.space"
    public_url = f"https://{public_host}"
    space_page = f"https://huggingface.co/spaces/{repo_id}"

    print("\n" + "=" * 65)
    print("🎉 DEPLOYMENT LAUNCHED ON HUGGING FACE SPACES!")
    print(f"Space Page:  {space_page}")
    print(f"Public API:  {public_url}")
    print(f"Health API:  {public_url}/health")
    print("=" * 65)
    return public_url, repo_id

if __name__ == "__main__":
    token = os.environ.get("HUGGINGFACE_API_KEY", "")
    if token:
        deploy(token)
    else:
        print("HUGGINGFACE_API_KEY not set")
