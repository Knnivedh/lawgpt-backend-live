"""
Configuration for Testing System
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from config/.env
project_root = Path(__file__).parent.parent
load_dotenv(project_root / "config" / ".env")

# Import Config after loading .env
from config.config import Config


class TestConfig:
    """Centralized test configuration"""
    
    # Paths
    BASE_DIR = Path(__file__).parent
    PROJECT_ROOT = BASE_DIR.parent
    
    DATASET_CLEANED = BASE_DIR / "kaanoon_qa_dataset_cleaned.json"
    DATASET_SUMMARY = BASE_DIR / "kaanoon_qa_summary.json"
    TEST_QUERIES_FILE = BASE_DIR / "test_queries_generated.json"
    RESULTS_DIR = BASE_DIR / "test_results"
    
    # API Keys - Load from Config (which loads from .env)
    NVIDIA_API_KEY = Config.get_nvidia_api_key()
    NVIDIA_API_KEY_2 = Config.get_nvidia_api_key(use_backup=True)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # Optional, not used currently
    
    # Systems to Test
    SYSTEMS_TO_TEST = [
        {
            'name': 'LAW-GPT ULTIMATE RAG (80%+ Target)',
            'type': 'rag_ultimate',
            'enabled': True
        },
        {
            'name': 'LAW-GPT Optimized RAG',
            'type': 'rag_optimized',
            'enabled': True
        },
        {
            'name': 'LAW-GPT RAG System (Baseline)',
            'type': 'rag_system',
            'enabled': False
        },
        {
            'name': 'Standalone Kaanoon Bot',
            'type': 'standalone',
            'enabled': False  # Disabled for now
        },
        {
            'name': 'NVIDIA Llama 3.1 70B',
            'type': 'external',
            'provider': 'nvidia',
            'model': 'meta/llama-3.1-70b-instruct',
            'enabled': False  # Disabled for now
        },
        {
            'name': 'OpenRouter Gemini 2.0',
            'type': 'external',
            'provider': 'openrouter',
            'model': 'google/gemini-2.0-flash-exp:free',
            'enabled': False  # Disabled - requires OPENROUTER_API_KEY environment variable
        }
    ]
    
    # Test Parameters
    TIMEOUT_SECONDS = 30
    MAX_RETRIES = 2
    RETRY_DELAY = 1.0
    
    # Metrics Thresholds (what's considered "good")
    THRESHOLDS = {
        'accuracy_score': 0.7,  # 70% overall accuracy
        'semantic_similarity': 0.6,  # 60% semantic match
        'keyword_f1': 0.5,  # 50% keyword overlap
        'reference_match': 0.4,  # 40% legal references matched
        'latency_ms': 5000,  # 5 seconds max
    }
    
    # Report Settings
    REPORT_FORMATS = ['json', 'html', 'csv']
    INCLUDE_RAW_RESPONSES = True
    INCLUDE_FAILURE_ANALYSIS = True
    
    @classmethod
    def ensure_dirs(cls):
        """Create necessary directories"""
        cls.RESULTS_DIR.mkdir(exist_ok=True)
        
    @classmethod
    def get_enabled_systems(cls):
        """Get list of enabled systems"""
        return [s for s in cls.SYSTEMS_TO_TEST if s.get('enabled', True)]


# Create directories on import
TestConfig.ensure_dirs()

