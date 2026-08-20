#!/usr/bin/env python3
"""
setup_indian_law_db.py - Complete pipeline for Indian Law database setup

This script:
1. Processes both JSON files from family_law_domain
2. Creates optimized chunks to prevent overflow
3. Generates 768-dimensional embeddings using InLegal-Sbert
4. Creates a new Milvus collection with proper dimensions
5. Loads all data into the new collection

Usage:
    python setup_indian_law_db.py

Requirements:
    - InLegal-Sbert model (will be downloaded automatically)
    - Milvus connection configured in .env
    - JSON files in ./data/family_law_domain/
"""

import os
import sys
import json
import time
import dotenv
from pathlib import Path

# Load environment variables
dotenv.load_dotenv()

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_step(step_num, total_steps, message):
    """Print formatted step message"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}[Step {step_num}/{total_steps}]{Colors.END} {Colors.BOLD}{message}{Colors.END}")

def print_success(message):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_warning(message):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠️  {message}{Colors.END}")

def print_error(message):
    """Print error message"""
    print(f"{Colors.FAIL}❌ {message}{Colors.END}")

def verify_data_files():
    """Verify that data files exist"""
    data_dir = Path("./data/family_law_domain")
    
    if not data_dir.exists():
        print_error(f"Data directory not found: {data_dir}")
        return False
    
    json_files = list(data_dir.glob("*.json"))
    json_files = [f for f in json_files if not f.name.endswith(".bak")]
    
    if not json_files:
        print_error("No JSON files found in data directory")
        return False
    
    print_success(f"Found {len(json_files)} data files:")
    for f in json_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  📄 {f.name} ({size_mb:.2f} MB)")
    
    return True

def run_chunking():
    """Run the chunking process"""
    print("\n📦 Starting chunking process...")
    print("   Using optimized parameters to prevent overflow:")
    print("   • Chunk size: 600 tokens")
    print("   • Overlap: 80 tokens")
    print("   • Max query length: 8000 chars")
    
    try:
        import chunking
        print_success("Chunking completed successfully")
        return True
    except Exception as e:
        print_error(f"Chunking failed: {e}")
        return False

def run_embedding():
    """Run the embedding generation"""
    print("\n🔢 Starting embedding generation...")
    print("   Using InLegal-Sbert (law-ai/InLegal-Sbert)")
    print("   Embedding dimension: 768")
    print("   Note: First run will download the model (~440 MB)")
    
    try:
        import embedding
        print_success("Embeddings generated successfully")
        return True
    except Exception as e:
        print_error(f"Embedding generation failed: {e}")
        return False

def run_milvus_setup():
    """Run the Milvus database setup"""
    print("\n💾 Starting Milvus database setup...")
    
    milvus_uri = os.getenv("MILVUS_URI")
    collection_name = os.getenv("MILVUS_COLLECTION_NAME", "indian_family_law_cases")
    
    print(f"   Collection: {collection_name}")
    print(f"   Endpoint: {milvus_uri}")
    
    try:
        import milvus_store
        print_success("Milvus database setup completed")
        return True
    except Exception as e:
        print_error(f"Milvus setup failed: {e}")
        return False

def verify_setup():
    """Verify the complete setup"""
    print("\n🔍 Verifying setup...")
    
    checks = []
    
    # Check chunked files
    chunked_dir = Path("./data/chunked")
    if chunked_dir.exists():
        chunk_files = list(chunked_dir.glob("*_chunks.json"))
        checks.append(("Chunk files", len(chunk_files) > 0, f"{len(chunk_files)} files"))
    else:
        checks.append(("Chunk files", False, "Directory not found"))
    
    # Check embedding files
    embeddings_dir = Path("./data/embeddings")
    if embeddings_dir.exists():
        embed_files = list(embeddings_dir.glob("*_embeddings.json"))
        checks.append(("Embedding files", len(embed_files) > 0, f"{len(embed_files)} files"))
        
        # Verify embedding dimensions
        if embed_files:
            with open(embed_files[0]) as f:
                sample = json.load(f)
                if sample:
                    dim = len(sample[0]["embedding"])
                    checks.append(("Embedding dimension", dim == 768, f"{dim}D"))
    else:
        checks.append(("Embedding files", False, "Directory not found"))
    
    print("\n📊 Verification Results:")
    all_passed = True
    for name, passed, detail in checks:
        status = f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.FAIL}✗{Colors.END}"
        print(f"  {status} {name}: {detail}")
        all_passed = all_passed and passed
    
    return all_passed

def main():
    """Main execution function"""
    start_time = time.time()
    
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * 70)
    print("🇮🇳  Indian Family Law Database Setup")
    print("=" * 70)
    print(f"{Colors.END}")
    
    print("\nThis script will:")
    print("  1. Process JSON files with Indian family law cases")
    print("  2. Create optimized text chunks")
    print("  3. Generate embeddings using InLegal-Sbert (768-dim)")
    print("  4. Create new Milvus collection")
    print("  5. Load all data into the database")
    
    # Verify prerequisites
    print_step(0, 5, "Verifying prerequisites")
    if not verify_data_files():
        print_error("Prerequisites check failed. Please ensure data files exist.")
        return 1
    
    # Check environment variables
    if not os.getenv("MILVUS_URI") or not os.getenv("MILVUS_TOKEN"):
        print_error("MILVUS_URI and MILVUS_TOKEN must be set in .env file")
        return 1
    
    print_success("Prerequisites verified")
    
    # Step 1: Chunking
    print_step(1, 5, "Creating text chunks")
    if not run_chunking():
        print_error("Setup failed at chunking step")
        return 1
    
    # Step 2: Embedding
    print_step(2, 5, "Generating embeddings with InLegal-Sbert")
    if not run_embedding():
        print_error("Setup failed at embedding step")
        return 1
    
    # Step 3: Milvus setup
    print_step(3, 5, "Setting up Milvus database")
    if not run_milvus_setup():
        print_error("Setup failed at Milvus setup step")
        return 1
    
    # Step 4: Verification
    print_step(4, 5, "Verifying setup")
    if not verify_setup():
        print_warning("Some verification checks failed, but database may still be functional")
    
    # Step 5: Complete
    print_step(5, 5, "Setup complete!")
    
    elapsed = time.time() - start_time
    print(f"\n{Colors.BOLD}{Colors.GREEN}")
    print("=" * 70)
    print("✨ Indian Family Law Database Setup Complete!")
    print("=" * 70)
    print(f"{Colors.END}")
    
    print(f"\n⏱️  Total time: {elapsed:.2f} seconds")
    print(f"\n{Colors.BOLD}Next steps:{Colors.END}")
    print("  1. Update your .env file with the new collection name")
    print("  2. Restart your application")
    print("  3. Test queries with Indian law context")
    
    print(f"\n{Colors.CYAN}Collection name:{Colors.END} {os.getenv('MILVUS_COLLECTION_NAME', 'indian_family_law_cases')}")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Setup interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
