"""
Indian Kanoon API Client
Provides real-time access to case law, judgments, and bare acts from Indian Kanoon
"""

import requests
from typing import Dict, List, Optional, Any
import time
from functools import lru_cache
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from config directory
config_path = Path(__file__).parent.parent.parent / "config" / ".env"
load_dotenv(dotenv_path=config_path)


class IndianKanoonClient:
    """Client for Indian Kanoon API integration."""
    
    BASE_URL = "https://api.indiankanoon.org"
    SEARCH_URL = f"{BASE_URL}/search/"
    DOC_URL = f"{BASE_URL}/doc/"
    
    def __init__(self, api_token: str = None, timeout: int = 10, cache_size: int = 128):
        """
        Initialize Indian Kanoon API client with authentication.
        
        Args:
            api_token: Indian Kanoon API token (if None, loads from .env)
            timeout: Request timeout in seconds
            cache_size: LRU cache size for repeated queries
        """
        # Load API token from environment or parameter
        self.api_token = api_token or os.getenv('INDIAN_KANOON_API_TOKEN')
        
        if not self.api_token:
            print("[WARNING] Indian Kanoon API token not found. Set INDIAN_KANOON_API_TOKEN in .env")
        else:
            print(f"[OK] Indian Kanoon API authenticated (token: {self.api_token[:20]}...)")
        
        env_timeout = os.getenv("INDIAN_KANOON_TIMEOUT_SECONDS", "").strip()
        if env_timeout:
            try:
                timeout = max(1, int(env_timeout))
            except ValueError:
                print(f"[WARNING] Invalid INDIAN_KANOON_TIMEOUT_SECONDS='{env_timeout}', using default {timeout}s")

        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Authorization': f'Token {self.api_token}' if self.api_token else ''
        })
    
    @lru_cache(maxsize=128)
    def search_judgments(
        self, 
        query: str, 
        court: Optional[str] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for judgments on Indian Kanoon.
        
        Args:
            query: Search query (case name, citation, keywords)
            court: Filter by court (e.g., "Supreme Court", "Delhi High Court")
            max_results: Maximum number of results to return
            
        Returns:
            List of judgment dictionaries with title, doc_id, court, year
        """
        try:
            # Build search query
            search_query = query
            if court:
                search_query = f"{query} court:{court}"
            
            data = {
                'formInput': search_query,
                'pagenum': 0
            }
            
            # Primary method is POST; fallback to GET on 405 for compatibility.
            response = self.session.post(
                self.SEARCH_URL,
                data=data,
                timeout=self.timeout
            )
            if response.status_code == 405:
                response = self.session.get(
                    self.SEARCH_URL,
                    params=data,
                    timeout=self.timeout
                )
            response.raise_for_status()
            
            data = response.json()
            
            # Parse results
            results = []
            for item in data.get('docs', [])[:max_results]:
                results.append({
                    'title': item.get('title', ''),
                    'doc_id': item.get('tid', ''),
                    'court': self._extract_court(item.get('title', '')),
                    'year': self._extract_year(item.get('title', '')),
                    'snippet': item.get('headline', '')[:200]
                })
            
            return results
            
        except Exception as e:
            print(f"[Indian Kanoon] Search error: {e}")
            return []
    
    @lru_cache(maxsize=64)
    def get_judgment(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full judgment text by document ID.
        
        Args:
            doc_id: Indian Kanoon document ID
            
        Returns:
            Dictionary with full judgment text and metadata
        """
        try:
            url = f"{self.DOC_URL}{doc_id}/"
            
            # Document endpoint frequently expects GET; fallback to POST for compatibility.
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 405:
                response = self.session.post(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'doc_id': doc_id,
                'title': data.get('title', ''),
                'text': data.get('doc', ''),
                'citation': self._extract_citation(data.get('title', '')),
                'court': self._extract_court(data.get('title', '')),
                'year': self._extract_year(data.get('title', ''))
            }
            
        except Exception as e:
            print(f"[Indian Kanoon] Document fetch error: {e}")
            return None
    
    def verify_citation(self, citation: str) -> Dict[str, Any]:
        """
        Verify if a citation exists and is correctly formatted.
        
        Args:
            citation: Case citation (e.g., "(2017) 9 SCC 161")
            
        Returns:
            Verification result with exists flag and correct citation
        """
        results = self.search_judgments(citation, max_results=1)
        
        if results:
            return {
                'exists': True,
                'verified_citation': results[0]['title'],
                'doc_id': results[0]['doc_id'],
                'court': results[0]['court']
            }
        else:
            return {
                'exists': False,
                'verified_citation': None,
                'error': 'Citation not found in Indian Kanoon database'
            }
    
    @lru_cache(maxsize=32)
    def search_ipc_section(self, section: str) -> Optional[Dict[str, Any]]:
        """
        Search for IPC section details.
        
        Args:
            section: IPC section number (e.g., "304A", "420")
            
        Returns:
            Section details including text and punishment
        """
        query = f"IPC Section {section}"
        results = self.search_judgments(query, max_results=3)
        
        # Look for bare act entry
        for result in results:
            if 'Indian Penal Code' in result['title'] and section in result['title']:
                doc = self.get_judgment(result['doc_id'])
                if doc:
                    return {
                        'section': section,
                        'title': result['title'],
                        'text': doc['text'][:1000],  # First 1000 chars
                        'source': 'Indian Kanoon',
                        'doc_id': result['doc_id']
                    }
        
        return None
    
    def get_recent_judgments(
        self, 
        court: str = "Supreme Court",
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent judgments from specified court.
        
        Args:
            court: Court name
            days: Get judgments from last N days
            
        Returns:
            List of recent judgment summaries
        """
        # Indian Kanoon doesn't have a direct "recent" API
        # We search with court filter and check dates
        query = f"court:\"{court}\""
        return self.search_judgments(query, max_results=10)
    
    # Helper methods
    
    @staticmethod
    def _extract_court(title: str) -> str:
        """Extract court name from judgment title."""
        title_lower = title.lower()
        if 'supreme court' in title_lower:
            return 'Supreme Court of India'
        elif 'high court' in title_lower:
            # Extract specific HC
            for hc in ['delhi', 'bombay', 'madras', 'calcutta', 'karnataka', 'kerala', 'allahabad', 'gujarat', 'telangana', 'punjab', 'rajasthan']:
                if hc in title_lower:
                    return f'{hc.capitalize()} High Court'
            return 'High Court'
        return 'Unknown'
    
    @staticmethod
    def _extract_year(title: str) -> Optional[int]:
        """Extract year from judgment title."""
        import re
        # Try finding 'on [Date] [Month], [Year]' format common in Indian Kanoon
        # e.g. "vs Union Of India on 15 February, 2024"
        date_match = re.search(r'on\s+\d+\s+\w+,\s+(\d{4})', title)
        if date_match:
            return int(date_match.group(1))
            
        # Look for year in parentheses (2024) or standalone 2024
        match = re.search(r'\((\d{4})\)|(\d{4})', title)
        if match:
            # Filter to ensure it's a reasonable year (1950-2030)
            y1, y2 = match.groups()
            year = int(y1 if y1 else y2)
            if 1950 <= year <= 2030:
                return year
        return None
    
    @staticmethod
    def _extract_citation(title: str) -> Optional[str]:
        """Extract citation from judgment title."""
        import re
        # Look for SCC citation format
        match = re.search(r'\((\d{4})\)\s+(\d+)\s+SCC\s+(\d+)', title)
        if match:
            return f"({match.group(1)}) {match.group(2)} SCC {match.group(3)}"
        return None


# Singleton instance
_indian_kanoon_client = None

def get_indian_kanoon_client() -> IndianKanoonClient:
    """Get singleton Indian Kanoon client instance."""
    global _indian_kanoon_client
    if _indian_kanoon_client is None:
        _indian_kanoon_client = IndianKanoonClient()
    return _indian_kanoon_client
