import os
import logging
from typing import List
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelType, ModelPlatformType
from camel.messages import BaseMessage
from camel.toolkits import SearchToolkit, BrowserToolkit
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

import sys
sys.path.append(os.path.join(os.getcwd(), 'kaanoon_test'))
from system_adapters.rag_system_adapter_ULTIMATE import SimpleWebSearchClient

class DeepResearchAgent:
    """
    Advanced Research Workforce using CAMEL-AI OWL collaboration.
    Uses existing Search Client and specialized agents.
    """
    
    def __init__(self, model_platform: ModelPlatformType = ModelPlatformType.GROQ, model_type: ModelType = ModelType.GROQ_LLAMA_3_3_70B):
        self.model_platform = model_platform
        self.model_type = model_type
        self.search_client = SimpleWebSearchClient()

    def _create_agent(self, role_name: str, system_message: str) -> ChatAgent:
        model = ModelFactory.create(
            model_platform=self.model_platform,
            model_type=self.model_type,
        )
        
        return ChatAgent(
            system_message=BaseMessage.make_assistant_message(
                role_name=role_name,
                content=system_message
            ),
            model=model,
        )

    def conduct_research(self, query: str) -> str:
        """
        Executes collaborative research using search client and OWL agents.
        """
        logger.info(f"Starting Collaborative Research for: {query}")
        
        # 1. External Search (Robust)
        logger.info("Fetching search results...")
        search_results = self.search_client.search_duckduckgo(query, max_results=5)
        search_context = "\n".join([f"Title: {r['title']}\nSnippet: {r['snippet']}\nURL: {r['url']}\n" for r in search_results])
        
        # 2. Synthesis phase (OWL Agent)
        logger.info("OWL Agent synthesizing report...")
        synthesis_agent = self._create_agent(
            "Senior Legal Researcher", 
            "You are a Senior Legal Researcher. Synthesize the provided search results into a detailed, professional legal report with citations."
        )
        
        synthesis_prompt = f"Based on the following search results, compile a comprehensive legal research report on '{query}'.\n\nSEARCH RESULTS:\n{search_context}"
        
        final_response = synthesis_agent.step(synthesis_prompt)
        return final_response.msgs[0].content

if __name__ == "__main__":
    # Test execution
    researcher = DeepResearchAgent()
    
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        topic = "Recent Supreme Court rulings on the right to privacy vs digital surveillance in India (2024-2025)"
        
    print(f"Researching: {topic}...")
    result = researcher.conduct_research(topic)
    print("\n--- RESEARCH REPORT ---")
    print(result)
