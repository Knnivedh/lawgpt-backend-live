from pathlib import Path

p = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\main.py")
t = p.read_text(encoding="utf-8")

old_text = "import json\nimport os"
new_text = "import json\nimport os\nimport re"

assert old_text in t, "old_text not found in main.py"
t = t.replace(old_text, new_text, 1)

p.write_text(t, encoding="utf-8")
print("SUCCESS: Added import re to main.py!")
