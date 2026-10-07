"""
Core Testing Framework for Legal AI Systems
Provides TestCase, TestResult, MetricsCalculator, and TestRunner classes
"""

import json
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import re


@dataclass
class TestCase:
    """Represents a single test case"""
    test_id: str
    query: str
    expected_id: str
    expected_answer: str
    expected_references: List[str]
    variation_type: str
    difficulty: str
    metadata: Dict[str, Any] = None


@dataclass
class TestResult:
    """Stores results from a test execution"""
    test_id: str
    system_name: str
    query: str
    expected_id: str
    
    # Response data
    response: str = ""
    retrieved_context: Optional[str] = None
    
    # Timing
    start_time: float = 0.0
    end_time: float = 0.0
    latency_ms: float = 0.0
    
    # Metrics
    accuracy_score: float = 0.0
    semantic_similarity: float = 0.0
    keyword_overlap_f1: float = 0.0
    reference_match_rate: float = 0.0
    retrieval_correct: bool = False
    
    # Quality indicators
    contains_hallucination: bool = False
    citation_accuracy: float = 0.0
    
    # Error tracking
    error: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


class MetricsCalculator:
    """Calculate various metrics for test results"""
    
    def __init__(self):
        """Initialize with embedding model for semantic similarity"""
        print("[Init] Loading embedding model for metrics...")
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        print("[OK] Embedding model ready")

    @staticmethod
    def _to_text(value: Any) -> str:
        """Normalize any value to a plain text string"""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return " ".join(MetricsCalculator._to_text(v) for v in value)
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError:
            return str(value)
    
    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity between two texts"""
        try:
            embeddings = self.embedding_model.encode([text1, text2])
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return float(similarity)
        except Exception as e:
            print(f"[ERROR] Semantic similarity calculation failed: {e}")
            return 0.0
    
    def extract_keywords(self, text: str) -> set:
        """Extract important keywords from text"""
        text = self._to_text(text)
        # Remove common words and extract meaningful terms
        text = text.lower()
        # Remove punctuation but keep alphanumeric
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Common stop words to remove
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'could', 'may', 'might', 'can', 'this', 'that', 'these',
            'those', 'it', 'its', 'they', 'their', 'them', 'he', 'she', 'his',
            'her', 'him', 'you', 'your', 'we', 'our', 'us', 'i', 'my', 'me'
        }
        
        words = text.split()
        keywords = {w for w in words if len(w) > 3 and w not in stop_words}
        return keywords
    
    def calculate_keyword_overlap_f1(self, response: str, expected: str) -> float:
        """Calculate F1 score based on keyword overlap"""
        response_keywords = self.extract_keywords(response)
        expected_keywords = self.extract_keywords(expected)
        
        if not expected_keywords:
            return 0.0
        
        # Calculate precision and recall
        true_positives = len(response_keywords & expected_keywords)
        
        if not response_keywords:
            return 0.0
        
        precision = true_positives / len(response_keywords) if response_keywords else 0
        recall = true_positives / len(expected_keywords) if expected_keywords else 0
        
        # Calculate F1
        if precision + recall == 0:
            return 0.0
        
        f1 = 2 * (precision * recall) / (precision + recall)
        return f1
    
    def extract_legal_references(self, text: str) -> set:
        """Extract legal references from text"""
        text = self._to_text(text)
        references = set()
        text_lower = text.lower()
        
        # Patterns for legal references
        patterns = [
            r'article\s+\d+',
            r'section\s+\d+',
            r'order\s+\d+',
            r'rule\s+\d+',
            r'धारा\s+\d+',
            r'अनुच्छेद\s+\d+',
            r'नियम\s+\d+',
            r'act[,\s]+\d{4}',
            r'limitation\s+act',
            r'cpc',
            r'ipc',
            r'crpc',
            r'आईपीसी',
            r'सीपीसी',
            r'सीआरपीसी',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            references.update(matches)
        
        # Extract case names (simplified)
        case_pattern = r'([A-Z][a-z]+\s+v\.?\s+[A-Z][a-z]+)'
        case_matches = re.findall(case_pattern, text)
        references.update([c.lower() for c in case_matches])
        
        return references
    
    def calculate_reference_match_rate(self, response: str, expected_references: List[str]) -> float:
        """Calculate how many expected legal references are mentioned"""
        if not expected_references:
            return 1.0  # No references expected
        
        response_refs = self.extract_legal_references(response)
        expected_refs_lower = {ref.lower() for ref in expected_references}
        
        # Check how many expected references appear
        matches = 0
        for exp_ref in expected_refs_lower:
            # Check if any part of the expected reference appears in response
            for resp_ref in response_refs:
                if exp_ref in resp_ref or resp_ref in exp_ref:
                    matches += 1
                    break
        
        match_rate = matches / len(expected_references)
        return match_rate
    
    def detect_hallucination(self, response: str, context: Optional[str]) -> bool:
        """Simple hallucination detection"""
        if not context:
            return False
        
        # Check if response contains information not in context
        # This is simplified - real hallucination detection is complex
        
        # Look for specific false claims
        false_patterns = [
            r'according to.*(?:which|that).*(?:does not exist|fictional)',
            r'section\s+\d{4,}',  # Section numbers that are too high
            r'article\s+\d{4,}',  # Article numbers that are too high
        ]
        
        for pattern in false_patterns:
            if re.search(pattern, response.lower()):
                return True
        
        return False
    
    def calculate_all_metrics(
        self,
        response: str,
        expected_answer: str,
        expected_references: List[str],
        context: Optional[str] = None
    ) -> Dict[str, float]:
        """Calculate all metrics at once"""
        response_text = self._to_text(response)
        expected_text = self._to_text(expected_answer)
        context_text = self._to_text(context)

        metrics = {
            'semantic_similarity': self.calculate_semantic_similarity(response_text, expected_text) if response_text and expected_text else 0.0,
            'keyword_overlap_f1': self.calculate_keyword_overlap_f1(response_text, expected_text) if response_text and expected_text else 0.0,
            'reference_match_rate': self.calculate_reference_match_rate(response_text, expected_references),
            'contains_hallucination': self.detect_hallucination(response_text, context_text),
        }
        
        # Calculate overall accuracy score (weighted average)
        # Optimized weights: Prioritize semantic meaning over exact keywords
        # since legal answers can be correct with different wording
        accuracy = (
            metrics['semantic_similarity'] * 0.70 +      # Increased: factual correctness
            metrics['keyword_overlap_f1'] * 0.15 +       # Reduced: exact term matching
            metrics['reference_match_rate'] * 0.15       # Reduced: citation matching
        )
        metrics['accuracy_score'] = accuracy
        
        return metrics


class TestRunner:
    """Orchestrates test execution across different systems"""
    
    def __init__(self, ground_truth_path: str):
        """Initialize with ground truth dataset"""
        with open(ground_truth_path, 'r', encoding='utf-8') as f:
            self.ground_truth = json.load(f)
        
        self.metrics_calculator = MetricsCalculator()
        self.results = []
    
    def create_test_case(self, query_data: Dict) -> TestCase:
        """Create TestCase from query data"""
        expected_id = query_data['expected_id']
        
        # Find expected answer from ground truth
        expected_qa = None
        for qa in self.ground_truth:
            if qa['id'] == expected_id:
                expected_qa = qa
                break
        
        if not expected_qa:
            raise ValueError(f"Expected Q&A {expected_id} not found in ground truth")
        
        return TestCase(
            test_id=query_data['test_id'],
            query=query_data['query'],
            expected_id=expected_id,
            expected_answer=expected_qa.get('answer_summary', ''),
            expected_references=expected_qa.get('legal_references', []),
            variation_type=query_data.get('variation_type', 'unknown'),
            difficulty=query_data.get('difficulty', 'medium'),
            metadata=query_data
        )
    
    def run_test(
        self,
        test_case: TestCase,
        system_adapter,
        system_name: str
    ) -> TestResult:
        """Run a single test case"""
        
        result = TestResult(
            test_id=test_case.test_id,
            system_name=system_name,
            query=test_case.query,
            expected_id=test_case.expected_id
        )
        
        try:
            # Execute query
            result.start_time = time.time()
            response_data = system_adapter.query(test_case.query)
            result.end_time = time.time()
            
            result.latency_ms = (result.end_time - result.start_time) * 1000
            result.response = response_data.get('answer', '')
            result.retrieved_context = response_data.get('context', None)
            
            # Check if correct Q&A was retrieved
            if 'retrieved_id' in response_data:
                result.retrieval_correct = (response_data['retrieved_id'] == test_case.expected_id)
            
            # Calculate metrics
            metrics = self.metrics_calculator.calculate_all_metrics(
                response=result.response,
                expected_answer=test_case.expected_answer,
                expected_references=test_case.expected_references,
                context=result.retrieved_context
            )
            
            result.accuracy_score = metrics['accuracy_score']
            result.semantic_similarity = metrics['semantic_similarity']
            result.keyword_overlap_f1 = metrics['keyword_overlap_f1']
            result.reference_match_rate = metrics['reference_match_rate']
            result.contains_hallucination = metrics['contains_hallucination']
            
        except Exception as e:
            result.error = str(e)
            print(f"[ERROR] Test {test_case.test_id} failed: {e}")
        
        return result
    
    def run_test_suite(
        self,
        test_cases: List[TestCase],
        system_adapter,
        system_name: str,
        verbose: bool = True
    ) -> List[TestResult]:
        """Run complete test suite on a system"""
        
        results = []
        total = len(test_cases)
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"TESTING: {system_name}")
            print(f"{'='*60}")
            print(f"Total test cases: {total}\n")
        
        for idx, test_case in enumerate(test_cases, 1):
            if verbose:
                print(f"[{idx}/{total}] Testing: {test_case.test_id} ({test_case.variation_type})")
            
            result = self.run_test(test_case, system_adapter, system_name)
            results.append(result)
            
            if verbose and result.error is None:
                print(f"  [OK] Accuracy: {result.accuracy_score:.2f}, Latency: {result.latency_ms:.0f}ms")
            elif verbose:
                print(f"  [ERROR] {result.error}")
        
        self.results.extend(results)
        
        if verbose:
            self._print_summary(results, system_name)
        
        return results
    
    def _print_summary(self, results: List[TestResult], system_name: str):
        """Print summary statistics for a test run"""
        successful = [r for r in results if r.error is None]
        
        if not successful:
            print(f"\n[WARNING] No successful tests for {system_name}")
            return
        
        avg_accuracy = np.mean([r.accuracy_score for r in successful])
        avg_similarity = np.mean([r.semantic_similarity for r in successful])
        avg_latency = np.mean([r.latency_ms for r in successful])
        avg_reference = np.mean([r.reference_match_rate for r in successful])
        
        retrieval_correct = sum(1 for r in successful if r.retrieval_correct)
        hallucinations = sum(1 for r in successful if r.contains_hallucination)
        
        print(f"\n{'='*60}")
        print(f"SUMMARY: {system_name}")
        print(f"{'='*60}")
        print(f"Successful Tests: {len(successful)}/{len(results)}")
        print(f"Average Accuracy: {avg_accuracy:.3f}")
        print(f"Semantic Similarity: {avg_similarity:.3f}")
        print(f"Keyword F1 Score: {np.mean([r.keyword_overlap_f1 for r in successful]):.3f}")
        print(f"Reference Match Rate: {avg_reference:.3f}")
        print(f"Correct Retrievals: {retrieval_correct}/{len(successful)}")
        print(f"Avg Latency: {avg_latency:.0f}ms")
        print(f"Hallucinations Detected: {hallucinations}")
        print(f"{'='*60}\n")
    
    def save_results(self, output_path: str):
        """Save all results to JSON file"""
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': len(self.results),
            'results': [r.to_dict() for r in self.results]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"[SAVED] Results: {output_path}")


def main():
    """Demo of testing framework"""
    print("\n" + "="*60)
    print("TESTING FRAMEWORK DEMO")
    print("="*60)
    
    # This is just a demo - actual usage is in run_tests.py
    print("\nFramework components:")
    print("✓ TestCase - Test case representation")
    print("✓ TestResult - Result storage")
    print("✓ MetricsCalculator - Metric computation")
    print("✓ TestRunner - Test orchestration")
    
    print("\nReady to use with system adapters!")


if __name__ == "__main__":
    main()

