#!/usr/bin/env python3
"""
Autonomous Hugging Face Spaces Deployment Script
Deploys the FastAPI backend to Hugging Face Spaces Docker container (16GB RAM, Free Tier).
"""

import os
import sys
import time
from pathlib import Path
from huggingface_hub import HfApi, create_repo, upload_folder

BACKEND_DIR = Path(__file__).resolve().parent

def deploy_to_hf(token: str, space_name: str = "indian-family-law-api", organization: str = None):
    print("=" * 60)
    print("1. Authenticating with Hugging Face...")
    api = HfApi(token=token)
    user_info = api.whoami()
    username = user_info.get("name")
    print(f"   Authenticated as: {username}")

    repo_id = f"{organization or username}/{space_name}"
    print(f"2. Preparing Space: {repo_id} (SDK: docker)...")

    try:
        create_repo(
            repo_id=repo_id,
            token=token,
            repo_type="space",
            space_sdk="docker",
            private=False,
            exist_ok=True
        )
        print("   Space created / verified successfully.")
    except Exception as e:
        print(f"   Note on space creation: {e}")

    # Set up README.md with Docker space metadata
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

    print("3. Syncing files to Space...")
    # Prepare dockerfile for HF
    hf_dockerfile = BACKEND_DIR / "Dockerfile.hf"
    temp_dockerfile = BACKEND_DIR / "Dockerfile"
    
    # Upload backend files
    # Exclude unnecessary caches and local env
    ignore_patterns = [
        "*.pyc", "__pycache__", ".venv", ".venv/*", ".git", ".git/*",
        "*.db-journal", "logs/*", ".pytest_cache", ".pytest_cache/*"
    ]

    print("   Uploading application source to Hugging Face...")
    upload_folder(
        folder_path=str(BACKEND_DIR),
        repo_id=repo_id,
        repo_type="space",
        token=token,
        ignore_patterns=ignore_patterns,
        path_in_repo=""
    )

    # Upload README_HF as README.md
    api.upload_file(
        path_or_fileobj=str(readme_path),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="space",
        token=token
    )

    # Upload Dockerfile.hf as Dockerfile
    if hf_dockerfile.exists():
        api.upload_file(
            path_or_fileobj=str(hf_dockerfile),
            path_in_repo="Dockerfile",
            repo_id=repo_id,
            repo_type="space",
            token=token
        )

    public_url = f"https://{username.lower()}-{space_name.lower().replace('_', '-')}.hf.space"
    space_page = f"https://huggingface.co/spaces/{repo_id}"

    print("=" * 60)
    print("DEPLOYMENT INITIATED SUCCESSFULLY!")
    print(f"Space URL:    {space_page}")
    print(f"Public API:   {public_url}")
    print(f"Health Check: {public_url}/health")
    print("=" * 60)
    return public_url, space_page

if __name__ == "__main__":
    if len(sys.argv) < 2:
        token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        if not token:
            print("Usage: python deploy_huggingface.py <HF_WRITE_TOKEN> [space_name]")
            sys.exit(1)
    else:
        token = sys.argv[1]

    space_name = sys.argv[2] if len(sys.argv) > 2 else "indian-family-law-api"
    deploy_to_hf(token, space_name)
