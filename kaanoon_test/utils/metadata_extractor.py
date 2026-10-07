"""
Metadata Extractor - Extract sources, dates, and publication info from documents
"""
import re
from typing import Dict, List, Optional
from datetime import datetime


class MetadataExtractor:
    """Extract metadata (URLs, dates, publications) from document text"""
    
    def __init__(self):
        # Domain to publication name mapping
        self.domain_map = {
            'theweek.in': 'The Week',
            'tconews.in': 'TC News',
            'newindianexpress.com': 'New Indian Express',
            'indiankanoon.org': 'Indian Kanoon',
            'indiankanoon.com': 'Indian Kanoon',
            'livelaw.in': 'Live Law',
            'barandbench.com': 'Bar and Bench',
            'scobserver.in': 'SC Observer',
            'theleaflet.in': 'The Leaflet',
            'timesofindia.indiatimes.com': 'Times of India',
            'hindustantimes.com': 'Hindustan Times',
            'thehindu.com': 'The Hindu',
            'ndtv.com': 'NDTV',
            'thequint.com': 'The Quint',
            'scroll.in': 'Scroll.in',
            'opindia.com': 'OpIndia',
            'thenewsminute.com': 'The News Minute',
        }
    
    def extract_sources(self, document_text: str) -> List[Dict]:
        """
        Extract source URLs and publication names from text
        
        Returns:
            List of dicts with 'url', 'publication', 'type' keys
        """
        sources = []
        seen_urls = set()
        
        # Pattern 1: Extract URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]()]+'
        urls = re.findall(url_pattern, document_text)
        
        for url in urls:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            sources.append({
                'url': url,
                'publication': self._extract_publication_from_url(url),
                'type': 'web'
            })
        
        # Pattern 2: Extract publication mentions
        # e.g., "according to The Week", "as per LiveLaw", "reported by Times of India"
        pub_pattern = r'(?:according to|as per|reported by|source:)\s+([A-Z][a-zA-Z\s]+(?:\.in|\.com|\.org)?)'
        publications = re.findall(pub_pattern, document_text, re.IGNORECASE)
        
        for pub in publications:
            pub_clean = pub.strip()
            if pub_clean and pub_clean not in [s.get('publication') for s in sources]:
                sources.append({
                    'publication': pub_clean,
                    'type': 'mention'
                })
        
        return sources
    
    def extract_dates(self, document_text: str) -> List[str]:
        """
        Extract dates from text in various formats
        
        Returns:
            List of date strings (e.g., ['Oct 2012', 'June 16, 2023'])
        """
        date_patterns = [
            # Month DD, YYYY (e.g., "June 16, 2023")
            r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b',
            
            # DD Month YYYY (e.g., "16 June 2023")
            r'\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b',
            
            # Month YYYY (e.g., "Oct 2012", "July 2025")
            r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b',
            
            # YYYY-MM-DD (ISO format)
            r'\b\d{4}-\d{2}-\d{2}\b',
            
            # DD/MM/YYYY or DD-MM-YYYY
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b',
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, document_text, re.IGNORECASE)
            dates.extend(matches)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_dates = []
        for date in dates:
            date_normalized = date.strip().lower()
            if date_normalized not in seen:
                seen.add(date_normalized)
                unique_dates.append(date.strip())
        
        return unique_dates
    
    def extract_case_citations(self, document_text: str) -> List[str]:
        """
        Extract legal case citations (e.g., "A vs B", "State v. Kumar")
        
        Returns:
            List of case citation strings
        """
        # Pattern: Name vs/v./v Name
        citation_pattern = r'\b([A-Z][a-zA-Z\s]+)\s+(?:vs?\.?|versus)\s+([A-Z][a-zA-Z\s]+)\b'
        citations = re.findall(citation_pattern, document_text)
        
        return [f"{party1.strip()} vs {party2.strip()}" for party1, party2 in citations]
    
    def extract_court_names(self, document_text: str) -> List[str]:
        """
        Extract court names from text
        
        Returns:
            List of court names
        """
        court_patterns = [
            r'\b(Supreme Court(?:\s+of\s+India)?)\b',
            r'\b([A-Z][a-z]+\s+High\s+Court)\b',
            r'\b(District\s+Court)\b',
            r'\b(Sessions?\s+Court)\b',
            r'\b(CBI\s+(?:Special\s+)?Court)\b',
        ]
        
        courts = []
        for pattern in court_patterns:
            matches = re.findall(pattern, document_text, re.IGNORECASE)
            courts.extend(matches)
        
        return list(set(courts))
    
    def _extract_publication_from_url(self, url: str) -> str:
        """Extract publication name from URL using domain mapping"""
        url_lower = url.lower()
        
        # Check each domain in our map
        for domain, name in self.domain_map.items():
            if domain in url_lower:
                return name
        
        # Fallback: extract domain name
        match = re.search(r'https?://(?:www\.)?([^/]+)', url_lower)
        if match:
            domain = match.group(1)
            # Clean up domain (remove .com, .in, etc.)
            cleaned = re.sub(r'\.(com|in|org|net|gov)$', '', domain)
            return cleaned.replace('.', ' ').title()
        
        return 'Unknown Source'
    
    def enrich_document_metadata(self, document: Dict) -> Dict:
        """
        Enrich a document dictionary with extracted metadata
        
        Args:
            document: Dict with 'text' or 'content' key
        
        Returns:
            Enhanced document dict with extracted_sources, extracted_dates, etc.
        """
        text = document.get('text') or document.get('content', '')
        
        document['extracted_sources'] = self.extract_sources(text)
        document['extracted_dates'] = self.extract_dates(text)
        document['extracted_citations'] = self.extract_case_citations(text)
        document['extracted_courts'] = self.extract_court_names(text)
        
        return document
