"""
Quick Start Script for Expert Legal RAG System
Starts the backend server with all expert components
"""

import subprocess
import sys
from pathlib import Path

def start_server():
    """Start the advanced RAG API server"""
    project_root = Path(__file__).parent.parent
    server_path = project_root / "kaanoon_test" / "advanced_rag_api_server.py"
    
    print("="*60)
    print("STARTING EXPERT LEGAL RAG SYSTEM")
    print("="*60)
    print(f"\nServer: {server_path}")
    print("Port: 5000")
    print("URL: http://localhost:5000")
    print("\nInitializing... (this may take 30-60 seconds)")
    print("="*60)
    
    try:
        subprocess.run([
            sys.executable,
            str(server_path)
        ], cwd=str(project_root / "kaanoon_test"))
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
    except Exception as e:
        print(f"\n[ERROR] Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    start_server()

