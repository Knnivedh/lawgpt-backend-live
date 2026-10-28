from pathlib import Path

p = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\nodes\generator.py")
t = p.read_text(encoding="utf-8")
t = t.replace("timeout=12.0", "timeout=25.0")
t = t.replace("chunk.get('content', '')[:1800]", "chunk.get('content', '')[:700]")
p.write_text(t, encoding="utf-8")
print("SUCCESS: Optimized generator.py!")
