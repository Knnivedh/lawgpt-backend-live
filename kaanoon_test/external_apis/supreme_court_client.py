"""
Supreme Court of India Client
Fetches official judgments and daily orders from main.sci.gov.in and eSCR
"""

import requests
from typing import Dict, List, Optional, Any
from functools import lru_cache
import datetime

class SupremeCourtClient:
    """Client for Supreme Court Official Website & eSCR."""
    
    SCI_BASE_URL = "https://main.sci.gov.in"
    ESCR_BASE_URL = "https://escr.supremecourt.gov.in"
    
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_latest_judgments_link(self) -> str:
        """Get link to the latest judgments page."""
        return f"{self.SCI_BASE_URL}/judgments"
    
    def get_escr_search_link(self, query: str) -> str:
        """Get direct search link for eSCR."""
        # eSCR uses a specific search format, but we can direct users to the search page
        return f"{self.ESCR_BASE_URL}/?q={query}"
    
    def verify_official_citation(self, citation: str) -> Dict[str, Any]:
        """
        Check if a citation format matches official SCR citation.
        e.g., '2017 10 SCC 1' is SCC, but '2017 SCR 1' is official.
        """
        is_scr = 'SCR' in citation
        return {
            'is_official_scr': is_scr,
            'source': 'Supreme Court Reports (Official)' if is_scr else 'Private Journal',
            'search_url': self.get_escr_search_link(citation)
        }

# Singleton
_sc_client = None

def get_supreme_court_client() -> SupremeCourtClient:
    global _sc_client
    if _sc_client is None:
        _sc_client = SupremeCourtClient()
    return _sc_client
