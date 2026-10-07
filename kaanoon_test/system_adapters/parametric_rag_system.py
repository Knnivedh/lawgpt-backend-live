"""
PARAMETRIC ADVANCED RAG SYSTEM
Accepts parameters from LLM router and optimizes retrieval accordingly

ADVANCED FEATURES:
- Multi-Query Retrieval (query variations)
- HyDE (Hypothetical Document Embeddings)
- Cloud Re-ranking with Cross-Encoder
- Metadata Filtering
- RRF Fusion
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import time
import logging

logger = logging.getLogger(__name__)

# Add parent directories to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# chromadb is disabled on cloud — guard it
try:
    from rag_system.core.hybrid_chroma_store import HybridChromaStore
    _CHROMADB_AVAILABLE = True
except ImportError:
    HybridChromaStore = None
    _CHROMADB_AVAILABLE = False

from rag_system.core.enhanced_retriever import EnhancedRetriever
try:
    from rag_system.core.advanced_retrieval import AdvancedRetrieval, get_advanced_retrieval
except ImportError:
    AdvancedRetrieval = None
    get_advanced_retrieval = None


class ParametricRAGSystem:
    """Advanced RAG with parameter-based optimization and state-of-the-art retrieval"""
    
    def __init__(self, main_store=None, statute_store=None, llm_client=None):
        """Initialize parametric RAG system with advanced retrieval"""
        print("[PARAMETRIC RAG] Initializing advanced retrieval system...")
        self.store = main_store
        self.statute_store = statute_store
        self.retriever = EnhancedRetriever(self.store, statute_store=self.statute_store)
        
        # Initialize advanced retrieval module
        self.advanced = AdvancedRetrieval(llm_client)
        self.llm_client = llm_client
        
        # Store reference to cross-encoder from enhanced retriever
        self.reranker = self.retriever.reranker if self.retriever.has_reranker else None
        
        print("[PARAMETRIC RAG] [OK] System ready with advanced retrieval")

    
    def retrieve_with_params(
        self,
        query: str,
        rag_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve documents using parameters from LLM router
        
        Args:
            query: User query
            rag_params: Parameters from router including:
                - search_domain: str (IPC, GST, DPDP, etc.)
                - specific_sections: List[str]
                - case_names: List[str]
                - keywords: List[str]
                - complexity: str (simple|medium|complex)
        
        Returns:
            {
                'documents': List[Dict],
                'context': str,
                'metadata': Dict
            }
        """
        start_time = time.time()
        
        # Extract parameters
        search_domain = rag_params.get('search_domain', 'general')
        specific_sections = rag_params.get('specific_sections', [])
        case_names = rag_params.get('case_names', [])
        keywords = rag_params.get('keywords', [])
        complexity = rag_params.get('complexity', 'medium')
        
        print(f"\n[PARAMETRIC RAG] Query: {query}")
        print(f"[PARAMETRIC RAG] Domain: {search_domain}")
        print(f"[PARAMETRIC RAG] Complexity: {complexity}")
        print(f"[PARAMETRIC RAG] Sections: {specific_sections}")
        print(f"[PARAMETRIC RAG] Keywords: {keywords}")
        
        # Build enhanced query with parameters
        enhanced_query = self._build_enhanced_query(
            query, search_domain, specific_sections, case_names, keywords
        )
        
        print(f"[PARAMETRIC RAG] Enhanced query: {enhanced_query}")
        
        # Determine retrieval count based on complexity
        retrieval_count = self._get_retrieval_count(complexity)
        
        # Execute retrieval - OPTIMIZED: Only use advanced pipeline for truly complex queries
        try:
            # PERFORMANCE FIX: Only use advanced retrieval for COMPLEX queries
            # Simple/Medium queries use direct search (MUCH faster)
            use_advanced = complexity == 'complex' and self.llm_client is not None
            
            if use_advanced and hasattr(self.store, 'advanced_search'):
                logger.info("[ADVANCED RAG] Using multi-query + HyDE + re-ranking pipeline (COMPLEX ONLY)")
                
                # Extract metadata filters from query (but don't force them)
                metadata_filter = self.advanced.extract_legal_metadata(query)
                
                # Define search function for advanced retrieval
                def cloud_search(q, n_results=10):
                    # First try WITH filters
                    if metadata_filter:
                        results = self.store.advanced_search(
                            q, 
                            n_results=n_results, 
                            metadata_filter=metadata_filter,
                            reranker=self.reranker
                        )
                        if results:
                            return results
                    
                    # Fallback: search WITHOUT filters
                    return self.store.advanced_search(
                        q, 
                        n_results=n_results, 
                        metadata_filter=None,  # No filter
                        reranker=self.reranker
                    )
                
                # Run advanced retrieval pipeline (ONLY for complex queries)
                results = self.advanced.advanced_retrieve(
                    query=enhanced_query,
                    search_func=cloud_search,
                    use_multi_query=True,  # Only for complex
                    use_hyde=True,  # Only for complex
                    use_compression=False,  # Disabled for speed
                    top_k=retrieval_count * 2
                )
                
                logger.info(f"[ADVANCED RAG] Retrieved {len(results)} documents via advanced pipeline")
                
            elif hasattr(self.store, 'hybrid_search'):
                # FAST PATH: Direct Milvus search for simple/medium queries
                # No multi-query, no HyDE, no slow LLM calls
                logger.info(f"[FAST RAG] Using direct Milvus search (complexity: {complexity})")
                results = self.store.hybrid_search(enhanced_query, n_results=retrieval_count * 2)
                logger.info(f"[FAST RAG] Retrieved {len(results)} documents directly")
                
            else:
                # Fallback to standard retriever
                results = self.retriever.retrieve(
                    enhanced_query,
                    use_reranking=(complexity == 'complex'),  # Only rerank complex
                    use_query_expansion=False  # Disabled for speed
                )
            
            # Filter results by domain if specified
            if search_domain != 'general':
                results = self._filter_by_domain(results, search_domain, specific_sections)
            
            # Limit to retrieval count
            results = results[:retrieval_count]
            
            # Build context from results
            context = self._build_context(results, query, rag_params)
            
            retrieval_time = time.time() - start_time
            
            print(f"[PARAMETRIC RAG] Retrieved {len(results)} documents in {retrieval_time:.2f}s")
            
            return {
                'documents': results,
                'context': context,
                'metadata': {
                    'retrieval_time': retrieval_time,
                    'document_count': len(results),
                    'search_domain': search_domain,
                    'complexity': complexity,
                    'enhanced_query': enhanced_query,
                    'advanced_mode': use_advanced if 'use_advanced' in dir() else False
                }
            }
            
        except Exception as e:
            print(f"[ERROR] Parametric retrieval failed: {e}")
            return {
                'documents': [],
                'context': '',
                'metadata': {
                    'error': str(e),
                    'retrieval_time': time.time() - start_time
                }
            }
    
    def _build_enhanced_query(
        self,
        original_query: str,
        domain: str,
        sections: List[str],
        cases: List[str],
        keywords: List[str]
    ) -> str:
        """Build enhanced query with parameters"""
        
        enhanced_parts = [original_query]
        
        # Add domain context
        if domain != 'general':
            enhanced_parts.append(domain)
        
        # Add specific sections
        if sections:
            enhanced_parts.append(' '.join(f"Section {s}" for s in sections))
        
        # Add case names
        if cases:
            enhanced_parts.append(' '.join(cases))
        
        # Add important keywords
        if keywords:
            # Filter out common words already in query
            new_keywords = [k for k in keywords if k.lower() not in original_query.lower()]
            if new_keywords:
                enhanced_parts.append(' '.join(new_keywords[:3]))  # Top 3 keywords
        
        return ' '.join(enhanced_parts)
    
    def _get_retrieval_count(self, complexity: str) -> int:
        """Determine document count based on complexity"""
        counts = {
            'simple': 2,    # Fast and focused
            'medium': 5,    # Balanced
            'complex': 8    # Comprehensive
        }
        return counts.get(complexity, 5)
    
    def _filter_by_domain(
        self,
        results: List[Dict],
        domain: str,
        sections: List[str]
    ) -> List[Dict]:
        """Filter results by legal domain"""
        
        # Domain keywords for filtering
        domain_keywords = {
            'IPC': ['ipc', 'indian penal code', 'section', 'criminal'],
            'GST': ['gst', 'goods and services tax', 'tax', 'cgst', 'sgst'],
            'DPDP': ['dpdp', 'data protection', 'privacy', 'personal data'],
            'Contract': ['contract', 'agreement', 'indian contract act'],
            'Property': ['property', 'ownership', 'transfer', 'land'],
            'Criminal': ['criminal', 'offense', 'punishment', 'ipc'],
            'Civil': ['civil', 'suit', 'damages', 'tort'],
            'Corporate': ['company', 'corporate', 'director', 'companies act']
        }
        
        keywords = domain_keywords.get(domain, [])
        if not keywords:
            return results  # No filtering if domain not recognized
        
        # Score results by domain relevance
        scored_results = []
        for result in results:
            text = result.get('text', '').lower()
            metadata = result.get('metadata', {})
            
            # Calculate domain match score
            match_score = sum(1 for kw in keywords if kw in text)
            
            # Boost if specific section mentioned
            if sections:
                for section in sections:
                    if section in text or f"section {section}" in text:
                        match_score += 5
            
            if match_score > 0:
                result['domain_score'] = match_score
                scored_results.append(result)
        
        # Sort by domain relevance + original score
        scored_results.sort(
            key=lambda x: (x.get('domain_score', 0) * 0.3 + x.get('score', 0) * 0.7),
            reverse=True
        )
        
        return scored_results if scored_results else results  # Return filtered or original
    
    def _build_context(
        self,
        results: List[Dict],
        query: str,
        rag_params: Dict
    ) -> str:
        """Build context string from retrieved documents"""
        
        if not results:
            return ""
        
        context_parts = []
        
        # Add domain header if specific
        domain = rag_params.get('search_domain', 'general')
        if domain != 'general':
            context_parts.append(f"Legal Domain: {domain}\n")
        
        # Add each document
        for i, doc in enumerate(results, 1):
            text = doc.get('text', '')
            score = doc.get('score', 0)
            metadata = doc.get('metadata', {})
            
            # Truncate if too long
            if len(text) > 800:
                text = text[:800] + "..."
            
            context_parts.append(f"[Document {i}] (Relevance: {score:.2f})")
            context_parts.append(text)
            context_parts.append("")  # Empty line
        
        return '\n'.join(context_parts)
