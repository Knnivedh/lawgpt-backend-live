from pathlib import Path

p = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\nodes\information_gatherer.py")
t = p.read_text(encoding="utf-8")

# 1. Update imports
old_imp = "from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint"
new_imp = "from langchain_openai import ChatOpenAI\nimport re"
assert old_imp in t, "old_imp not found"
t = t.replace(old_imp, new_imp, 1)

# 2. Update __init__
old_init = """    def __init__(self, huggingface_api_key: str = None):
        \"\"\"Initialize the InformationGatherer with LLM.\"\"\"
        from config import get_settings
        settings = get_settings()
        
        api_key = huggingface_api_key or settings.huggingface_api_key
        
        self.llm = ChatHuggingFace(
            llm=HuggingFaceEndpoint(
                repo_id=settings.llm_model,
                huggingfacehub_api_token=api_key,
                task="text-generation",
                max_new_tokens=256,
                temperature=0.1,  # Lower temperature for more consistent extraction
            )
        )"""

new_init = """    def __init__(self, huggingface_api_key: str = None):
        \"\"\"Initialize the InformationGatherer with Dahl LLMs.\"\"\"
        from config import get_settings
        settings = get_settings()
        
        dahl_key = getattr(settings, "dahl_api_key", None) or os.getenv("DAHL_API_KEY") or "dahl_4gBX24FQWzR8sTxVBK1fn7UN8dAQArhGT"
        dahl_base = getattr(settings, "dahl_base_url", None) or os.getenv("DAHL_BASE_URL") or "https://inference.dahl.global/v1"
        model_name = getattr(settings, "llm_model", "deepseek-ai/DeepSeek-V4-Flash-0731")
        fb_model = getattr(settings, "fallback_llm_model", "MiniMaxAI/MiniMax-M2.7")
        
        self.llm = ChatOpenAI(
            model=model_name,
            api_key=dahl_key,
            base_url=dahl_base,
            max_tokens=500,
            temperature=0.1,
            timeout=8.0,
            max_retries=0,
        )
        self.fallback_llm = ChatOpenAI(
            model=fb_model,
            api_key=dahl_key,
            base_url=dahl_base,
            max_tokens=500,
            temperature=0.1,
            timeout=12.0,
            max_retries=0,
        )"""

assert old_init in t, "old_init not found"
t = t.replace(old_init, new_init, 1)

# 3. Update _generate_question LLM call
old_gen = """            response = self.llm.invoke(conversation)
            question = response.content.strip()"""

new_gen = """            try:
                response = self.llm.invoke(conversation)
            except Exception as e_prim:
                logger.warning(f"Primary LLM in question generation failed ({e_prim}), using fallback...")
                response = self.fallback_llm.invoke(conversation)
            content_clean = re.sub(r'<think>.*?</think>', '', response.content, flags=re.DOTALL).strip()
            question = content_clean"""

assert old_gen in t, "old_gen not found"
t = t.replace(old_gen, new_gen, 1)

# 4. Update _extract_information LLM call
old_ext = """            response = self.llm.invoke(conversation)
            response_text = response.content.strip()"""

new_ext = """            try:
                response = self.llm.invoke(conversation)
            except Exception as e_prim:
                logger.warning(f"Primary LLM in extraction failed ({e_prim}), using fallback...")
                response = self.fallback_llm.invoke(conversation)
            content_clean = re.sub(r'<think>.*?</think>', '', response.content, flags=re.DOTALL).strip()
            response_text = content_clean"""

assert old_ext in t, "old_ext not found"
t = t.replace(old_ext, new_ext, 1)

p.write_text(t, encoding="utf-8")
print("SUCCESS: Migrated information_gatherer.py to Dahl LLM!")
