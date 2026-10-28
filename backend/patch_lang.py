from pathlib import Path

p = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\lang_utils.py")
t = p.read_text(encoding="utf-8")

old_code = """        code = detect(text)
        logger.debug(f"[lang_utils] detected language: {code!r} for text: {text[:60]!r}")
        return code"""

new_code = """        code = detect(text)
        # If detected language is not a supported Indic language, treat as English
        if code not in LANGUAGE_NAMES or code not in ("hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "or", "as", "ur"):
            code = "en"
        logger.debug(f"[lang_utils] detected language: {code!r} for text: {text[:60]!r}")
        return code"""

assert old_code in t, "old_code not found in lang_utils.py"
t = t.replace(old_code, new_code, 1)
p.write_text(t, encoding="utf-8")
print("SUCCESS: Patched lang_utils.py to ensure English queries stay English!")
