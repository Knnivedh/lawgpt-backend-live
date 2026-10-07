"""
Legal Data Enricher
Enriches RAG responses with verified external legal data from Indian Kanoon
"""

from typing import Dict, List, Optional, Any
import re
from .indian_kanoon_client import get_indian_kanoon_client


from typing import Dict, List, Optional, Any
import re
from .indian_kanoon_client import get_indian_kanoon_client
from .india_code_client import get_india_code_client
from .supreme_court_client import get_supreme_court_client
from .web_search_client import get_web_search_client


class LegalDataEnricher:
    """Enriches RAG responses with verified legal data from multiple official sources."""
    
    def __init__(self):
        """Initialize enricher with all API clients."""
        self.ik_client = get_indian_kanoon_client()
        self.sc_client = get_supreme_court_client()
        self.web_client = get_web_search_client()
        self.enabled = True
    
    def enrich_response(
        self, 
        question: str, 
        rag_response: str,
        rag_sources: List[Dict]
    ) -> Dict[str, Any]:
        """
        Enrich RAG response with verified external data.
        
        Args:
            question: User's question
            rag_response: Generated response from RAG
            rag_sources: Sources used by RAG
            
        Returns:
            Enriched response with verification data
        """
        if not self.enabled:
            return {
                'response': rag_response,
                'enriched': False,
                'verification': {}
            }
        
        enrichment = {
            'response': rag_response,
            'enriched': True,
            'verification': {},
            'additional_sources': []
        }
        
        try:
            # 1. Verify citations in response
            citations = self._extract_citations(rag_response)
            if citations:
                enrichment['verification']['citations'] = self._verify_citations(citations)
            
            # 2. Enrich with case law if relevant
            if self._needs_case_law_enrichment(question):
                case_law = self._fetch_relevant_case_law(question)
                if case_law:
                    enrichment['additional_sources'].extend(case_law)
                    # Optionally append to response
                    enrichment['response'] = self._append_case_law(rag_response, case_law)
            
            # 3. Verify IPC sections mentioned
            ipc_sections = self._extract_ipc_sections(rag_response)
            if ipc_sections:
                enrichment['verification']['ipc_sections'] = self._verify_ipc_sections(ipc_sections)
            
            # 4. Add recent judgments if constitutional query
            if self._is_constitutional_query(question):
                recent = self._get_recent_relevant_judgments(question)
                if recent:
                    enrichment['additional_sources'].extend(recent)
            
            # 5. Add Official Source Links (India Code / Supreme Court)
            official_links = self._get_official_links(question, rag_response)
            if official_links:
                enrichment['official_sources'] = official_links
                enrichment['response'] = self._append_official_sources(enrichment['response'], official_links)
            
            # 6. Add Paid Source Note
            enrichment['response'] += "\n\n> **Note:** For 100% professional accuracy, cross-check citations with **SCC Online** or **Manupatra** if you have a subscription."
        
        except Exception as e:
            print(f"[Enricher] Error during enrichment: {e}")
            # Return original response if enrichment fails
            enrichment['enriched'] = False
            enrichment['error'] = str(e)
        
        return enrichment

    def _get_official_links(self, question: str, response: str) -> List[Dict[str, str]]:
        """Get links to official government sources."""
        links = []
        text_to_check = (question + " " + response).lower()
        
        # Check for major Acts
        acts_to_check = ['penal code', 'criminal procedure', 'evidence act', 'juvenile justice', 'contract act']
        for act in acts_to_check:
            if act in text_to_check:
                url = self.india_code_client.get_act_url(act)
                if url:
                    links.append({
                        'title': f"Official Text: {act.title()}",
                        'url': url,
                        'source': 'India Code (Govt of India)'
                    })
        
        # Check for Supreme Court
        if 'supreme court' in text_to_check:
            links.append({
                'title': 'Supreme Court Official Judgments',
                'url': self.sc_client.get_latest_judgments_link(),
                'source': 'Supreme Court of India'
            })
            
        return links

    def _append_official_sources(self, response: str, links: List[Dict[str, str]]) -> str:
        """Append official source links to response."""
        if not links:
            return response
            
        addition = "\n\n**Official Government Sources:**\n"
        for link in links:
            addition += f"• [{link['title']}]({link['url']}) - *{link['source']}*\n"
        return response + addition
    
    def _extract_citations(self, text: str) -> List[str]:
        """Extract case citations from text."""
        # Pattern: (YYYY) VOL SCC PAGE
        pattern = r'\((\d{4})\)\s+(\d+)\s+SCC\s+(\d+)'
        matches = re.findall(pattern, text)
        return [f"({year}) {vol} SCC {page}" for year, vol, page in matches]
    
    def _verify_citations(self, citations: List[str]) -> Dict[str, Any]:
        """Verify each citation against Indian Kanoon."""
        verification_results = {}
        
        for citation in citations:
            try:
                result = self.ik_client.verify_citation(citation)
                verification_results[citation] = {
                    'verified': result['exists'],
                    'correct_citation': result.get('verified_citation'),
                    'source': 'Indian Kanoon'
                }
            except Exception as e:
                verification_results[citation] = {
                    'verified': False,
                    'error': str(e)
                }
        
        return verification_results
    
    def _extract_ipc_sections(self, text: str) -> List[str]:
        """Extract IPC section numbers from text."""
        # Pattern: IPC Section XXX or Section XXX, IPC
        pattern = r'(?:IPC\s+Section\s+|Section\s+)(\d+[A-Z]?)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        return list(set(matches))  # Unique sections
    
    def _verify_ipc_sections(self, sections: List[str]) -> Dict[str, Any]:
        """Verify IPC sections against Indian Kanoon."""
        verification_results = {}
        
        for section in sections:
            try:
                result = self.ik_client.search_ipc_section(section)
                if result:
                    verification_results[section] = {
                        'verified': True,
                        'title': result['title'],
                        'preview': result['text'][:200],
                        'source': 'Indian Kanoon'
                    }
                else:
                    verification_results[section] = {
                        'verified': False,
                        'note': 'Section not found in Indian Kanoon'
                    }
            except Exception as e:
                verification_results[section] = {
                    'verified': False,
                    'error': str(e)
                }
        
        return verification_results
    
    def _needs_case_law_enrichment(self, question: str) -> bool:
        """Determine if question needs case law enrichment."""
        keywords = ['precedent', 'judgment', 'case law', 'supreme court', 'high court']
        return any(kw in question.lower() for kw in keywords)
    
    def _is_constitutional_query(self, question: str) -> bool:
        """Check if query is about constitutional law."""
        keywords = ['article', 'constitution', 'fundamental right', 'directive principle']
        return any(kw in question.lower() for kw in keywords)
    
    def _fetch_relevant_case_law(self, question: str) -> List[Dict[str, Any]]:
        """Fetch relevant case law from Indian Kanoon."""
        try:
            # Extract key terms for search
            search_query = self._extract_search_terms(question)
            results = self.ik_client.search_judgments(search_query, max_results=3)
            
            return [{
                'type': 'case_law',
                'title': r['title'],
                'court': r['court'],
                'year': r['year'],
                'snippet': r.get('snippet', ''),
                'source': 'Indian Kanoon',
                'doc_id': r['doc_id']
            } for r in results]
        
        except Exception as e:
            print(f"[Enricher] Case law fetch error: {e}")
            return []
    
    def _get_recent_relevant_judgments(self, question: str) -> List[Dict[str, Any]]:
        """Get recent relevant judgments."""
        try:
            # For constitutional queries, get recent SC judgments
            recent = self.ik_client.get_recent_judgments("Supreme Court", days=90)
            
            # Filter by relevance to question
            relevant = []
            question_terms = set(question.lower().split())
            
            for judgment in recent[:5]:
                title_terms = set(judgment['title'].lower().split())
                # Simple relevance check
                if len(question_terms & title_terms) >= 2:
                    relevant.append({
                        'type': 'recent_judgment',
                        'title': judgment['title'],
                        'court': judgment['court'],
                        'year': judgment['year'],
                        'source': 'Indian Kanoon (Recent)',
                        'doc_id': judgment['doc_id']
                    })
            
            return relevant[:2]  # Max 2 recent judgments
        
        except Exception as e:
            print(f"[Enricher] Recent judgments error: {e}")
            return []
    
    def _extract_search_terms(self, question: str) -> str:
        """Extract key search terms from question."""
        # Remove common words
        stopwords = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or'}
        words = [w for w in question.lower().split() if w not in stopwords]
        return ' '.join(words[:8])  # Max 8 keywords
    
    def _append_case_law(self, response: str, case_law: List[Dict]) -> str:
        """Append verified case law to response."""
        if not case_law:
            return response
        
        addition = "\n\n**Additional Relevant Case Law (from Indian Kanoon):**\n"
        for i, case in enumerate(case_law, 1):
            addition += f"{i}. *{case['title']}* - {case['court']}, {case['year']}\n"
        
        return response + addition

    def get_web_context(self, question: str) -> str:
        """
        Perform a live web search and return a formatted context string.
        Used for 'out of syllabus' or trending queries.
        """
        try:
            results = self.web_client.search(question, max_results=5)
            if not results:
                return ""
                
            context = "WEB SEARCH RESULTS (For recent/trending topics):\n\n"
            for i, res in enumerate(results, 1):
                context += f"Source {i}: {res['title']}\n"
                context += f"URL: {res['link']}\n"
                context += f"Snippet: {res['snippet']}\n\n"
                
            return context
        except Exception as e:
            print(f"[Enricher] Web search error: {e}")
            return ""


# Singleton instance
_enricher = None

def get_legal_enricher() -> LegalDataEnricher:
    """Get singleton legal enricher instance."""
    global _enricher
    if _enricher is None:
        _enricher = LegalDataEnricher()
    return _enricher
