"""
Run comprehensive accuracy test without server
Quick standalone test using kaanoon_qa_dataset_cleaned.json
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add parent to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(Path(__file__).parent))

from enhanced_rag_with_caching import EnhancedRAGSystem
from testing_framework import MetricsCalculator

def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE ACCURACY TEST - GROUND TRUTH EVALUATION")
    print("="*80)
    
    # Load ground truth (using summary for consistency with Ultimate RAG)
    print("\n[1/4] Loading ground truth dataset...")
    with open('kaanoon_qa_summary.json', 'r', encoding='utf-8') as f:
        ground_truth = json.load(f)
    print(f"[OK] Loaded {len(ground_truth)} Q&A pairs")
    
    # Initialize systems
    print("\n[2/4] Initializing Enhanced RAG System...")
    system = EnhancedRAGSystem()
    metrics_calc = MetricsCalculator()
    
    # Test all Q&A
    print("\n[3/4] Running comprehensive tests...")
    print("="*80)
    
    results = []
    for i, qa in enumerate(ground_truth, 1):
        qa_id = qa.get('id')
        
        # Skip Q5 which is reference guide
        if 'Q5' in qa_id:
            print(f"\n[{i}/{len(ground_truth)}] Skipping Q5 (reference guide)")
            continue
        
        question = qa.get('question', '')
        expected = qa.get('short_answer', '')
        
        if not question or not expected:
            print(f"[{i}/{len(ground_truth)}] Skipping {qa_id} - missing data")
            continue
        
        print(f"\n[{i}/{len(ground_truth)}] Testing {qa_id} - {qa.get('category', 'Unknown')}")
        print(f"  Q: {question[:80]}...")
        
        try:
            # Query system
            start = time.time()
            result = system.query(question, category=qa.get('category', 'general'))
            latency = time.time() - start
            
            # Calculate metrics
            metrics = metrics_calc.calculate_all_metrics(result['answer'], expected, [])
            
            # Display result
            accuracy = metrics['accuracy_score']
            semantic = metrics['semantic_similarity']
            keyword = metrics['keyword_overlap_f1']
            
            # Additional display
            print(f"  Expected: {expected[:80]}...")
            
            status = "[EXCELLENT]" if accuracy >= 0.90 else "[GOOD]" if accuracy >= 0.70 else "[NEEDS WORK]" if accuracy >= 0.50 else "[POOR]"
            
            print(f"  Answer: {result['answer'][:100]}...")
            print(f"  {status}")
            print(f"  Accuracy: {accuracy:.1%} | Semantic: {semantic:.1%} | Keyword: {keyword:.1%}")
            kaanoon_mark = "YES" if result.get('used_kaanoon') else "NO"
            print(f"  Latency: {latency:.2f}s | Kaanoon: {kaanoon_mark}")
            
            results.append({
                'id': qa_id,
                'category': qa.get('category', 'unknown'),
                'metrics': metrics,
                'latency': latency,
                'used_kaanoon': result.get('used_kaanoon', False)
            })
            
        except Exception as e:
            print(f"  [ERROR]: {e}")
            results.append({
                'id': qa_id,
                'error': str(e)
            })
    
    # Final summary
    print("\n\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    success_results = [r for r in results if 'error' not in r]
    
    if success_results:
        avg_accuracy = sum(r['metrics']['accuracy_score'] for r in success_results) / len(success_results)
        avg_semantic = sum(r['metrics']['semantic_similarity'] for r in success_results) / len(success_results)
        avg_keyword = sum(r['metrics']['keyword_overlap_f1'] for r in success_results) / len(success_results)
        avg_latency = sum(r['latency'] for r in success_results) / len(success_results)
        
        print(f"\nTests Completed: {len(success_results)}")
        print(f"Errors: {len(results) - len(success_results)}")
        print(f"\nAverage Accuracy: {avg_accuracy:.1%}")
        print(f"Average Semantic Similarity: {avg_semantic:.1%}")
        print(f"Average Keyword F1: {avg_keyword:.1%}")
        print(f"Average Latency: {avg_latency:.2f}s")
        
        kaanoon_used = sum(1 for r in success_results if r.get('used_kaanoon'))
        print(f"Kaanoon Usage: {kaanoon_used}/{len(success_results)} ({kaanoon_used/len(success_results)*100:.0f}%)")
        
        if avg_accuracy >= 0.90:
            verdict = "[EXCELLENT] - World-Class Performance!"
        elif avg_accuracy >= 0.80:
            verdict = "[TARGET MET] - Production Ready!"
        elif avg_accuracy >= 0.70:
            verdict = "[GOOD] - Needs Minor Improvements"
        elif avg_accuracy >= 0.50:
            verdict = "[NEEDS WORK] - Significant Improvements Required"
        else:
            verdict = "[POOR] - Major Improvements Required"
        
        print(f"\n{verdict}")
    
    # Save detailed results
    output_file = 'comprehensive_accuracy_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': len(results),
                'successful': len(success_results),
                'failed': len(results) - len(success_results),
                'avg_accuracy': float(avg_accuracy) if success_results else 0,
                'avg_semantic': float(avg_semantic) if success_results else 0,
                'avg_keyword': float(avg_keyword) if success_results else 0,
                'avg_latency': float(avg_latency) if success_results else 0,
                'kaanoon_usage_rate': float(kaanoon_used/len(success_results)) if success_results else 0
            },
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n[SUCCESS] Results saved to: {output_file}")
    print("="*80)
    
    # Save cache and analytics
    system.save_analytics()
    print(f"[SUCCESS] Analytics saved to: analytics_dashboard.json")


if __name__ == '__main__':
    main()

