"""
CITATION EXTRACTOR - Enhanced Citation Extraction and Validation
Extracts, validates, and formats legal citations (IPC sections, case law, statutes)
with special focus on preventing truncation errors
"""

import re
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class CitationExtractor:
    """
    Specialized citation extractor that:
    - Extracts IPC sections with complete numbers (prevents truncation)
    - Identifies case law citations (Supreme Court, High Court)
    - Formats citations properly
    - Validates citation accuracy
    - Groups citations by type
    """
    
    def __init__(self):
        """Initialize citation extractor"""
        # IPC section pattern (complete numbers only)
        self.ipc_pattern = r'(?:IPC|Indian Penal Code).*?Section\s*(\d+[a-z]?)'
        self.ipc_full_pattern = r'IPC\s*Section\s*(\d+[a-z]?)'
        
        # Case citation patterns
        self.case_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\((\d{4})\)(?:\s+(\d+)\s+([A-Z]+)\s+(\d+))?'
        
        # Truncation detection patterns
        self.truncation_patterns = [
            r'IPC\s*\d{1,2}\.\.\.',  # IPC 30...
            r'IPC\s*\d{1,2}\s*\.\.\.',  # IPC 30 ...
            r'Section\s*\d{1,2}\.\.\.',  # Section 30...
            r'Section\s*\d{1,2}\s*\.\.\.',  # Section 30 ...
        ]
        
        # Valid IPC section numbers (common ones)
        self.valid_ipc_sections = {
            '302', '304', '307', '308', '300', '299', '379', '380', '381', '382',
            '420', '415', '416', '417', '418', '406', '405', '407', '408', '409',
            '376', '376A', '376B', '376C', '376D', '376E', '498A', '304B', '306',
            '138', '139', '140', '141', '142', '120B', '34', '149'
        }
    
    def extract_citations(self, text: str) -> Dict[str, List[str]]:
        """
        Extract all citations from text
        
        Args:
            text: Text to extract citations from
            
        Returns:
            Dictionary with extracted citations by type
        """
        citations = {
            'ipc_sections': [],
            'case_law': [],
            'statutes': [],
            'articles': [],
            'cpc_sections': [],
            'crpc_sections': [],
            'orders': [],
            'rules': []
        }
        
        # Extract IPC sections
        citations['ipc_sections'] = self._extract_ipc_sections(text)
        
        # Extract case law
        citations['case_law'] = self._extract_case_citations(text)
        
        # Extract statutes
        citations['statutes'] = self._extract_statutes(text)
        
        # Extract constitutional articles
        citations['articles'] = self._extract_constitutional_articles(text)
        
        # Extract CPC sections/orders/rules
        cpc_data = self._extract_cpc_citations(text)
        citations['cpc_sections'] = cpc_data['sections']
        citations['orders'] = cpc_data['orders']
        citations['rules'] = cpc_data['rules']
        
        # Extract CrPC sections
        citations['crpc_sections'] = self._extract_crpc_sections(text)
        
        return citations
    
    def _extract_ipc_sections(self, text: str) -> List[str]:
        """Extract IPC sections with complete numbers"""
        sections = []
        
        # Pattern 1: "IPC Section 302" or "IPC Section 302A"
        matches = re.findall(self.ipc_full_pattern, text, re.IGNORECASE)
        sections.extend([f"IPC Section {m}" for m in matches])
        
        # Pattern 2: "Section 302 IPC" or "Section 302 of IPC"
        pattern2 = r'Section\s*(\d+[a-z]?)\s+(?:of\s+)?IPC'
        matches2 = re.findall(pattern2, text, re.IGNORECASE)
        sections.extend([f"IPC Section {m}" for m in matches2])
        
        # Pattern 3: "IPC 302" (without "Section")
        pattern3 = r'\bIPC\s+(\d+[a-z]?)\b'
        matches3 = re.findall(pattern3, text, re.IGNORECASE)
        sections.extend([f"IPC Section {m}" for m in matches3])
        
        # Remove duplicates and sort
        sections = list(set(sections))
        sections.sort()
        
        return sections
    
    def _extract_case_citations(self, text: str) -> List[Dict]:
        """Extract case law citations"""
        cases = []
        
        # Full citation pattern: "Case Name v. Respondent (Year) Volume Reporter Page"
        matches = re.finditer(self.case_pattern, text)
        
        for match in matches:
            petitioner, respondent, year, volume, reporter, page = match.groups()
            
            case_name = f"{petitioner} v. {respondent}"
            citation = {
                'case_name': case_name,
                'petitioner': petitioner,
                'respondent': respondent,
                'year': year,
                'full_citation': match.group(0)
            }
            
            if volume and reporter and page:
                citation['volume'] = volume
                citation['reporter'] = reporter
                citation['page'] = page
                citation['formatted'] = f"{case_name} ({year}) {volume} {reporter} {page}"
            else:
                citation['formatted'] = f"{case_name} ({year})"
            
            cases.append(citation)
        
        # Also look for simple case names: "Case Name v. Respondent"
        simple_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        simple_matches = re.finditer(simple_pattern, text)
        
        for match in simple_matches:
            case_name = match.group(0)
            # Check if not already in cases
            if not any(c['case_name'] == case_name for c in cases):
                cases.append({
                    'case_name': case_name,
                    'formatted': case_name,
                    'full_citation': case_name
                })
        
        return cases
    
    def _extract_statutes(self, text: str) -> List[str]:
        """Extract statute/Act references"""
        statutes = []
        
        # Pattern: "Act Name Act, Year" or "Act Name Act"
        pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act(?:\s*,?\s*(\d{4}))?'
        matches = re.finditer(pattern, text)
        
        for match in matches:
            act_name = match.group(1)
            year = match.group(2)
            
            if year:
                formatted = f"{act_name} Act, {year}"
            else:
                formatted = f"{act_name} Act"
            
            if formatted not in statutes:
                statutes.append(formatted)
        
        return statutes
    
    def _extract_constitutional_articles(self, text: str) -> List[str]:
        """Extract Constitutional Article references"""
        articles = []
        
        # Pattern: "Article 21" or "Article 21 of the Constitution"
        pattern = r'Article\s*(\d+[a-z]?)(?:\s+of\s+the\s+Constitution)?'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        articles = [f"Article {m}" for m in matches]
        articles = list(set(articles))
        articles.sort()
        
        return articles
    
    def _extract_cpc_citations(self, text: str) -> Dict[str, List[str]]:
        """Extract CPC sections, orders, and rules"""
        result = {
            'sections': [],
            'orders': [],
            'rules': []
        }
        
        # CPC Sections
        pattern = r'(?:CPC|Civil Procedure Code).*?Section\s*(\d+[a-z]?)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        result['sections'] = [f"CPC Section {m}" for m in matches]
        
        # Orders
        order_pattern = r'(?:CPC|Civil Procedure Code).*?Order\s*(\d+[a-z]?)'
        order_matches = re.findall(order_pattern, text, re.IGNORECASE)
        result['orders'] = [f"CPC Order {m}" for m in order_matches]
        
        # Rules
        rule_pattern = r'(?:CPC|Civil Procedure Code).*?Rule\s*(\d+[a-z]?)'
        rule_matches = re.findall(rule_pattern, text, re.IGNORECASE)
        result['rules'] = [f"CPC Rule {m}" for m in rule_matches]
        
        # Also standalone Order/Rule references
        standalone_order = r'Order\s*(\d+[a-z]?)'
        standalone_rule = r'Rule\s*(\d+[a-z]?)'
        
        standalone_orders = re.findall(standalone_order, text, re.IGNORECASE)
        standalone_rules = re.findall(standalone_rule, text, re.IGNORECASE)
        
        result['orders'].extend([f"Order {m}" for m in standalone_orders])
        result['rules'].extend([f"Rule {m}" for m in standalone_rules])
        
        # Remove duplicates
        result['sections'] = list(set(result['sections']))
        result['orders'] = list(set(result['orders']))
        result['rules'] = list(set(result['rules']))
        
        return result
    
    def _extract_crpc_sections(self, text: str) -> List[str]:
        """Extract CrPC sections"""
        sections = []
        
        pattern = r'(?:CrPC|Criminal Procedure Code).*?Section\s*(\d+[a-z]?)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        sections = [f"CrPC Section {m}" for m in matches]
        
        sections = list(set(sections))
        sections.sort()
        
        return sections
    
    @staticmethod
    def _normalize_case_text(value: str) -> str:
        """Normalise a case name so real citations match retrieved text.

        Retrieved text varies in punctuation and connective style
        ("Basalingappa vs. State of Karnataka" vs "Basalingappa v. State of
        Karnataka", italic markers, extra whitespace). The previous raw substring
        test failed on those, so every genuine case was reported as
        missing_from_context and the caller then stripped it out of the answer.
        """
        text = str(value or "").lower()
        text = text.replace("&", " and ")
        text = re.sub(r"\bvs\.?\b", " v ", text)
        text = re.sub(r"\bv\.?\b", " v ", text)
        text = re.sub(r"[*_`]", " ", text)
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _case_present_in_context(cls, case_name: str, context_text: str) -> bool:
        """True when the case genuinely appears in the retrieved context.

        Accepts the citation when the distinctive party surnames co-occur, which
        tolerates the connective and punctuation differences that made the old
        exact-substring test fail on real cases.
        """
        needle = cls._normalize_case_text(case_name)
        hay = cls._normalize_case_text(context_text)
        if not needle:
            return False
        if needle in hay:
            return True
        # Drop connective/common party words so they cannot create a false match.
        tokens = [t for t in needle.split() if t not in {"v", "and", "the", "of", "state"}]
        tokens = [t for t in tokens if len(t) > 2]
        if not tokens:
            return False
        distinctive = sorted(set(tokens), key=len, reverse=True)[:2]
        return all(tok in hay for tok in distinctive)

    def validate_citations(
        self,
        citations: Dict,
        context: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Validate citations against context
        
        Args:
            citations: Extracted citations
            context: Retrieved documents for validation
            
        Returns:
            Dictionary with validated citations and errors
        """
        validated = {
            'valid': [],
            'invalid': [],
            'truncated': [],
            'missing_from_context': []
        }
        
        # Check for truncation errors
        context_text = " ".join([str(d.get('text', '')) for d in context])
        
        for pattern in self.truncation_patterns:
            matches = re.findall(pattern, context_text, re.IGNORECASE)
            if matches:
                validated['truncated'].extend(matches)
        
        # Validate IPC sections
        for ipc_section in citations.get('ipc_sections', []):
            # Extract section number
            section_num = re.search(r'(\d+[a-z]?)', ipc_section)
            if section_num:
                section_num = section_num.group(1)
                
                # Check if complete (not truncated)
                if '...' in ipc_section or len(section_num) < 3:
                    validated['truncated'].append({
                        'citation': ipc_section,
                        'type': 'IPC Section',
                        'error': 'Truncated section number'
                    })
                else:
                    # Check if exists in context
                    if ipc_section.lower() in context_text.lower():
                        validated['valid'].append({
                            'citation': ipc_section,
                            'type': 'IPC Section',
                            'status': 'valid'
                        })
                    else:
                        validated['missing_from_context'].append({
                            'citation': ipc_section,
                            'type': 'IPC Section',
                            'error': 'Not found in context'
                        })
        
        # Validate case citations
        for case in citations.get('case_law', []):
            case_name = case.get('case_name', '')
            if self._case_present_in_context(case_name, context_text):
                validated['valid'].append({
                    'citation': case.get('formatted', case_name),
                    'type': 'Case Law',
                    'status': 'valid'
                })
            else:
                validated['missing_from_context'].append({
                    'citation': case.get('formatted', case_name),
                    'type': 'Case Law',
                    'error': 'Not found in context'
                })
        
        return validated
    
    def fix_truncated_citations(self, text: str, context: List[Dict]) -> str:
        """
        Fix truncated citations in text using context
        
        Args:
            text: Text with potentially truncated citations
            context: Context documents to find complete citations
            
        Returns:
            Text with fixed citations
        """
        fixed_text = text
        
        # Search context for complete IPC sections
        context_text = " ".join([str(d.get('text', '')) for d in context])
        
        # Find truncated patterns
        for pattern in self.truncation_patterns:
            matches = re.finditer(pattern, fixed_text, re.IGNORECASE)
            for match in matches:
                truncated = match.group(0)
                
                # Try to find complete version in context
                # Extract partial number
                partial_num = re.search(r'(\d{1,2})', truncated)
                if partial_num:
                    partial = partial_num.group(1)
                    
                    # Search for complete sections starting with this number
                    complete_pattern = rf'IPC\s*Section\s*({partial}\d+[a-z]?)'
                    complete_matches = re.findall(complete_pattern, context_text, re.IGNORECASE)
                    
                    if complete_matches:
                        # Use the most common one
                        complete_section = max(set(complete_matches), key=complete_matches.count)
                        fixed_text = fixed_text.replace(
                            truncated,
                            f"IPC Section {complete_section}"
                        )
        
        return fixed_text
    
    def format_citations_summary(self, citations: Dict) -> str:
        """Format citations into a readable summary"""
        summary_parts = []
        
        if citations.get('ipc_sections'):
            summary_parts.append(f"IPC Sections: {', '.join(citations['ipc_sections'][:10])}")
        
        if citations.get('case_law'):
            case_names = [c.get('formatted', c.get('case_name', '')) for c in citations['case_law'][:5]]
            summary_parts.append(f"Case Law: {', '.join(case_names)}")
        
        if citations.get('statutes'):
            summary_parts.append(f"Acts: {', '.join(citations['statutes'][:5])}")
        
        if citations.get('articles'):
            summary_parts.append(f"Constitutional Articles: {', '.join(citations['articles'][:5])}")
        
        return "\n".join(summary_parts) if summary_parts else "No citations found"

