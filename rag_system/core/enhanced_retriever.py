"""
ENHANCED RETRIEVER - Improved Search & Ranking System
Fixes: Query optimization, re-ranking, multi-hop retrieval
"""

import re
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
import numpy as np
import numpy as np
import logging

try:
    import os
    # We will import SentenceTransformer/CrossEncoder lazily inside methods
    # to avoid failing if they aren't installed on restricted RAM environments
    pass
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


import sys
from pathlib import Path

# Add project root to path for external_apis
# Try multiple common locations for robustness
current_dir = Path(__file__).parent
project_paths = [
    current_dir.parent.parent / "kaanoon_test",  # kaanoon_test/external_apis
    current_dir.parent.parent,                   # LAW-GPT/external_apis
]

for path in project_paths:
    if (path / "external_apis").exists():
        sys.path.append(str(path))
        break

try:
    from external_apis.indian_kanoon_client import IndianKanoonClient
except ImportError:
    logging.warning("Could not import IndianKanoonClient. Live retrieval will be disabled.")
    IndianKanoonClient = None

class EnhancedRetriever:
    """
    Enhanced retrieval system with:
    1. Query preprocessing & expansion
    2. Increased retrieval count (adaptive)
    3. Cross-encoder re-ranking
    4. Multi-hop reasoning support
    5. Legal term normalization
    6. [NEW] Live Search fallback (Indian Kanoon)
    """

    DEFAULT_TRUSTED_LIVE_DOMAINS = {
        "indiankanoon.org",
        "livelaw.in",
        "barandbench.com",
        "scobserver.in",
        "main.sci.gov.in",
        "escr.supremecourt.gov.in",
        "indiacode.nic.in",
    }
    
    def __init__(self, hybrid_store, statute_store=None, reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize enhanced retriever
        
        Args:
            hybrid_store: Main HybridChromaStore instance (Judgments)
            statute_store: Specialized HybridChromaStore instance (Statutes) [OPTIONAL]
            reranker_model: Cross-encoder model for re-ranking
        """
        self.hybrid_store = hybrid_store
        self.statute_store = statute_store
        self.strict_live_trust_filter = str(
            os.getenv("LEGAL_TRUST_FILTER_STRICT", "true")
        ).strip().lower() in ("1", "true", "yes", "on")
        self.live_trusted_domains = self._load_trusted_live_domains()
        
        # Initialize Indian Kanoon Client
        if IndianKanoonClient:
            self.kanoon_client = IndianKanoonClient()
        else:
            self.kanoon_client = None
            
        # Load re-ranker for better relevance scoring
        logger.info(f"Loading re-ranker: {reranker_model} (Lazy Mode)")
        self.reranker_model = reranker_model
        self.reranker = None
        self.has_reranker = False # Will check lazily
        
        # Legal term mappings for normalization
        self.legal_term_patterns = {
            # IPC patterns
            r'\bipc\s*(\d+[a-z]?)\b': r'IPC Section \1',
            r'\bsection\s*(\d+[a-z]?)\b': r'Section \1',
            
            # Common Acts (normalize names)
            r'\bcrpc\b': 'Criminal Procedure Code',
            r'\bcpc\b': 'Civil Procedure Code',
            r'\biea\b': 'Indian Evidence Act',
            r'\bpoc\s*act\b': 'Prevention of Corruption Act',
            
            # Legal concepts
            r'\bfir\b': 'First Information Report',
            r'\bbail\b': 'bail application',
            r'\bwrit\b': 'writ petition',
        }
        
        # Synonyms for query expansion
        self.legal_synonyms = {
            'murder': ['homicide', 'killing', 'IPC 302', 'culpable homicide'],
            'theft': ['stealing', 'IPC 379', 'larceny'],
            'fraud': ['cheating', 'IPC 420', 'deception'],
            'property': ['real estate', 'land', 'immovable property'],
            'will': ['testament', 'succession', 'inheritance'],
            'divorce': ['dissolution of marriage', 'separation'],
            'custody': ['guardianship', 'child custody'],
            'bail': ['surety', 'bond', 'release'],
        }

    def _load_trusted_live_domains(self) -> set:
        raw = str(os.getenv("LEGAL_TRUSTED_DOMAINS", "")).strip()
        if not raw:
            return set(self.DEFAULT_TRUSTED_LIVE_DOMAINS)
        parsed = {part.strip().lower() for part in raw.split(",") if part.strip()}
        return parsed or set(self.DEFAULT_TRUSTED_LIVE_DOMAINS)

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            return (urlparse(url or "").netloc or "").lower().replace("www.", "")
        except Exception:
            return ""

    def _is_trusted_live_domain(self, domain: str) -> bool:
        if not domain:
            return False
        for allowed in self.live_trusted_domains:
            if domain == allowed or domain.endswith(f".{allowed}"):
                return True
        return domain.endswith(".gov.in") or domain.endswith(".nic.in")

    @staticmethod
    def _build_provenance_id(*parts: str) -> str:
        base = "|".join(str(part or "") for part in parts)
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:20]

    def _build_live_metadata(
        self,
        *,
        title: str,
        source: str,
        court: str,
        year: str,
        citation: str,
        url: str,
        doc_type: str,
        is_recent: bool,
    ) -> Dict:
        source_domain = self._extract_domain(url)
        trusted_source = self._is_trusted_live_domain(source_domain)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        return {
            'title': title,
            'source': source,
            'court': court,
            'year': year,
            'citation': citation,
            'url': url,
            'type': doc_type,
            'is_recent': is_recent,
            'source_domain': source_domain,
            'trusted_source': trusted_source,
            'source_tier': 'trusted' if trusted_source else 'unverified',
            'retrieved_at': retrieved_at,
            'provenance_id': self._build_provenance_id(title, url, year, source, retrieved_at),
        }
    
    def normalize_legal_terms(self, text: str) -> str:
        """
        Normalize legal terminology in query
        
        Args:
            text: Input query text
            
        Returns:
            Normalized text
        """
        normalized = text
        
        # Apply regex patterns
        for pattern, replacement in self.legal_term_patterns.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized
    
    def expand_query(self, query: str) -> str:
        """
        Expand query with synonyms and related terms
        
        Args:
            query: Original query
            
        Returns:
            Expanded query
        """
        query_lower = query.lower()
        expanded_terms = []
        
        # Add synonyms if found
        for term, synonyms in self.legal_synonyms.items():
            if term in query_lower:
                # Add 1-2 most relevant synonyms (not all to avoid dilution)
                expanded_terms.extend(synonyms[:2])
        
        if expanded_terms:
            return f"{query} {' '.join(expanded_terms)}"
        
        return query
    
    def preprocess_query(self, query: str) -> Tuple[str, str]:
        """
        Complete query preprocessing pipeline with legal-domain enhancements
        
        Args:
            query: Raw user query
            
        Returns:
            Tuple of (normalized_query, expanded_query)
        """
        # Step 1: Normalize legal terms
        normalized = self.normalize_legal_terms(query)
        
        # Step 2: Expand legal abbreviations
        expanded = self._expand_legal_abbreviations(query)
        
        # Step 3: Add legal synonyms
        expanded = self._add_legal_synonyms(expanded)
        
        # Step 4: Add related sections
        expanded = self._add_related_sections(expanded)
        
        # Step 5: Add procedural terms
        expanded = self._add_procedural_terms(expanded)
        
        logger.info(f"Query preprocessing:")
        logger.info(f"  Original: {query}")
        logger.info(f"  Normalized: {normalized}")
        logger.info(f"  Expanded: {expanded}")
        
        return normalized, expanded
    
    def _expand_legal_abbreviations(self, query: str) -> str:
        """Expand legal abbreviations in query"""
        expanded = query
        query_upper = query.upper()
        
        abbreviations_map = {
            'IPC': ['Indian Penal Code', 'Penal Code'],
            'CrPC': ['Code of Criminal Procedure', 'Criminal Procedure Code'],
            'CPC': ['Code of Civil Procedure', 'Civil Procedure Code'],
            'IEA': ['Indian Evidence Act', 'Evidence Act'],
            'FIR': ['First Information Report', 'Section 154 CrPC'],
            'SC': ['Supreme Court', 'Apex Court'],
            'HC': ['High Court'],
            'NCLT': ['National Company Law Tribunal'],
            'NCLAT': ['National Company Law Appellate Tribunal'],
            'RERA': ['Real Estate Regulatory Authority'],
            'CAT': ['Central Administrative Tribunal'],
            'ADR': ['Alternative Dispute Resolution', 'Arbitration'],
            'POCSO': ['Protection of Children from Sexual Offences Act'],
            'GST': ['Goods and Services Tax'],
            'RTI': ['Right to Information'],
        }
        
        for abbrev, expansions in abbreviations_map.items():
            if abbrev in query_upper:
                for expansion in expansions:
                    if expansion.lower() not in query.lower():
                        expanded += f" {expansion}"
        
        return expanded
    
    def _add_legal_synonyms(self, query: str) -> str:
        """Add legal synonyms to query"""
        expanded = query
        query_lower = query.lower()
        
        synonyms_map = {
            'murder': ['homicide', 'killing', 'culpable homicide', 'IPC 302'],
            'theft': ['stealing', 'larceny', 'IPC 379'],
            'fraud': ['cheating', 'deception', 'IPC 420'],
            'property': ['real estate', 'land', 'immovable property'],
            'will': ['testament', 'succession', 'inheritance'],
            'divorce': ['dissolution of marriage', 'separation'],
            'custody': ['guardianship', 'child custody'],
            'bail': ['surety', 'bond', 'release'],
            'arrest': ['apprehension', 'detention'],
            'trial': ['proceedings', 'hearing'],
            'judgment': ['order', 'decree', 'verdict'],
            'appeal': ['challenge', 'revision'],
            'writ': ['constitutional remedy', 'mandamus', 'habeas corpus'],
            'contract': ['agreement', 'deed'],
            'lease': ['tenancy', 'rental'],
            'possession': ['occupation', 'control'],
            'ownership': ['title', 'proprietorship'],
        }
        
        for term, synonyms in synonyms_map.items():
            if term in query_lower:
                for synonym in synonyms:
                    if synonym.lower() not in query_lower:
                        expanded += f" {synonym}"
        
        return expanded
    
    def _add_related_sections(self, query: str) -> str:
        """Add related IPC sections to query"""
        expanded = query
        
        # Extract IPC section numbers
        ipc_pattern = r'(?:IPC|Indian Penal Code|Section)\s*(\d+[a-z]?)'
        matches = re.findall(ipc_pattern, query, re.IGNORECASE)
        
        # Related sections mapping
        related_sections = {
            '302': ['304', '307', '308', '300', '299'],  # Murder
            '304': ['302', '299', '300'],  # Culpable homicide
            '307': ['302', '308', '309'],  # Attempt to murder
            '379': ['380', '381', '382'],  # Theft
            '420': ['415', '416', '417', '418'],  # Cheating
            '406': ['405', '407', '408', '409'],  # Criminal breach of trust
            '376': ['376A', '376B', '376C', '376D'],  # Rape
            '498A': ['304B', '306'],  # Dowry
        }
        
        for section_num in matches:
            if section_num in related_sections:
                for related_section in related_sections[section_num]:
                    if f"Section {related_section}" not in expanded and f"IPC {related_section}" not in expanded:
                        expanded += f" IPC Section {related_section}"
        
        return expanded
    
    def _add_procedural_terms(self, query: str) -> str:
        """Add procedural terms based on query content"""
        expanded = query
        query_lower = query.lower()
        
        # FIR-related
        if 'fir' in query_lower or 'first information' in query_lower:
            if 'section 154' not in query_lower:
                expanded += " Section 154 CrPC First Information Report"
        
        # Bail-related
        if 'bail' in query_lower:
            expanded += " Section 437 CrPC Section 438 CrPC anticipatory bail"
        
        # Evidence-related
        if 'evidence' in query_lower or 'witness' in query_lower:
            expanded += " Indian Evidence Act examination cross-examination"
        
        # Property-related
        if 'property' in query_lower or 'sale' in query_lower:
            expanded += " Transfer of Property Act registration deed"
        
        return expanded
    
    def detect_query_complexity(self, query: str) -> str:
        """
        Detect query complexity to adjust retrieval count
        
        Returns:
            'SIMPLE', 'MEDIUM', or 'COMPLEX'
        """
        query_lower = query.lower()
        word_count = len(query.split())
        
        # Complex indicators
        complex_keywords = [
            'constitutional', 'article', 'fundamental right',
            'vs', 'versus', 'conflict', 'interfaith',
            'analyze', 'compare', 'relationship',
            'multiple', 'different laws', 'succession',
            'jurisdiction', 'precedent', 'landmark'
        ]
        
        # Check complexity
        has_complex_keywords = any(kw in query_lower for kw in complex_keywords)
        
        if has_complex_keywords or word_count > 20:
            return 'COMPLEX'
        elif word_count > 10:
            return 'MEDIUM'
        else:
            return 'SIMPLE'
    
    def adaptive_retrieval_count(self, query: str) -> int:
        """
        Determine optimal number of documents to retrieve based on query
        
        Args:
            query: User query
            
        Returns:
            Number of documents to retrieve
        """
        complexity = self.detect_query_complexity(query)
        
        retrieval_counts = {
            'SIMPLE': 2,      # Simple queries - minimal docs needed (optimized for speed)
            'MEDIUM': 3,      # Medium complexity - balanced (SPEED FIX)
            'COMPLEX': 5      # Complex queries - sufficient context (SPEED FIX)
        }
        
        count = retrieval_counts[complexity]
        logger.info(f"Query complexity: {complexity} → Retrieving {count} documents")
        
        return count
    
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """
        Re-rank results using cross-encoder for better relevance
        
        Args:
            query: User query
            results: Initial retrieved results
            
        Returns:
            Re-ranked results
        """
        if self.reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Activating Re-ranker: {self.reranker_model}")
                self.reranker = CrossEncoder(self.reranker_model)
                self.has_reranker = True
            except (ImportError, Exception) as e:
                logger.warning(f"Re-ranker disabled. Dependencies missing or error: {e}")
                self.has_reranker = False
                return results

        logger.info("Re-ranking results with cross-encoder...")
        
        # Prepare query-document pairs
        pairs = [[query, doc['text'][:384]] for doc in results]  # Limit to 384 chars for faster scoring
        
        # Get cross-encoder scores
        try:
            scores = self.reranker.predict(pairs)
        except Exception as e:
            logger.error(f"Re-ranking prediction failed: {e}")
            return results
        
        # Add scores to results
        for i, result in enumerate(results):
            result['rerank_score'] = float(scores[i])
        
        # Sort by rerank score (descending)
        reranked = sorted(results, key=lambda x: x['rerank_score'], reverse=True)
        
        logger.info(f"Re-ranked {len(results)} results")
        
        return reranked
    
    def _fetch_live_results(self, query: str, max_results: int = 2) -> List[Dict]:
        """
        Fetch live results from Indian Kanoon API if local results are insufficient
        
        Args:
            query: Search query
            max_results: Max docs to fetch (keep low for latency)
            
        Returns:
            List of formatted document dictionaries
        """
        if not self.kanoon_client:
            return []
            
        logger.info(f"Initiating LIVE SEARCH on Indian Kanoon for: '{query}'")
        
        try:
            queries_to_run = [query]
            
            # Smart Freshness: If user wants "latest/recent", explicitly search for recent years
            is_recent_query = any(w in query.lower() for w in ['latest', 'recent', 'newest', '2024', '2025'])
            if is_recent_query:
                # Add explicit year queries to force search engine to find new cases
                # Note: We append the year to the query
                base_query = query.replace('latest', '').replace('recent', '').replace('newest', '').strip()
                queries_to_run.append(f"{base_query} 2024")
                queries_to_run.append(f"{base_query} 2025")
                logger.info("Detected 'latest' query - Adding explicit 2024/2025 year searches")

            all_results = []
            seen_ids = set()
            
            for q in queries_to_run:
                try:
                    # Search for judgments
                    results = self.kanoon_client.search_judgments(q, max_results=max_results)
                    
                    for item in results:
                        doc_id = item['doc_id']
                        if doc_id in seen_ids:
                            continue
                            
                        seen_ids.add(doc_id)
                        
                        # Fetch full text
                        judgment = self.kanoon_client.get_judgment(doc_id)
                        
                        if judgment and judgment['text']:
                            doc_year = judgment['year'] or 0
                            
                            # Boost score for recent years if 'latest' was requested
                            freshness_boost = 0.0
                            if is_recent_query and doc_year >= 2024:
                                freshness_boost = 5.0 # Huge boost for 2024/25
                                logger.info(f"Boosting RECENT judgment: {judgment['title']} ({doc_year})")
                            elif is_recent_query and doc_year >= 2023:
                                freshness_boost = 2.0
                            
                            all_results.append({
                                'id': f"live_ik_{doc_id}",
                                'text': f"{judgment['title']}\n\n{judgment['text']}",
                                'metadata': self._build_live_metadata(
                                    title=judgment['title'],
                                    source='Indian Kanoon (Live)',
                                    court=judgment['court'] or 'Unknown',
                                    year=str(doc_year) if doc_year else 'Unknown',
                                    citation=judgment['citation'] or '',
                                    url=f"https://indiankanoon.org/doc/{doc_id}/",
                                    doc_type='live_judgment',
                                    is_recent=doc_year >= 2023,
                                ),
                                'distance': 0.0 - freshness_boost # Lower distance = Better rank (or use rerank_score if available)
                            })
                except Exception as e:
                    logger.warning(f"Indian Kanoon API partial failure for '{q}': {e}")
            
            # FALLBACK: If API failed or found nothing (e.g. 403 Forbidden), use Web Search
            if not all_results:
                logger.warning("Indian Kanoon API found 0 documents (or is blocked). Switching to WEB SEARCH FALLBACK.")
                
                # Lazy import to avoid circular dep issues
                try:
                    from kaanoon_test.external_apis.web_search_client import get_web_search_client
                    web_client = get_web_search_client()
                    
                    # Target trustworthy legal sites
                    # AUTO-FRESHNESS: Always hunt for 2024/2025 data in fallback mode
                    # This ensures we don't just get the old 2019/2021 cases which are more popular
                    web_query = f"{query} site:indiankanoon.org OR site:livelaw.in OR site:barandbench.com 2024 2025"
                        
                    web_results = web_client.search(web_query, max_results=4)
                    
                    for res in web_results:
                        url = str(res.get('link') or res.get('url') or '').strip()
                        source_domain = self._extract_domain(url)
                        trusted_source = self._is_trusted_live_domain(source_domain)
                        if self.strict_live_trust_filter and not trusted_source:
                            logger.info(f"Skipping untrusted live web source: {source_domain or 'unknown'}")
                            continue

                        snippet = str(res.get('snippet') or '')
                        result_year = '2024' if ('2024' in snippet or '2025' in snippet) else 'Unknown'
                        all_results.append({
                            'id': f"live_web_{self._build_provenance_id(url, res.get('title', ''))}",
                            'text': (
                                f"Title: {res.get('title', '')}\n"
                                f"Source: {res.get('source', 'Web Search')}\n"
                                f"URL: {url}\n\n"
                                f"Summary/Snippet:\n{snippet}"
                            ),
                            'metadata': self._build_live_metadata(
                                title=str(res.get('title') or 'Web result'),
                                source='Web Search (Live)',
                                court='Unknown',
                                year=result_year,
                                citation='',
                                url=url,
                                doc_type='web_fallback',
                                is_recent=True,
                            ),
                            'distance': 0.1 # Slightly worse than direct API but better than nothing
                        })
                    logger.info(f"✓ Retrieved {len(all_results)} documents via WEB SEARCH")
                    
                except Exception as we:
                    logger.error(f"Web Search Fallback also failed: {we}")

            if not all_results and self.strict_live_trust_filter:
                logger.warning("No live results survived trusted-domain filtering.")
            logger.info(f"✓ Retrieved {len(all_results)} LIVE documents (Unique)")
            return all_results
            
        except Exception as e:
            logger.error(f"Live search failed: {e}")
            return []

    def retrieve(
        self,
        query: str,
        use_reranking: bool = True,
        use_query_expansion: bool = True,
        top_k: int = None,
        allow_live_search: bool = False  # SPEED FIX: Default to False for sub-10s
    ) -> List[Dict]:
        """
        Enhanced retrieval with all improvements + Live Search
        
        Args:
            query: User query
            use_reranking: Whether to apply re-ranking
            use_query_expansion: Whether to expand query
            top_k: Override for number of results
            allow_live_search: Whether to fallback to API for fresh data
            
        Returns:
            List of retrieved and ranked documents
        """
        # Step 1: Preprocess query
        normalized_query, expanded_query = self.preprocess_query(query)
        
        # Step 2: Determine retrieval count adaptively or use override
        n_results = top_k if top_k is not None else self.adaptive_retrieval_count(query)
        
        # Step 3: Retrieve from LOCAL database
        search_query = expanded_query if use_query_expansion else normalized_query
        
        # Retrieve more than needed for re-ranking
        retrieve_count = n_results * 2 if use_reranking else n_results
        
        results = []
        if self.hybrid_store:
            results = self.hybrid_store.hybrid_search(
                query=search_query,
                n_results=retrieve_count
            )
        else:
            logger.warning("Main hybrid store not available, skipping local main search.")
        
        # Step 3.5: Retrieve from STATUTE store if available
        if self.statute_store:
            logger.info("Searching specialized STATUTE store...")
            statute_results = self.statute_store.hybrid_search(
                query=search_query,
                n_results=retrieve_count
            )
            # Add to results and mark them as high-priority or unique
            for res in statute_results:
                # Deduplicate if necessary (unlikely between stores)
                results.append(res)
        
        logger.info(f"Retrieved {len(results)} total documents from local searching")
        
        # Step 4: LIVE SEARCH Fallback/Enrichment
        # Trigger if:
        # 1. Very few local results (< 3)
        # 2. Or explicitly complex/specific case law query
        # 3. Or user specifically asks for "recent" or "judgment"
        # 4. Or local stores are unavailable (cloud deployment without vector DB)
        no_local_store_available = not bool(self.hybrid_store) and not bool(self.statute_store)
        needs_live_search = (
            (allow_live_search or no_local_store_available)
            and (
                len(results) < 3
                or "recent" in query.lower()
                or "judgment" in query.lower()
                or "case" in query.lower()
                or no_local_store_available
            )
        )

        if no_local_store_available and not allow_live_search:
            logger.info("Local stores unavailable; forcing live-search fallback.")
        
        if needs_live_search:
            # Use original query for API search (it handles boolean/phrase better)
            live_results = self._fetch_live_results(query, max_results=2)
            if live_results:
                results.extend(live_results)
        
        # Step 5: Re-rank if enabled AND we have enough results (SPEED FIX: skip for few results)
        if use_reranking and self.has_reranker and len(results) > 3:
            results = self.rerank_results(query, results)
            # Take top n_results after re-ranking
            results = results[:n_results]
        
        # Step 6: Add retrieval metadata
        for i, result in enumerate(results):
            result['rank'] = i + 1
            result['retrieval_query'] = search_query
            result['normalized_query'] = normalized_query
        
        logger.info(f"Final: Returning {len(results)} ranked documents")
        
        return results
    
    def multi_hop_retrieval(
        self,
        query: str,
        max_hops: int = 2
    ) -> List[Dict]:
        """
        Multi-hop retrieval for complex queries requiring information synthesis
        
        Args:
            query: User query
            max_hops: Maximum number of retrieval hops
            
        Returns:
            Combined results from multiple hops
        """
        logger.info(f"Multi-hop retrieval (max {max_hops} hops)")
        
        all_results = []
        seen_ids = set()
        
        # Hop 1: Initial retrieval
        hop1_results = self.retrieve(query)
        
        for result in hop1_results:
            if result['id'] not in seen_ids:
                all_results.append(result)
                seen_ids.add(result['id'])
        
        # Extract key entities from hop 1 results
        key_entities = self._extract_key_entities_from_results(hop1_results)
        
        # Hop 2: Query using extracted entities
        if max_hops >= 2 and key_entities:
            expanded_query = f"{query} {' '.join(key_entities[:3])}"
            
            logger.info(f"Hop 2 query: {expanded_query}")
            
            hop2_results = self.retrieve(expanded_query)
            
            for result in hop2_results:
                if result['id'] not in seen_ids:
                    result['hop'] = 2
                    all_results.append(result)
                    seen_ids.add(result['id'])
        
        logger.info(f"Multi-hop complete: {len(all_results)} total documents")
        
        return all_results
    
    def _extract_key_entities_from_results(self, results: List[Dict]) -> List[str]:
        """
        Extract key legal entities from retrieved documents
        
        Args:
            results: Retrieved documents
            
        Returns:
            List of key entities (IPC sections, Acts, etc.)
        """
        entities = []
        
        # Extract IPC sections
        for result in results:
            text = result['text']
            
            # Find IPC sections
            ipc_matches = re.findall(r'IPC\s+(?:Section\s+)?(\d+[A-Z]?)', text, re.IGNORECASE)
            entities.extend([f"IPC {match}" for match in ipc_matches[:2]])
            
            # Find Acts
            act_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Act,?\s+\d{4})', text)
            entities.extend(act_matches[:2])
        
        # Remove duplicates
        return list(set(entities))
    
    def get_retrieval_explanation(self, results: List[Dict]) -> str:
        """
        Generate explanation of retrieval process for transparency
        
        Args:
            results: Retrieved documents
            
        Returns:
            Human-readable explanation
        """
        if not results:
            return "No documents retrieved."
        
        explanation = f"Retrieved {len(results)} documents:\n"
        
        for i, result in enumerate(results[:5], 1):
            metadata = result.get('metadata', {})
            domain = metadata.get('domain', 'unknown')
            score = result.get('rrf_score', result.get('rerank_score', 0))
            
            explanation += f"  {i}. [{domain}] Score: {score:.4f}\n"
        
        return explanation


# Example usage and testing
if __name__ == "__main__":
    print("Enhanced Retriever Module - Ready for integration")
    print("\nKey Features:")
    print("✓ Query preprocessing & normalization")
    print("✓ Legal term expansion")
    print("✓ Adaptive retrieval count (5-15 docs)")
    print("✓ Cross-encoder re-ranking")
    print("✓ Multi-hop retrieval")

