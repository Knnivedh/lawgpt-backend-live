"""
ADVANCED RETRIEVAL MODULE
State-of-the-art retrieval techniques for high-precision legal RAG.

Features:
1. Multi-Query Retrieval - Generate query variations
2. HyDE (Hypothetical Document Embeddings) - Search with hypothetical answers
3. Contextual Compression - Extract only relevant sentences
4. Result Fusion - Merge and deduplicate results
5. Metadata Extraction - Parse legal citations from queries
"""

import logging
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Unified result format for advanced retrieval"""
    id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    source: str  # 'vector', 'bm25', 'hyde', 'multi_query'


class AdvancedRetrieval:
    """
    Advanced RAG retrieval system optimized for 200K+ legal documents.
    """
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: OpenAI-compatible client for query generation
        """
        self.llm_client = llm_client
        # Same env contract as Config.MAIN_LLM_MODEL (LLM_MODEL/MAIN_LLM_MODEL)
        self.llm_model = os.getenv("LLM_MODEL") or os.getenv("MAIN_LLM_MODEL") or "llama-3.3-70b-versatile"
        
        # Legal metadata patterns
        self.metadata_patterns = {
            'act': r'(?:under|of|in)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Act)(?:,?\s*(\d{4}))?',
            'section': r'[Ss]ection\s+(\d+[A-Za-z]?)',
            'ipc': r'[Ii][Pp][Cc]\s+(\d+[A-Za-z]?)',
            'year': r'\b(19\d{2}|20\d{2})\b',
            'court': r'(Supreme Court|High Court|District Court|NCDRC|NCLAT|CAT)',
        }
    
    # =========================================================================
    # 1. MULTI-QUERY RETRIEVAL
    # =========================================================================
    
    def generate_query_variations(self, original_query: str, num_variations: int = 3) -> List[str]:
        """
        Generate semantic variations of the query to capture different phrasings.
        
        Example:
        Original: "divorce on mental cruelty"
        Variations: ["psychological abuse in marriage", "emotional suffering in matrimony", ...]
        """
        if not self.llm_client:
            # Fallback: simple keyword expansion
            return [original_query]
        
        prompt = f"""Generate {num_variations} semantically different search queries that would help find the same legal information as the original query. 
Focus on:
- Different legal terminology
- Synonyms of key concepts
- Alternative phrasings lawyers might use

Original query: "{original_query}"

Return ONLY the queries, one per line, no numbering or explanations."""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200
            )
            
            variations = response.choices[0].message.content.strip().split('\n')
            variations = [v.strip() for v in variations if v.strip() and len(v.strip()) > 5]
            
            # Always include original
            all_queries = [original_query] + variations[:num_variations]
            logger.info(f"[MULTI-QUERY] Generated {len(all_queries)} query variations")
            return all_queries
            
        except Exception as e:
            logger.warning(f"[MULTI-QUERY] Failed to generate variations: {e}")
            return [original_query]
    
    # =========================================================================
    # 2. HyDE (Hypothetical Document Embeddings)
    # =========================================================================
    
    def generate_hypothetical_answer(self, query: str) -> str:
        """
        Generate a hypothetical answer that would contain the information
        the user is looking for. This answer is then used for embedding search.
        
        This bridges the gap between query embedding space and document embedding space.
        """
        if not self.llm_client:
            return query
        
        prompt = f"""You are a legal expert. Write a SHORT hypothetical document passage (2-3 sentences) that would directly answer this legal query. 
Write as if you're quoting from a statute or judgment - use formal legal language.

Query: {query}

Hypothetical document passage:"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150
            )
            
            hyde_doc = response.choices[0].message.content.strip()
            logger.info(f"[HyDE] Generated hypothetical document: {hyde_doc[:80]}...")
            return hyde_doc
            
        except Exception as e:
            logger.warning(f"[HyDE] Failed to generate hypothetical: {e}")
            return query
    
    # =========================================================================
    # 3. METADATA EXTRACTION FROM QUERY
    # =========================================================================
    
    def extract_legal_metadata(self, query: str) -> Dict[str, Any]:
        """
        Extract legal metadata from query for filtering.
        
        Example:
        Query: "Section 302 IPC punishment 2023"
        Returns: {'section': '302', 'ipc': '302', 'year': '2023'}
        """
        metadata = {}
        
        # Extract Act names
        act_match = re.search(self.metadata_patterns['act'], query)
        if act_match:
            metadata['act'] = act_match.group(1)
            if act_match.group(2):
                metadata['act_year'] = act_match.group(2)
        
        # Extract Section numbers
        section_match = re.search(self.metadata_patterns['section'], query, re.IGNORECASE)
        if section_match:
            metadata['section'] = section_match.group(1)
        
        # Extract IPC sections
        ipc_match = re.search(self.metadata_patterns['ipc'], query, re.IGNORECASE)
        if ipc_match:
            metadata['ipc_section'] = ipc_match.group(1)
        
        # Extract year
        year_match = re.findall(self.metadata_patterns['year'], query)
        if year_match:
            metadata['year'] = year_match[-1]  # Take most recent year mentioned
        
        # Extract court
        court_match = re.search(self.metadata_patterns['court'], query, re.IGNORECASE)
        if court_match:
            metadata['court'] = court_match.group(1)
        
        if metadata:
            logger.info(f"[METADATA] Extracted filters: {metadata}")
        
        return metadata
    
    # =========================================================================
    # 4. CONTEXTUAL COMPRESSION
    # =========================================================================
    
    def compress_context(self, query: str, documents: List[Dict], max_sentences: int = 3) -> List[Dict]:
        """
        Extract only the most query-relevant sentences from each document.
        Reduces noise and focuses LLM attention.
        """
        if not self.llm_client:
            # Fallback: just truncate
            for doc in documents:
                if len(doc.get('text', '')) > 500:
                    doc['text'] = doc['text'][:500] + "..."
            return documents
        
        compressed_docs = []
        
        for doc in documents:
            text = doc.get('text', '')
            if len(text) < 200:  # Already short enough
                compressed_docs.append(doc)
                continue
            
            prompt = f"""Extract the {max_sentences} most relevant sentences from this document that directly answer or relate to the query.

Query: {query}

Document:
{text[:2000]}

Return ONLY the relevant sentences, nothing else:"""

            try:
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=300
                )
                
                compressed_text = response.choices[0].message.content.strip()
                doc_copy = doc.copy()
                doc_copy['text'] = compressed_text
                doc_copy['original_length'] = len(text)
                doc_copy['compressed'] = True
                compressed_docs.append(doc_copy)
                
            except Exception as e:
                logger.warning(f"[COMPRESSION] Failed: {e}")
                compressed_docs.append(doc)
        
        logger.info(f"[COMPRESSION] Compressed {len(compressed_docs)} documents")
        return compressed_docs
    
    # =========================================================================
    # 5. RESULT FUSION (RRF - Reciprocal Rank Fusion)
    # =========================================================================
    
    def reciprocal_rank_fusion(
        self, 
        result_lists: List[List[Dict]], 
        k: int = 60
    ) -> List[Dict]:
        """
        Merge multiple result lists using Reciprocal Rank Fusion.
        
        RRF formula: score = sum(1 / (k + rank_i)) for each list
        
        This gives higher weight to documents that appear highly ranked
        across multiple query variations.
        """
        fused_scores = {}
        doc_data = {}
        
        for result_list in result_lists:
            for rank, doc in enumerate(result_list, 1):
                doc_id = doc.get('id', hashlib.md5(doc.get('text', '')[:100].encode()).hexdigest())
                
                # RRF score accumulation
                if doc_id not in fused_scores:
                    fused_scores[doc_id] = 0
                    doc_data[doc_id] = doc
                
                fused_scores[doc_id] += 1 / (k + rank)
        
        # Sort by fused score
        sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
        
        fused_results = []
        for doc_id in sorted_ids:
            doc = doc_data[doc_id].copy()
            doc['rrf_score'] = fused_scores[doc_id]
            fused_results.append(doc)
        
        logger.info(f"[RRF] Fused {sum(len(r) for r in result_lists)} results into {len(fused_results)} unique documents")
        return fused_results
    
    # =========================================================================
    # 6. ADVANCED RETRIEVAL PIPELINE
    # =========================================================================
    
    def advanced_retrieve(
        self,
        query: str,
        search_func,  # Callable that takes query and returns results
        use_multi_query: bool = True,
        use_hyde: bool = True,
        use_compression: bool = False,  # Disable by default for speed
        top_k: int = 10
    ) -> List[Dict]:
        """
        Complete advanced retrieval pipeline.
        
        Args:
            query: User query
            search_func: Function to call for each search (e.g., milvus_store.hybrid_search)
            use_multi_query: Enable multi-query retrieval
            use_hyde: Enable HyDE
            use_compression: Enable contextual compression
            top_k: Final number of results to return
        """
        all_result_lists = []
        
        # 1. Original query search
        logger.info(f"[ADVANCED] Starting retrieval for: {query[:50]}...")
        original_results = search_func(query, n_results=top_k * 2)
        if original_results:
            all_result_lists.append(original_results)
        
        # 2. Multi-query retrieval
        if use_multi_query:
            variations = self.generate_query_variations(query, num_variations=2)
            for variant in variations[1:]:  # Skip original
                variant_results = search_func(variant, n_results=top_k)
                if variant_results:
                    all_result_lists.append(variant_results)
        
        # 3. HyDE retrieval
        if use_hyde:
            hyde_doc = self.generate_hypothetical_answer(query)
            if hyde_doc != query:
                hyde_results = search_func(hyde_doc, n_results=top_k)
                if hyde_results:
                    all_result_lists.append(hyde_results)
        
        # 4. Fuse results with RRF
        if len(all_result_lists) > 1:
            fused_results = self.reciprocal_rank_fusion(all_result_lists)
        else:
            fused_results = all_result_lists[0] if all_result_lists else []
        
        # 5. Take top_k
        top_results = fused_results[:top_k]
        
        # 6. Optional compression
        if use_compression and top_results:
            top_results = self.compress_context(query, top_results)
        
        logger.info(f"[ADVANCED] Final: {len(top_results)} documents retrieved")
        return top_results


# Singleton instance
_advanced_retrieval = None

def get_advanced_retrieval(llm_client=None) -> AdvancedRetrieval:
    """Get or create singleton instance"""
    global _advanced_retrieval
    if _advanced_retrieval is None:
        _advanced_retrieval = AdvancedRetrieval(llm_client)
    return _advanced_retrieval
