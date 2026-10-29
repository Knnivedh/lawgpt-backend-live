from pathlib import Path

p = Path(r"c:\Users\LOQ\Downloads\Indian-Family-Law-Assistant-repo\backend\main.py")
with open(p, "r", encoding="utf-8") as f:
    content = f.read()

# Replace root endpoint
old_root = '@app.get("/")\nasync def root():'
old_root_crlf = '@app.get("/")\r\nasync def root():'
new_root = '@app.get("/api/info")\nasync def api_info():'

if old_root in content:
    content = content.replace(old_root, new_root)
    print("Replaced LF root")
elif old_root_crlf in content:
    content = content.replace(old_root_crlf, new_root)
    print("Replaced CRLF root")
else:
    print("Could not find root route")

mount_code = """
# Mount static frontend
from fastapi.staticfiles import StaticFiles

_frontend_dir = Path(__file__).resolve().parent / "static_frontend"
if _frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
"""

target_lf = 'if __name__ == "__main__":'
target_crlf = 'if __name__ == "__main__":'

if "StaticFiles" not in content and target_lf in content:
    content = content.replace(target_lf, mount_code.strip() + "\n\n\n" + target_lf)
    print("Mounted StaticFiles before main entry")

with open(p, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: main.py updated!")
