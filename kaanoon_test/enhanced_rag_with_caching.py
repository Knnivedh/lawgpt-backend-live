"""
Enhanced RAG System with Caching, Multi-language Support, and Monitoring
Implements all production-ready features for LAW-GPT
"""

import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging

# Add parent to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from system_adapters.rag_system_adapter_ULTIMATE import UltimateRAGAdapter
from landmark_cases_loader import get_landmark_db
from rag_system.core.scenario_detector import ScenarioDetector
import re

try:
    from prompts.chatbot_rules_enhanced import CHATBOT_RULES_SYSTEM
except ImportError:
    CHATBOT_RULES_SYSTEM = ""

try:
    from prompts.few_shot_examples import FEW_SHOT_LEGAL_EXAMPLES
except ImportError:
    FEW_SHOT_LEGAL_EXAMPLES = []

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rag_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class QueryCache:
    """
    Intelligent query caching system
    Caches frequent queries for faster responses
    """
    
    def __init__(self, max_size: int = 5000, ttl_seconds: int = 7200):
        """
        Initialize cache
        
        Args:
            max_size: Maximum number of cached queries
            ttl_seconds: Time to live for cache entries (default: 1 hour)
        """
        self.cache = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hit_count = 0
        self.miss_count = 0
        logger.info(f"Query cache initialized (max_size={max_size}, ttl={ttl_seconds}s)")
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query"""
        normalized = re.sub(r"[^\w\u0900-\u097F]+", " ", (query or "").lower().strip())
        normalized = " ".join(normalized.split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired"""
        query_hash = self._hash_query(query)
        
        if query_hash in self.cache:
            entry = self.cache[query_hash]
            
            # Check if expired
            if datetime.now() < entry['expires_at']:
                self.hit_count += 1
                logger.info(f"Cache HIT for query: {query[:50]}...")
                return entry['response']
            else:
                # Remove expired entry
                del self.cache[query_hash]
                logger.debug(f"Cache EXPIRED for query: {query[:50]}...")
        
        self.miss_count += 1
        logger.debug(f"Cache MISS for query: {query[:50]}...")
        return None
    
    def set(self, query: str, response: Dict[str, Any]):
        """Cache a response"""
        query_hash = self._hash_query(query)
        
        # If cache is full, remove oldest entry
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['created_at'])
            del self.cache[oldest_key]
            logger.debug("Cache full - removed oldest entry")
        
        self.cache[query_hash] = {
            'response': response,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(seconds=self.ttl_seconds),
            'query': query
        }
        logger.debug(f"Cached response for query: {query[:50]}...")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'ttl_seconds': self.ttl_seconds
        }
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        self.hit_count = 0
        self.miss_count = 0
        logger.info("Cache cleared")


class AnalyticsDashboard:
    """
    Analytics and monitoring dashboard
    Tracks queries, performance, and system health
    """
    
    def __init__(self):
        self.query_log = []
        self.error_log = []
        self.performance_metrics = defaultdict(list)
        self.query_categories = defaultdict(int)
        self.start_time = datetime.now()
        logger.info("Analytics dashboard initialized")
    
    def log_query(self, query: str, response: Dict[str, Any], latency: float, 
                  category: str = "general", from_cache: bool = False):
        """Log a query and its response"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'category': category,
            'latency_ms': round(latency * 1000, 2),
            'from_cache': from_cache,
            'answer_length': len(response.get('answer', '')),
            'sources_count': len(response.get('sources', [])),
            'used_kaanoon': response.get('used_kaanoon', False),
            'extraction_method': response.get('extraction_method', 'unknown')
        }
        
        self.query_log.append(log_entry)
        self.performance_metrics['latency'].append(latency)
        self.query_categories[category] += 1
        
        # Keep only last 1000 queries
        if len(self.query_log) > 1000:
            self.query_log.pop(0)
        
        logger.info(f"Logged query: {query[:50]}... (latency: {latency:.2f}s, cache: {from_cache})")
    
    def log_error(self, query: str, error: str):
        """Log an error"""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'error': error
        }
        
        self.error_log.append(error_entry)
        
        # Keep only last 100 errors
        if len(self.error_log) > 100:
            self.error_log.pop(0)
        
        logger.error(f"Error logged: {error} for query: {query[:50]}...")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data"""
        latencies = self.performance_metrics['latency']
        
        uptime = datetime.now() - self.start_time
        
        dashboard = {
            'system': {
                'uptime_seconds': int(uptime.total_seconds()),
                'uptime_formatted': str(uptime).split('.')[0],
                'start_time': self.start_time.isoformat()
            },
            'queries': {
                'total': len(self.query_log),
                'by_category': dict(self.query_categories),
                'last_24h': len([q for q in self.query_log if 
                                (datetime.now() - datetime.fromisoformat(q['timestamp'])).seconds < 86400])
            },
            'performance': {
                'avg_latency_ms': round(sum(latencies) / len(latencies) * 1000, 2) if latencies else 0,
                'min_latency_ms': round(min(latencies) * 1000, 2) if latencies else 0,
                'max_latency_ms': round(max(latencies) * 1000, 2) if latencies else 0,
                'p95_latency_ms': round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 2) if latencies else 0
            },
            'errors': {
                'total': len(self.error_log),
                'recent': self.error_log[-10:] if self.error_log else []
            },
            'usage': {
                'kaanoon_used': len([q for q in self.query_log if q.get('used_kaanoon')]),
                'from_cache': len([q for q in self.query_log if q.get('from_cache')]),
                'avg_answer_length': sum([q.get('answer_length', 0) for q in self.query_log]) // len(self.query_log) if self.query_log else 0
            }
        }
        
        return dashboard
    
    def save_dashboard(self, filepath: str = 'analytics_dashboard.json'):
        """Save dashboard data to file"""
        dashboard_data = self.get_dashboard_data()
        dashboard_data['generated_at'] = datetime.now().isoformat()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Dashboard data saved to {filepath}")


class EnhancedRAGSystem:
    """
    Enhanced RAG System with all features:
    - Query caching
    - Multi-language support
    - Monitoring & analytics
    - Integrated prompts
    """
    
    # Multi-language support
    SUPPORTED_LANGUAGES = ['en', 'hi']  # English, Hindi
    
    # Language detection keywords
    LANGUAGE_PATTERNS = {
        'hi': ['है', 'हैं', 'के', 'की', 'में', 'से', 'को', 'का', 'धारा', 'कानून', 'न्यायालय']
    }

    HINGLISH_HINTS = [
        'kya', 'kaise', 'kyun', 'kyuki', 'samjhao', 'samjhaiye', 'adhikar', 'zamanat',
        'dhara', 'adalat', 'kanun', 'kanoon', 'vakil', 'patni', 'pati', 'kiraya', 'makan', 'fir', 'bail',
    ]
    
    def __init__(self):
        """Initialize enhanced RAG system"""
        logger.info("=" * 80)
        logger.info("INITIALIZING ENHANCED RAG SYSTEM")
        logger.info("=" * 80)
        
        # Load expanded Kaanoon dataset
        self.load_expanded_dataset()
        
        # Initialize core RAG
        self.rag = UltimateRAGAdapter()
        
        # Initialize caching (optimized for performance)
        self.cache = QueryCache(max_size=5000, ttl_seconds=7200)
        
        # Initialize landmark cases database
        self.landmark_db = get_landmark_db()
        if not hasattr(self, 'is_initialized') or not self.is_initialized: # Added check for is_initialized
            # Initialize RAG adapter
            self.rag = UltimateRAGAdapter()
            self.store = self.rag.store # FIX: Alias for compatibility with older code paths
            
            # Scenario detection
            self.scenario_detector = ScenarioDetector()
        
        # Initialize analytics
        self.analytics = AnalyticsDashboard()
        
        # Initialize scenario detector
        self.scenario_detector = ScenarioDetector()
        logger.info("✅ Scenario detector initialized - 8 scenarios supported")
        
        # Load prompts
        self.chatbot_rules = CHATBOT_RULES_SYSTEM
        self.few_shot_examples = FEW_SHOT_LEGAL_EXAMPLES
        
        logger.info("✅ Enhanced RAG System ready with all features!")
        logger.info("   - Query caching enabled")
        logger.info("   - Multi-language support (English, Hindi)")
        logger.info("   - Analytics dashboard active")
        logger.info("   - Integrated prompts loaded")
        logger.info("=" * 80)
    
    def load_expanded_dataset(self):
        """Load expanded Kaanoon Q&A dataset"""
        try:
            current_dir = Path(__file__).parent
            dataset_path = current_dir / 'kaanoon_qa_expanded.json'
            with open(dataset_path, 'r', encoding='utf-8') as f:
                self.expanded_dataset = json.load(f)
            logger.info(f"✅ Loaded expanded dataset: {len(self.expanded_dataset)} Q&A pairs")
        except FileNotFoundError:
            logger.warning("Expanded dataset not found, using default")
            self.expanded_dataset = []
    
    def generate_response_title(self, query: str) -> str:
        """Generate dynamic title based on query content"""
        query_lower = query.lower()
        
        # IPC Section queries
        ipc_match = re.search(r'ipc\s*(?:section\s*)?(\d+[a-z]?)', query_lower)
        if ipc_match:
            section = ipc_match.group(1).upper()
            return f"IPC Section {section}"
        
        # CrPC Section queries
        crpc_match = re.search(r'crpc\s*(?:section\s*)?(\d+)', query_lower)
        if crpc_match:
            section = crpc_match.group(1)
            return f"CrPC Section {section}"
        
        # Article queries
        article_match = re.search(r'article\s*(\d+[a-z]?)', query_lower)
        if article_match:
            article = article_match.group(1).upper()
            return f"Article {article} of Indian Constitution"
        
        # Specific legal topics
        if 'fir' in query_lower and not re.search(r'\bfire\b', query_lower):
            return "First Information Report (FIR)"
        if 'bail' in query_lower:
            return "Bail Procedures in India"
        if 'divorce' in query_lower:
            return "Divorce Law in India"
        if 'property' in query_lower and ('transfer' in query_lower or 'sale' in query_lower):
            return "Property Transfer Law"
        if 'dowry' in query_lower:
            return "Dowry Law and Related Provisions"
        if 'rape' in query_lower or 'sexual assault' in query_lower:
            return "Sexual Assault Laws in India"
        if 'murder' in query_lower:
            return "Murder and Homicide Laws"
        if 'cheating' in query_lower or '420' in query:
            return "Cheating and Fraud Laws"
        if 'fundamental right' in query_lower:
            return "Fundamental Rights under Indian Constitution"
        if 'consumer' in query_lower and 'complaint' in query_lower:
            return "Consumer Protection Laws"
        if 'maintenance' in query_lower:
            return "Maintenance Laws in India"
        if 'custody' in query_lower:
            return "Child Custody Laws"
        if 'arrest' in query_lower:
            return "Arrest Procedures and Rights"
        if 'confession' in query_lower:
            return "Confessional Statements and Evidence"
        
        # Case law queries
        if 'case' in query_lower or 'judgment' in query_lower or 'supreme court' in query_lower:
            if 'kesavananda' in query_lower:
                return "Kesavananda Bharati Case - Basic Structure Doctrine"
            if 'vishaka' in query_lower:
                return "Vishaka Guidelines - Sexual Harassment"
            if 'rarest of rare' in query_lower or 'bachan singh' in query_lower:
                return "Rarest of Rare Doctrine - Death Penalty"
            if 'maneka gandhi' in query_lower:
                return "Maneka Gandhi Case - Personal Liberty"
            if 'privacy' in query_lower:
                return "Right to Privacy - Landmark Judgment"
            return "Landmark Case Law"
        
        # Process-based queries
        if query_lower.startswith('how to'):
            if 'file' in query_lower:
                return "Filing Procedure Guide"
            return "Legal Procedure Guide"
        
        if query_lower.startswith('what is'):
            # Extract the subject
            subject = query_lower.replace('what is', '').strip().rstrip('?').strip()
            if subject:
                # Capitalize properly
                words = subject.split()
                if words:
                    title_words = [word.upper() if word.upper() in ['IPC', 'CrPC', 'CPC', 'FIR', 'POCSO'] 
                                  else word.capitalize() for word in words]
                    return ' '.join(title_words)
        
        if 'difference between' in query_lower:
            return "Legal Concepts Comparison"
        
        # Default titles by topic detection
        if 'criminal' in query_lower:
            return "Criminal Law"
        if 'civil' in query_lower:
            return "Civil Law"
        if 'family' in query_lower:
            return "Family Law"
        if 'constitution' in query_lower:
            return "Constitutional Law"
        
        # Generic fallback
        return "Legal Information"
    
    def detect_language(self, query: str) -> str:
        """Detect query language"""
        if any(token in query.lower() for token in self.HINGLISH_HINTS):
            return 'hi'
        # Count language-specific characters/words
        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            if any(pattern in query for pattern in patterns):
                return lang
        return 'en'  # Default to English
    
    def translate_response(self, response: Dict[str, Any], target_lang: str) -> Dict[str, Any]:
        """
        Translate response to target language
        (Placeholder - integrate with translation API in production)
        """
        if target_lang == 'en':
            return response
        
        # For now, check if we have pre-translated answer in dataset
        for qa in self.expanded_dataset:
            if qa.get('short_answer') == response.get('answer'):
                if target_lang == 'hi' and 'answer_hindi' in qa:
                    response['answer'] = qa['answer_hindi']
                    response['translated_from'] = 'en'
                    response['target_language'] = 'hi'
                break
        
        return response
    
    def query(self, question: str, category: str = "general", target_language: str = None) -> Dict[str, Any]:
        """
        Query the enhanced RAG system
        
        Args:
            question: User question
            category: Question category for analytics
            target_language: Target language (en/hi) - auto-detected if None
            
        Returns:
            Dict with answer and metadata
        """
        start_time = time.time()
        from_cache = False
        
        try:
            # Check cache first (skip for fast responses, they're already instant)
            cached_response = self.cache.get(question)
            if cached_response:
                from_cache = True
                latency = time.time() - start_time
                self.analytics.log_query(question, cached_response, latency, category, from_cache=True)
                return cached_response
            
            # STEP 1: Detect scenario and enhance query
            scenario_info = self.scenario_detector.detect_scenario(question)
            enhanced_question = question  # Use original for now, can use enhanced later
            
            if scenario_info['scenarios']:
                logger.info(f"Detected scenarios: {[s['type'] for s in scenario_info['scenarios']]}")
                # Could use scenario_info['enhanced_query'] for better retrieval
            
            # Generate dynamic title based on query
            response_title = self.generate_response_title(question)
            
            # Get response from RAG (fast lookup happens inside)
            # Pass target_language=None to let RAG handle fast lookups instantly
            # Use enhanced question if available from scenario detection
            query_to_use = scenario_info.get('enhanced_query', question) if scenario_info['has_scenarios'] else question
            response = self.rag.query(query_to_use, target_language=target_language)
            
            # Add scenario metadata to response
            if scenario_info['scenarios']:
                response['detected_scenarios'] = [s['type'] for s in scenario_info['scenarios']]
                response['extracted_data'] = scenario_info.get('extracted_data', {})
            
            # Add dynamic title
            response['title'] = response_title
            
            # Enhance answer with landmark cases if relevant
            if not response.get('fast_response'):
                response['answer'] = self.landmark_db.enhance_answer_with_cases(question, response.get('answer', ''))
            
            # FAST RESPONSE: If RAG returned instantly (fast lookup), return immediately
            if response.get('fast_response'):
                # Skip language detection, translation, and analytics for speed
                response['system_info'] = {
                    'enhanced_features': True,
                    'caching_enabled': True,
                    'multi_language': True,
                    'detected_language': response.get('detected_language', 'en'),
                    'fast_lookup': True
                }
                # Still cache it for future queries
                self.cache.set(question, response)
                return response
            
            # For non-fast responses, do full processing
            # Detect language if not provided (only for non-fast responses)
            detected_lang = target_language or self.detect_language(question)
            logger.info(f"Query language detected: {detected_lang}")
            
            # Check if answer is already in correct language (from exact mapping)
            # If not, try to translate
            if detected_lang != 'en' and not response.get('detected_language'):
                response = self.translate_response(response, detected_lang)
            
            # Add system metadata
            response['system_info'] = {
                'enhanced_features': True,
                'caching_enabled': True,
                'multi_language': True,
                'detected_language': detected_lang
            }
            
            # 1. Retrieve relevant documents
            # Boost to 10 to catch landmark cases
            documents = self.rag.store.hybrid_search(question, n_results=10)
            
            # DEBUG: Print retrieved titles
            print(f"\n🔍 RETRIEVED {len(documents)} DOCS FOR: {question[:50]}...")
            for i, d in enumerate(documents[:3]):
                meta = d.get('metadata', {})
                print(f"  [{i+1}] {meta.get('case_name', 'No Title')} ({d.get('score', 0):.4f})")

            
            # Cache the response
            self.cache.set(question, response)
            
            # Log to analytics
            latency = time.time() - start_time
            self.analytics.log_query(question, response, latency, category, from_cache)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            self.analytics.log_error(question, str(e))
            raise
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()
    
    def get_dashboard(self) -> Dict[str, Any]:
        """Get analytics dashboard"""
        dashboard = self.analytics.get_dashboard_data()
        dashboard['cache_stats'] = self.get_cache_stats()
        return dashboard
    
    def save_analytics(self):
        """Save analytics to file"""
        self.analytics.save_dashboard()


def main():
    """Test the enhanced RAG system"""
    print("\n" + "="*80)
    print("ENHANCED RAG SYSTEM - TEST MODE")
    print("="*80)
    
    # Initialize system
    system = EnhancedRAGSystem()
    
    # Test queries
    test_queries = [
        ("Can principal claim money from 2000 GPA sale after 25 years?", "property_law"),
        ("Can landlord evict tenant without court order?", "property_law"),
        ("लेखा परीक्षक की देरी के कारण AGM देरी को कैसे माफ करवाएं?", "society_law"),  # Hindi
        ("Can principal claim money from 2000 GPA sale after 25 years?", "property_law"),  # Duplicate for cache test
    ]
    
    for i, (query, category) in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"TEST QUERY {i}: {query}")
        print(f"{'='*80}")
        
        result = system.query(query, category=category)
        
        print(f"\nAnswer: {result['answer'][:200]}...")
        print(f"\nMetadata:")
        print(f"   - Latency: {result.get('latency', 0):.2f}s")
        print(f"   - Used Kaanoon: {result.get('used_kaanoon', False)}")
        print(f"   - Language: {result.get('system_info', {}).get('detected_language', 'en')}")
        print(f"   - From Cache: {'Yes' if 'from_cache' not in result else 'No'}")
    
    # Show dashboard
    print(f"\n\n{'='*80}")
    print("SYSTEM DASHBOARD")
    print(f"{'='*80}")
    
    dashboard = system.get_dashboard()
    print(json.dumps(dashboard, indent=2))
    
    # Save analytics
    system.save_analytics()
    print(f"\n[SUCCESS] Analytics saved to: analytics_dashboard.json")


if __name__ == "__main__":
    main()

