"""Check which API keys are configured (never prints secret values)."""
from app.config import settings

checks = [
    ("GEMINI_API_KEY (embeddings)", settings.gemini_api_key),
    ("OPENAI_API_KEY (Codex reasoning)", settings.openai_api_key),
    ("SUPABASE_SERVICE_ROLE_KEY", settings.supabase_service_role_key),
]

for name, value in checks:
    if value:
        print(f"  OK   {name}  (len={len(value)})")
    else:
        print(f"  MISS {name}")

print(f"\n  model: gemini-embedding-2 ({settings.embed_dim}d), codex: {settings.codex_model}")
