import sys
import os
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

from kaanoon_test.system_adapters.unified_advanced_rag import UnifiedAdvancedRAG

def test_10_10_accuracy():
    """Run the 5 requested scenarios to verify 10/10 accuracy improvement"""
    
    print("\n" + "="*80)
    print("⚖️ STARTING 10/10 ACCURACY BENCHMARK TEST")
    print("="*80)
    
    rag = UnifiedAdvancedRAG()
    
    scenarios = [
        {
            "name": "Insurance & Estoppel",
            "query": """A health insurer repudiates a claim citing non-disclosure of a pre-existing disease, 
            relying on a discharge summary that allegedly contains an incorrect medical history recorded by a duty doctor. 
            The insured had earlier received claim approval for the same condition, and the policy was renewed without exclusions.
            Question: What statutory, contractual, and evidentiary issues must the Consumer Commission consider while deciding 
            whether the repudiation amounts to deficiency in service, bad faith, and unfair trade practice, and how does the doctrine of estoppel apply?"""
        },
        {
            "name": "Banking & SARFAESI",
            "query": """A bank initiates SARFAESI proceedings after classifying a loan account as NPA following temporary job loss of the borrower. 
            The borrower alleges forced insurance, unconscionable loan clauses, and denial of personal hearing, and approaches the High Court 
            under Article 226 despite the availability of a DRT remedy.
            Question: What constitutional, statutory, and procedural principles govern the maintainability of the writ petition, 
            and under what circumstances can the High Court interfere with SARFAESI action?"""
        },
        {
            "name": "Family Law & Property",
            "query": """During divorce proceedings, a husband transfers substantial assets to his parents after separation. 
            The wife seeks maintenance and residence rights, alleging that the transfers were intended to defeat her claims. 
            The husband argues that the transfers were bona fide family arrangements.
            Question: What legal tests and evidentiary standards must the Family Court apply to determine whether 
            such asset transfers can be ignored or reversed for the purpose of maintenance and residence rights?"""
        },
        {
            "name": "Consumer & E-Commerce",
            "query": """A consumer purchases a high-value electronic product online advertised as “brand new.” 
            The product is later found to be previously activated, and warranty coverage is denied on the ground that the seller was unauthorized. 
            The e-commerce platform claims it is merely an intermediary and invokes an arbitration clause.
            Question: How should the Consumer Commission determine the liability of the seller, manufacturer, 
            and e-commerce platform, and what is the effect of the arbitration clause on consumer jurisdiction?"""
        },
        {
            "name": "Data Privacy & Employment",
            "query": """An employer introduces mandatory biometric attendance and facial-recognition monitoring 
            without a written privacy policy. An employee is terminated based on AI-generated attendance data, 
            which later turns out to be inaccurate.
            Question: What constitutional, statutory, and contractual issues arise concerning privacy, 
            procedural fairness, and wrongful termination, and what remedies may be available to the employee?"""
        }
    ]
    
    results = []
    
    for scenario in scenarios:
        print(f"\n🚀 Running Scenario: {scenario['name']}...")
        result = rag.query(scenario['query'])
        answer = result.get('answer', '')
        
        # Verify 10/10 markers (precedents/sections)
        verification = {
            "name": scenario['name'],
            "answer": answer,
            "markers_found": []
        }
        
        # Check for expected markers in the answer
        markers = {
            "Insurance & Estoppel": ["Manmohan Nanda", "Section 2(42)", "Estoppel"],
            "Banking & SARFAESI": ["Satyawati Tondon", "Article 226", "DRT"],
            "Family Law & Property": ["Section 39", "Transfer of Property", "Maintenance"],
            "Consumer & E-Commerce": ["E-Commerce Rules 2020", "Emaar MGF", "Arbitration"],
            "Data Privacy & Employment": ["DPDP", "Puttaswamy", "Privacy"]
        }
        
        for marker in markers.get(scenario['name'], []):
            if marker.lower() in answer.lower():
                verification["markers_found"].append(marker)
        
        results.append(verification)
        print(f"✅ Completed. Markers found: {verification['markers_found']}")

    # Save results to a report file
    report_path = PROJECT_ROOT / "test_10_10_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4)
    
    print(f"\n" + "="*80)
    print(f"⚖️ BENCHMARK COMPLETE. REPORT SAVED TO: {report_path}")
    print("="*80)

if __name__ == "__main__":
    test_10_10_accuracy()
