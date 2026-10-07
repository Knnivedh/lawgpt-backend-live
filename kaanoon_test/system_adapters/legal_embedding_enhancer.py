"""
LEGAL EMBEDDING ENHANCER - Legal-Domain Query Optimization
Enhances queries with legal terminology, abbreviations, synonyms, and related sections
"""

import re
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class LegalEmbeddingEnhancer:
    """
    Enhances queries for legal-domain retrieval by:
    1. Expanding legal abbreviations (IPC → Indian Penal Code)
    2. Adding legal synonyms (theft → larceny, murder → homicide)
    3. Normalizing legal terminology
    4. Including related sections (Section 302 → also search 304, 307)
    5. Handling Latin maxims and legal jargon
    """
    
    def __init__(self):
        """Initialize legal term mappings and patterns"""
        
        # Legal abbreviation expansions
        self.legal_abbreviations = {
            'IPC': ['Indian Penal Code', 'IPC', 'Penal Code'],
            'CrPC': ['Code of Criminal Procedure', 'CrPC', 'Criminal Procedure Code', 'Criminal Procedure'],
            'CPC': ['Code of Civil Procedure', 'CPC', 'Civil Procedure Code', 'Civil Procedure'],
            'CrPC': ['Code of Criminal Procedure', 'CrPC'],
            'IEA': ['Indian Evidence Act', 'Evidence Act', 'IEA'],
            'FIR': ['First Information Report', 'FIR', 'Section 154 CrPC'],
            'SC': ['Supreme Court', 'SC', 'Apex Court'],
            'HC': ['High Court', 'HC'],
            'NCLT': ['National Company Law Tribunal', 'NCLT'],
            'NCLAT': ['National Company Law Appellate Tribunal', 'NCLAT'],
            'RERA': ['Real Estate Regulatory Authority', 'RERA'],
            'CAT': ['Central Administrative Tribunal', 'CAT'],
            'ADR': ['Alternative Dispute Resolution', 'ADR', 'Arbitration', 'Mediation'],
            'POCSO': ['Protection of Children from Sexual Offences Act', 'POCSO'],
            'IT Act': ['Information Technology Act', 'IT Act', 'Cyber Law'],
            'GST': ['Goods and Services Tax', 'GST'],
            'RTI': ['Right to Information', 'RTI'],
        }
        
        # Legal synonyms mapping
        self.legal_synonyms = {
            'murder': ['homicide', 'killing', 'culpable homicide', 'IPC 302', 'Section 302'],
            'theft': ['stealing', 'larceny', 'IPC 379', 'Section 379', 'theft of property'],
            'fraud': ['cheating', 'deception', 'IPC 420', 'Section 420', 'criminal breach of trust'],
            'property': ['real estate', 'land', 'immovable property', 'movable property', 'asset'],
            'will': ['testament', 'succession', 'inheritance', 'bequest'],
            'divorce': ['dissolution of marriage', 'separation', 'matrimonial dispute'],
            'custody': ['guardianship', 'child custody', 'care and control'],
            'bail': ['surety', 'bond', 'release', 'anticipatory bail'],
            'arrest': ['apprehension', 'detention', 'custody'],
            'trial': ['proceedings', 'hearing', 'adjudication'],
            'judgment': ['order', 'decree', 'verdict', 'decision'],
            'appeal': ['challenge', 'revision', 'petition'],
            'writ': ['constitutional remedy', 'mandamus', 'habeas corpus', 'certiorari'],
            'contract': ['agreement', 'deed', 'covenant'],
            'lease': ['tenancy', 'rental', 'license'],
            'possession': ['occupation', 'control', 'custody'],
            'ownership': ['title', 'proprietorship', 'right'],
            'evidence': ['proof', 'testimony', 'document', 'witness'],
            'witness': ['deponent', 'testifier', 'examiner'],
            'cross-examination': ['cross', 'interrogation', 'questioning'],
        }
        
        # Related IPC sections mapping (for query expansion)
        self.related_sections = {
            '302': ['304', '307', '308', '300', '299'],  # Murder → Culpable homicide, Attempt
            '304': ['302', '299', '300'],  # Culpable homicide → Murder
            '307': ['302', '308', '309'],  # Attempt to murder → Murder, Attempt to suicide
            '379': ['380', '381', '382'],  # Theft → Theft in dwelling, Preparation
            '420': ['415', '416', '417', '418'],  # Cheating → Cheating, Forgery
            '406': ['405', '407', '408', '409'],  # Criminal breach of trust → CBT variants
            '376': ['376A', '376B', '376C', '376D', '376E'],  # Rape → Rape variants
            '498A': ['304B', '306'],  # Dowry → Dowry death, Abetment
            '138': ['139', '140', '141', '142'],  # NI Act → Negotiable Instruments
        }
        
        # Latin maxims and their meanings
        self.latin_maxims = {
            'res judicata': ['res judicata', 'final judgment', 'already decided'],
            'stare decisis': ['stare decisis', 'precedent', 'binding precedent'],
            'habeas corpus': ['habeas corpus', 'produce the body', 'personal liberty'],
            'actus reus': ['actus reus', 'guilty act', 'criminal act'],
            'mens rea': ['mens rea', 'guilty mind', 'criminal intent'],
            'bona fide': ['bona fide', 'good faith', 'genuine'],
            'mala fide': ['mala fide', 'bad faith', 'fraudulent'],
            'prima facie': ['prima facie', 'at first sight', 'apparent'],
            'ultra vires': ['ultra vires', 'beyond powers', 'unauthorized'],
            'intra vires': ['intra vires', 'within powers', 'authorized'],
            'ex parte': ['ex parte', 'one party', 'without notice'],
            'ad interim': ['ad interim', 'temporary', 'interim'],
            'ex post facto': ['ex post facto', 'retroactive', 'after the fact'],
            'pro bono': ['pro bono', 'free legal service', 'public service'],
            'amicus curiae': ['amicus curiae', 'friend of court', 'expert opinion'],
        }
        
        # Legal term normalization patterns
        self.normalization_patterns = {
            r'\bipc\s*(\d+[a-z]?)\b': r'IPC Section \1',
            r'\bsection\s*(\d+[a-z]?)\s*ipc\b': r'IPC Section \1',
            r'\bipc\s*section\s*(\d+[a-z]?)\b': r'IPC Section \1',
            r'\bsection\s*(\d+[a-z]?)\b': r'Section \1',
            r'\bart\.\s*(\d+)\b': r'Article \1',
            r'\barticle\s*(\d+)\b': r'Article \1',
            r'\border\s*(\d+)\b': r'Order \1',
            r'\brule\s*(\d+)\b': r'Rule \1',
        }
    
    def enhance_query(self, query: str) -> str:
        """
        Enhance query with legal terminology expansion
        
        Args:
            query: Original query string
            
        Returns:
            Enhanced query with expanded terms
        """
        enhanced = query
        
        # Step 1: Expand legal abbreviations
        enhanced = self._expand_legal_abbreviations(enhanced)
        
        # Step 2: Add legal synonyms
        enhanced = self._add_legal_synonyms(enhanced)
        
        # Step 3: Add related sections
        enhanced = self._add_related_sections(enhanced)
        
        # Step 4: Expand Latin maxims
        enhanced = self._expand_latin_maxims(enhanced)
        
        return enhanced
    
    def _expand_legal_abbreviations(self, query: str) -> str:
        """Expand legal abbreviations in query"""
        expanded = query
        query_upper = query.upper()
        
        for abbrev, expansions in self.legal_abbreviations.items():
            if abbrev in query_upper:
                # Add expansions if not already present
                for expansion in expansions:
                    if expansion.lower() not in query.lower():
                        expanded += f" {expansion}"
        
        return expanded
    
    def _add_legal_synonyms(self, query: str) -> str:
        """Add legal synonyms to query"""
        expanded = query
        query_lower = query.lower()
        
        for term, synonyms in self.legal_synonyms.items():
            if term in query_lower:
                # Add synonyms that aren't already in query
                for synonym in synonyms:
                    if synonym.lower() not in query_lower:
                        expanded += f" {synonym}"
        
        return expanded
    
    def _add_related_sections(self, query: str) -> str:
        """Add related IPC sections to query"""
        expanded = query
        
        # Extract IPC section numbers
        ipc_pattern = r'(?:IPC|Section)\s*(\d+[a-z]?)'
        matches = re.findall(ipc_pattern, query, re.IGNORECASE)
        
        for section_num in matches:
            if section_num in self.related_sections:
                related = self.related_sections[section_num]
                for related_section in related:
                    if f"Section {related_section}" not in expanded and f"IPC {related_section}" not in expanded:
                        expanded += f" IPC Section {related_section}"
        
        return expanded
    
    def _expand_latin_maxims(self, query: str) -> str:
        """Expand Latin maxims with their meanings"""
        expanded = query
        query_lower = query.lower()
        
        for maxim, meanings in self.latin_maxims.items():
            if maxim in query_lower:
                for meaning in meanings:
                    if meaning.lower() not in query_lower:
                        expanded += f" {meaning}"
        
        return expanded
    
    def normalize_legal_terms(self, query: str) -> str:
        """
        Normalize legal terminology in query
        
        Args:
            query: Input query
            
        Returns:
            Normalized query
        """
        normalized = query
        
        # Apply normalization patterns
        for pattern, replacement in self.normalization_patterns.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized
    
    def get_enhanced_query_pair(self, query: str) -> Tuple[str, str]:
        """
        Get both normalized and enhanced query
        
        Args:
            query: Original query
            
        Returns:
            Tuple of (normalized_query, enhanced_query)
        """
        normalized = self.normalize_legal_terms(query)
        enhanced = self.enhance_query(query)
        
        return normalized, enhanced
    
    def extract_legal_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extract legal entities from query (sections, acts, cases)
        
        Args:
            query: Input query
            
        Returns:
            Dictionary with extracted entities
        """
        entities = {
            'ipc_sections': [],
            'cpc_sections': [],
            'crpc_sections': [],
            'articles': [],
            'acts': [],
            'cases': []
        }
        
        # Extract IPC sections
        ipc_pattern = r'(?:IPC|Indian Penal Code).*?Section\s*(\d+[a-z]?)'
        entities['ipc_sections'] = re.findall(ipc_pattern, query, re.IGNORECASE)
        
        # Extract CPC sections/orders/rules
        cpc_pattern = r'(?:CPC|Civil Procedure Code).*?(?:Section|Order|Rule)\s*(\d+[a-z]?)'
        entities['cpc_sections'] = re.findall(cpc_pattern, query, re.IGNORECASE)
        
        # Extract CrPC sections
        crpc_pattern = r'(?:CrPC|Criminal Procedure Code).*?Section\s*(\d+[a-z]?)'
        entities['crpc_sections'] = re.findall(crpc_pattern, query, re.IGNORECASE)
        
        # Extract Constitutional Articles
        article_pattern = r'Article\s*(\d+[a-z]?)'
        entities['articles'] = re.findall(article_pattern, query, re.IGNORECASE)
        
        # Extract Acts
        act_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act'
        entities['acts'] = re.findall(act_pattern, query)
        
        # Extract case names (basic pattern)
        case_pattern = r'([A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+)'
        entities['cases'] = re.findall(case_pattern, query)
        
        return entities

