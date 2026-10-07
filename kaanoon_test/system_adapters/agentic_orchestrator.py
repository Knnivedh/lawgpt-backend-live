"""
AGENTIC ORCHESTRATOR - Main system that coordinates LLM Router + Parametric RAG
Flow: User → LLM Analyzes → Routes → RAG (if needed) → LLM Generates Answer
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any
import time
from dotenv import load_dotenv

# Add parent directories to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv(project_root / "config" / ".env")

from openai import OpenAI
from kaanoon_test.system_adapters.agentic_llm_router import AgenticLLMRouter
from kaanoon_test.system_adapters.parametric_rag_system import ParametricRAGSystem

class AgenticOrchestrator:
    """
    Intelligent orchestrator that:
    1. Uses LLM to analyze query
    2. Routes to RAG only if needed
    3. Generates final response
    """
    
    def __init__(self):
        """Initialize agentic system"""
        print("\n" + "="*80)
        print("INITIALIZING AGENTIC RAG ORCHESTRATOR")
        print("="*80)
        
        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=os.getenv("NVIDIA_API_KEY"),
            base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        )
        self.model = os.getenv("NVIDIA_MODEL_NAME", "nvidia/llama-3.1-nemotron-70b-instruct")
        
        # Initialize components
        print("[1/2] Initializing LLM Router...")
        self.router = AgenticLLMRouter(self.client)
        
        print("[2/2] Initializing Parametric RAG...")
        self.rag = ParametricRAGSystem()
        
        print("\n✓ AGENTIC SYSTEM READY\n")
        print("="*80)
    
    def query(self, user_query: str, target_language: str = None) -> Dict[str, Any]:
        """
        Process user query through agentic system
        
        Flow:
        1. LLM analyzes query → decides if RAG needed
        2. If no RAG: LLM responds directly
        3. If RAG: Call parametric RAG → LLM generates answer from context
        
        Args:
            user_query: User's question
            target_language: Optional language code
        
        Returns:
            Dict with answer, metadata, timing info
        """
        start_time = time.time()
        
        print("\n" + "="*80)
        print(f"USER QUERY: {user_query}")
        print("="*80)
        
        try:
            # STEP 1: LLM analyzes and routes
            print("\n[STEP 1] LLM Router analyzing query...")
            routing_decision = self.router.analyze_and_route(user_query)
            
            needs_rag = routing_decision.get('needs_rag', True)
            query_type = routing_decision.get('query_type', 'unknown')
            reasoning = routing_decision.get('reasoning', '')
            confidence = routing_decision.get('confidence', 0.5)
            
            print(f"  → Query Type: {query_type}")
            print(f"  → Needs RAG: {needs_rag}")
            print(f"  → Confidence: {confidence:.2f}")
            print(f"  → Reasoning: {reasoning}")
            
            # STEP 2A: Direct response (no RAG)
            if not needs_rag:
                print("\n[STEP 2A] Generating direct response (no RAG)...")
                
                direct_response = routing_decision.get('direct_response')
                if direct_response:
                    answer = direct_response
                else:
                    answer = self.router.generate_direct_response(user_query)
                
                total_time = time.time() - start_time
                print(f"\n✓ Direct response generated in {total_time:.2f}s")
                
                return {
                    'answer': answer,
                    'context': 'No RAG needed',
                    'sources': [],
                    'latency': total_time,
                    'used_rag': False,
                    'query_type': query_type,
                    'reasoning': reasoning,
                    'detected_language': target_language or 'en',
                    'routing_confidence': confidence
                }
            
            # STEP 2B: RAG + Generation path
            print("\n[STEP 2B] RAG required - retrieving documents...")
            
            rag_params = routing_decision.get('rag_params', {})
            retrieval_result = self.rag.retrieve_with_params(user_query, rag_params)
            
            documents = retrieval_result.get('documents', [])
            context = retrieval_result.get('context', '')
            metadata = retrieval_result.get('metadata', {})
            
            print(f"  → Retrieved {len(documents)} documents")
            print(f"  → Domain: {metadata.get('search_domain', 'general')}")
            print(f"  → Retrieval time: {metadata.get('retrieval_time', 0):.2f}s")
            
            # STEP 3: Generate answer from context
            print("\n[STEP 3] Generating answer from retrieved context...")
            
            answer = self._generate_answer_from_context(
                user_query,
                context,
                documents,
                rag_params
            )
            
            total_time = time.time() - start_time
            print(f"\n✓ Complete agentic response in {total_time:.2f}s")
            
            # Format sources
            sources = [
                {
                    'rank': i + 1,
                    'score': doc.get('score', 0),
                    'source': doc.get('metadata', {}).get('source', 'Unknown'),
                    'text_preview': doc.get('text', '')[:200]
                }
                for i, doc in enumerate(documents[:5])
            ]
            
            return {
                'answer': answer,
                'context': context,
                'sources': sources,
                'latency': total_time,
                'used_rag': True,
                'query_type': query_type,
                'reasoning': reasoning,
                'rag_params': rag_params,
                'retrieval_metadata': metadata,
                'detected_language': target_language or 'en',
                'routing_confidence': confidence
            }
            
        except Exception as e:
            print(f"\n[ERROR] Agentic orchestration failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback
            return {
                'answer': "I encountered an error processing your query. Please try again or rephrase your question.",
                'context': '',
                'sources': [],
                'latency': time.time() - start_time,
                'used_rag': False,
                'query_type': 'error',
                'error': str(e)
            }
    
    def _generate_answer_from_context(
        self,
        query: str,
        context: str,
        documents: list,
        rag_params: Dict
    ) -> str:
        """Generate comprehensive answer from retrieved context"""
        
        # Build generation prompt
        domain = rag_params.get('search_domain', 'general')
        complexity = rag_params.get('complexity', 'medium')
        
        prompt = f"""You are an expert Indian legal assistant. Answer the user's query based on the retrieved legal documents.

USER QUERY: {query}

LEGAL DOMAIN: {domain}
QUERY COMPLEXITY: {complexity}

RETRIEVED LEGAL CONTEXT:
{context}

Instructions:
1. Provide a DIRECT, CONCISE answer to the specific question
2. Cite relevant sections, acts, or case law from the context
3. Structure your response clearly with headings if needed
4. Be accurate and professional
5. If the context doesn't fully answer the query, state what information is missing

Format your response as:
- **Direct Answer:** [Clear answer to the question]
- **Legal Basis:** [Relevant sections, acts, provisions]
- **Key Points:** [Important details from context]
- **Important Notes:** [Caveats, limitations, or additional information]

Generate your response:"""

        try:
            # Determine token count based on complexity
            max_tokens = {
                'simple': 180,
                'medium': 350,
                'complex': 550
            }.get(complexity, 350)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"[ERROR] Answer generation failed: {e}")
            # Fallback to context summary
            return f"Based on the legal documents, {context[:500]}..."


# Example usage
if __name__ == "__main__":
    orchestrator = AgenticOrchestrator()
    
    # Test queries
    test_queries = [
        "Hi",
        "What is IPC Section 302?",
        "DPDP Act processing of personal data",
        "Good morning",
        "GST for IT professionals with 10 LPA income"
    ]
    
    for query in test_queries:
        print("\n" + "#"*80)
        result = orchestrator.query(query)
        print(f"\nANSWER:\n{result['answer']}")
        print(f"\nUsed RAG: {result['used_rag']}")
        print(f"Query Type: {result['query_type']}")
        print(f"Time: {result['latency']:.2f}s")
