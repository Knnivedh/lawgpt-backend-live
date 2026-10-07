"""
LEGAL TOKENIZER - Improved tokenization for legal text
Fixes: Basic .lower().split() tokenization - adds legal preprocessing
"""

import re
from typing import List
import string


class LegalTokenizer:
    """
    Advanced tokenizer for Indian legal text
    
    Features:
    1. Preserves legal entities (IPC 302, Article 21, etc.)
    2. Handles abbreviations (CrPC, IPC, etc.)
    3. Normalizes legal terms
    4. Removes stopwords but keeps legal stopwords
    5. Handles numbers in legal context
    """
    
    def __init__(self):
        """Initialize tokenizer with legal-specific rules"""
        
        # Legal entities to preserve as single tokens
        self.legal_entity_patterns = [
            r'IPC\s+(?:Section\s+)?(\d+[A-Z]{0,2})',  # IPC sections
            r'Article\s+(\d+[A-Z]?)',  # Constitutional articles
            r'Section\s+(\d+[A-Z]{0,2})',  # Generic sections
            r'Cr\.?P\.?C\.?',  # CrPC
            r'C\.?P\.?C\.?',  # CPC
            r'(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act(?:,?\s+\d{4})?',  # Acts with year
            r'[A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',  # Case names
        ]
        
        # Compile patterns
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.legal_entity_patterns]
        
        # Legal abbreviations to normalize
        self.legal_abbrev_map = {
            'ipc': 'indian_penal_code',
            'crpc': 'criminal_procedure_code',
            'cpc': 'civil_procedure_code',
            'sc': 'supreme_court',
            'hc': 'high_court',
            'fir': 'first_information_report',
            'pil': 'public_interest_litigation',
            'suo': 'suo_moto',
            'ngo': 'non_governmental_organization',
        }
        
        # Common stopwords to remove (but keep legal ones)
        self.stopwords = set([
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'what', 'which', 'who', 'when', 'where', 'why', 'how'
        ])
        
        # Legal stopwords to KEEP (important for context)
        self.legal_keepwords = set([
            'not', 'no', 'if', 'under', 'unless', 'provided', 'except', 
            'subject', 'notwithstanding', 'shall', 'may', 'must',
            'liable', 'guilty', 'accused', 'plaintiff', 'defendant',
            'petition', 'appeal', 'writ', 'bail', 'custody',
        ])
    
    def extract_legal_entities(self, text: str) -> List[str]:
        """
        Extract and preserve legal entities as tokens
        
        Args:
            text: Input text
            
        Returns:
            List of legal entities found
        """
        entities = []
        
        for pattern in self.compiled_patterns:
            matches = pattern.findall(text)
            
            if matches:
                if isinstance(matches[0], tuple):
                    # Pattern with groups
                    for match in matches:
                        if match:
                            entities.append(match[0] if isinstance(match, tuple) else match)
                else:
                    entities.extend(matches)
        
        # Normalize entities
        normalized = []
        for entity in entities:
            # Convert to lowercase and replace spaces with underscores
            normalized.append(entity.lower().replace(' ', '_'))
        
        return normalized
    
    def normalize_legal_terms(self, token: str) -> str:
        """
        Normalize legal abbreviations and terms
        
        Args:
            token: Single token
            
        Returns:
            Normalized token
        """
        token_lower = token.lower()
        
        # Check if it's a known abbreviation
        if token_lower in self.legal_abbrev_map:
            return self.legal_abbrev_map[token_lower]
        
        return token_lower
    
    def tokenize(self, text: str, preserve_entities: bool = True) -> List[str]:
        """
        Tokenize legal text with legal-specific preprocessing
        
        Args:
            text: Input text
            preserve_entities: Whether to preserve legal entities
            
        Returns:
            List of tokens
        """
        if not text:
            return []
        
        tokens = []
        
        # Step 1: Extract and preserve legal entities
        if preserve_entities:
            entities = self.extract_legal_entities(text)
            tokens.extend(entities)
        
        # Step 2: Basic tokenization
        # Remove punctuation except periods in abbreviations
        text_clean = text.lower()
        
        # Preserve abbreviations (e.g., "Cr.P.C." -> "crpc")
        text_clean = re.sub(r'([A-Z])\.([A-Z])\.([A-Z])\.', r'\1\2\3', text_clean, flags=re.IGNORECASE)
        
        # Remove other punctuation
        text_clean = text_clean.translate(str.maketrans('', '', string.punctuation.replace('_', '')))
        
        # Split on whitespace
        basic_tokens = text_clean.split()
        
        # Step 3: Normalize and filter
        for token in basic_tokens:
            # Skip very short tokens
            if len(token) < 2:
                continue
            
            # Normalize legal terms
            normalized = self.normalize_legal_terms(token)
            
            # Remove stopwords (except legal keepwords)
            if normalized in self.stopwords and normalized not in self.legal_keepwords:
                continue
            
            tokens.append(normalized)
        
        return tokens
    
    def tokenize_batch(self, texts: List[str]) -> List[List[str]]:
        """
        Tokenize multiple texts
        
        Args:
            texts: List of text strings
            
        Returns:
            List of token lists
        """
        return [self.tokenize(text) for text in texts]


# Example usage and testing
if __name__ == "__main__":
    tokenizer = LegalTokenizer()
    
    # Test cases
    test_texts = [
        "What is IPC Section 302?",
        "The Supreme Court held in Bachan Singh v. State of Punjab that...",
        "Under Article 21 of the Constitution, every person has the right to life",
        "File FIR under Cr.P.C. Section 154 for theft under IPC 379"
    ]
    
    print("LEGAL TOKENIZER - Test Results")
    print("="*60)
    
    for text in test_texts:
        tokens = tokenizer.tokenize(text)
        print(f"\nText: {text}")
        print(f"Tokens: {tokens}")
        print(f"Count: {len(tokens)}")
    
    # Compare with basic tokenization
    print("\n\n" + "="*60)
    print("COMPARISON: Legal Tokenizer vs Basic .lower().split()")
    print("="*60)
    
    text = "IPC Section 302 and CrPC Section 41 apply in murder cases under Supreme Court guidelines"
    
    basic_tokens = text.lower().split()
    legal_tokens = tokenizer.tokenize(text)
    
    print(f"\nText: {text}")
    print(f"\nBasic tokens ({len(basic_tokens)}): {basic_tokens}")
    print(f"\nLegal tokens ({len(legal_tokens)}): {legal_tokens}")
    
    print("\n✓ Legal tokenizer preserves legal entities and removes stopwords")

