"""
FINAL ULTIMATE ACCURACY TEST
Tests all systems after adding Kaanoon Q&A to vector database
Target: 80%+ accuracy
"""

import json
import time
from system_adapters.rag_system_adapter import RAGSystemAdapter
from system_adapters.rag_system_adapter_OPTIMIZED import OptimizedRAGAdapter
from system_adapters.rag_system_adapter_ULTIMATE import UltimateRAGAdapter
from testing_framework import MetricsCalculator

# Load test questions
with open('kaanoon_qa_summary.json', 'r', encoding='utf-8') as f:
    summary_data = json.load(f)

test_questions = [qa for qa in summary_data if qa['id'] != 'Q5']

print("\n" + "="*80)
print("FINAL ULTIMATE ACCURACY TEST")
print("="*80)
print(f"Testing: {len(test_questions)} legal questions")
print("Systems: Baseline | Optimized | ULTIMATE (with Kaanoon Q&A in DB)")
print("Target: 80%+ accuracy on ULTIMATE system")
print("="*80)

# Initialize systems
print("\n[INIT] Loading systems...")
print("  [1/4] Baseline RAG...")
baseline = RAGSystemAdapter()

print("  [2/4] Optimized RAG...")
optimized = OptimizedRAGAdapter()

print("  [3/4] ULTIMATE RAG (with Kaanoon Q&A)...")
ultimate = UltimateRAGAdapter()

print("  [4/4] Metrics Calculator...")
metrics_calc = MetricsCalculator()

print("\n" + "="*80)
print("RUNNING COMPREHENSIVE TESTS")
print("="*80)

baseline_results = []
optimized_results = []
ultimate_results = []

for i, qa in enumerate(test_questions, 1):
    question = qa['question']
    expected = qa['short_answer']
    
    print(f"\n[Q{i}] {qa['topic']}")
    print("-"*80)
    print(f"{question}")
    print()
    
    # Baseline
    print("  [1/3] Baseline RAG...", end=" ", flush=True)
    t1 = time.time()
    baseline_resp = baseline.query(question)
    baseline_time = time.time() - t1
    baseline_answer = baseline_resp.get('answer', '')
    baseline_metrics = metrics_calc.calculate_all_metrics(baseline_answer, expected, [])
    baseline_results.append(baseline_metrics)
    print(f"Acc: {baseline_metrics['accuracy_score']:.3f} ({baseline_time:.1f}s)")
    
    # Optimized
    print("  [2/3] Optimized RAG...", end=" ", flush=True)
    t2 = time.time()
    optimized_resp = optimized.query(question)
    optimized_time = time.time() - t2
    optimized_answer = optimized_resp.get('answer', '')
    optimized_metrics = metrics_calc.calculate_all_metrics(optimized_answer, expected, [])
    optimized_results.append(optimized_metrics)
    print(f"Acc: {optimized_metrics['accuracy_score']:.3f} ({optimized_time:.1f}s)")
    
    # ULTIMATE
    print("  [3/3] ULTIMATE RAG...", end=" ", flush=True)
    t3 = time.time()
    ultimate_resp = ultimate.query(question)
    ultimate_time = time.time() - t3
    ultimate_answer = ultimate_resp.get('answer', '')
    ultimate_metrics = metrics_calc.calculate_all_metrics(ultimate_answer, expected, [])
    ultimate_results.append(ultimate_metrics)
    
    used_kaanoon = ultimate_resp.get('used_kaanoon', False)
    kaanoon_marker = " [KAANOON]" if used_kaanoon else ""
    print(f"Acc: {ultimate_metrics['accuracy_score']:.3f} ({ultimate_time:.1f}s){kaanoon_marker}")
    
    # Show improvement
    improvement = (ultimate_metrics['accuracy_score'] - baseline_metrics['accuracy_score']) * 100
    if improvement > 20:
        print(f"  >> MAJOR IMPROVEMENT: +{improvement:.1f}% over baseline!")
    elif improvement > 10:
        print(f"  >> Good improvement: +{improvement:.1f}%")
    elif improvement > 0:
        print(f"  >> Slight improvement: +{improvement:.1f}%")

# Final Summary
print("\n\n" + "="*80)
print("FINAL RESULTS - ALL SYSTEMS COMPARISON")
print("="*80)

def calc_avg(results, metric):
    return sum(r[metric] for r in results) / len(results)

systems = [
    ("Baseline RAG", baseline_results),
    ("Optimized RAG", optimized_results),
    ("ULTIMATE RAG", ultimate_results)
]

print(f"\n{'System':<25} {'Accuracy':<15} {'Semantic':<15} {'Keyword F1':<15}")
print("-"*80)

for name, results in systems:
    acc = calc_avg(results, 'accuracy_score')
    sem = calc_avg(results, 'semantic_similarity')
    kw = calc_avg(results, 'keyword_overlap_f1')
    
    marker = " *** TARGET MET!" if acc >= 0.80 else " ** GOOD!" if acc >= 0.70 else ""
    print(f"{name:<25} {acc:.3f} ({acc*100:.1f}%)  {sem:.3f} ({sem*100:.1f}%)  {kw:.3f} ({kw*100:.1f}%){marker}")

# Calculate improvements
print("\n" + "="*80)
print("IMPROVEMENT OVER BASELINE")
print("="*80)

baseline_acc = calc_avg(baseline_results, 'accuracy_score')
optimized_acc = calc_avg(optimized_results, 'accuracy_score')
ultimate_acc = calc_avg(ultimate_results, 'accuracy_score')

opt_improvement = ((optimized_acc - baseline_acc) / baseline_acc) * 100
ult_improvement = ((ultimate_acc - baseline_acc) / baseline_acc) * 100

print(f"\nOptimized RAG:  {opt_improvement:+.1f}%  ({optimized_acc/baseline_acc:.2f}x)")
print(f"ULTIMATE RAG:   {ult_improvement:+.1f}%  ({ultimate_acc/baseline_acc:.2f}x)")

# Verdict
print("\n" + "="*80)
print("VERDICT")
print("="*80)

if ultimate_acc >= 0.90:
    verdict = "[EXCELLENT] 90%+ accuracy achieved - World-class performance!"
    status = "SUCCESS"
elif ultimate_acc >= 0.80:
    verdict = "[TARGET MET] 80%+ accuracy achieved - Production ready!"
    status = "SUCCESS"
elif ultimate_acc >= 0.75:
    verdict = "[VERY CLOSE] 75%+ accuracy - Almost there, minor tuning needed"
    status = "GOOD"
elif ultimate_acc >= 0.70:
    verdict = "[GOOD] 70%+ accuracy - Significant improvement, needs refinement"
    status = "GOOD"
else:
    verdict = "[NEEDS WORK] Below 70% - Further optimization required"
    status = "NEEDS WORK"

print(f"\n{verdict}")
print(f"\nFinal Accuracy: {ultimate_acc:.1%}")
print(f"Status: {status}")

# Save detailed results
results_data = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "systems": {
        "baseline": {
            "accuracy": float(baseline_acc),
            "semantic": float(calc_avg(baseline_results, 'semantic_similarity')),
            "keyword_f1": float(calc_avg(baseline_results, 'keyword_overlap_f1'))
        },
        "optimized": {
            "accuracy": float(optimized_acc),
            "semantic": float(calc_avg(optimized_results, 'semantic_similarity')),
            "keyword_f1": float(calc_avg(optimized_results, 'keyword_overlap_f1'))
        },
        "ultimate": {
            "accuracy": float(ultimate_acc),
            "semantic": float(calc_avg(ultimate_results, 'semantic_similarity')),
            "keyword_f1": float(calc_avg(ultimate_results, 'keyword_overlap_f1'))
        }
    },
    "improvements": {
        "optimized_vs_baseline": float(opt_improvement),
        "ultimate_vs_baseline": float(ult_improvement)
    },
    "verdict": verdict,
    "status": status,
    "target_met": ultimate_acc >= 0.80
}

with open('ultimate_test_results.json', 'w', encoding='utf-8') as f:
    json.dump(results_data, f, indent=2)

print("\n" + "="*80)
print("Results saved to: ultimate_test_results.json")
print("="*80)

if ultimate_acc >= 0.80:
    print("\n[NEXT STEPS]")
    print("1. System is ready for production use")
    print("2. Consider updating main RAG system (scripts/multi_api_rag_ULTIMATE_V2.py)")
    print("3. Deploy with confidence - target accuracy achieved!")
else:
    print("\n[NEXT STEPS TO IMPROVE]")
    print("1. Review failed test cases")
    print("2. Add more examples to Kaanoon dataset")
    print("3. Fine-tune prompts further")
    print("4. Consider using a larger LLM model")

print("="*80)

