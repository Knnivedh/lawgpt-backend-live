from pathlib import Path

p = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\nodes\generator.py")
t = p.read_text(encoding="utf-8")

# Set primary timeout to 8.0s, fallback timeout to 12.0s
t = t.replace("timeout=25.0", "timeout=8.0")
# Update fallback_llm timeout specifically
target = """fallback_llm = ChatOpenAI(
    model=fb_model,
    api_key=dahl_key,
    base_url=dahl_base,
    max_tokens=3500,
    temperature=0.2,
    timeout=8.0,"""

replacement = """fallback_llm = ChatOpenAI(
    model=fb_model,
    api_key=dahl_key,
    base_url=dahl_base,
    max_tokens=3500,
    temperature=0.2,
    timeout=12.0,"""

if target in t:
    t = t.replace(target, replacement, 1)

p.write_text(t, encoding="utf-8")
print("SUCCESS: Optimized LLM timeouts for fast recurrence!")
