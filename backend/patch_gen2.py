from pathlib import Path

p = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\nodes\generator.py")
t = p.read_text(encoding="utf-8")

# 1. Increase max_tokens from 1500 to 3500
t = t.replace("max_tokens=1500", "max_tokens=3500")

# 2. Add empty response guard
target = """        logger.info(f"✅ Generated response: {len(response_content)} characters")"""
replacement = """        if len(response_content.strip()) < 60:
            logger.warning("⚠️ Response too short after think stripping, synthesizing legal advice...")
            raise ValueError("Response too short")
        logger.info(f"✅ Generated response: {len(response_content)} characters")"""

if target in t:
    t = t.replace(target, replacement, 1)

p.write_text(t, encoding="utf-8")
print("SUCCESS: Patched generator.py max_tokens and empty guard!")
