with open('c:/Users/LOQ/Downloads/Indian-Family-Law-Assistant-repo/backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)"""

replacement = """cors_origins = list(settings.cors_origins) if isinstance(settings.cors_origins, (list, tuple)) else ["*"]
if "https://lawgpt-frontend.pages.dev" not in cors_origins:
    cors_origins.extend(["https://lawgpt-frontend.pages.dev", "http://localhost:3000", "http://127.0.0.1:3000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\\.pages\\.dev|http://localhost:.*|http://127\\.0\\.0\\.1:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)"""

if target in content:
    content = content.replace(target, replacement, 1)
    with open('c:/Users/LOQ/Downloads/Indian-Family-Law-Assistant-repo/backend/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated CORS in main.py successfully!")
else:
    print("Target string not matched in main.py!")
