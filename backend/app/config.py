import os
from dotenv import load_dotenv

load_dotenv()

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"
FIREWORKS_MODEL_MAIN = os.getenv("FIREWORKS_MODEL_MAIN", "accounts/fireworks/models/kimi-k2p6")
FIREWORKS_MODEL_CLASSIFIER = os.getenv("FIREWORKS_MODEL_CLASSIFIER", "accounts/fireworks/models/gpt-oss-120b")
# Cheap conversational model for non-analytical regimes (advisory / pedagogy /
# orientation). These regimes don't call tools or generate analysis code, so the
# expensive tool-calling model (kimi-k2p6) is overkill. Defaults to gpt-oss-120b.
FIREWORKS_MODEL_CHAT = os.getenv("FIREWORKS_MODEL_CHAT", "accounts/fireworks/models/gpt-oss-120b")

E2B_API_KEY = os.getenv("E2B_API_KEY", "")

SANDBOX_TIMEOUT_SECONDS = int(os.getenv("SANDBOX_TIMEOUT_SECONDS", "3600"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
# Optional LEGACY fallback only. This project verifies user tokens via the JWKS
# endpoint (asymmetric ES256 signing keys) using SUPABASE_URL — no secret needed.
# Set this only if you still issue legacy HS256 tokens and want them accepted.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

MAX_STEPS = int(os.getenv("MAX_STEPS", "10"))
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
TOKEN_LIMIT = int(os.getenv("TOKEN_LIMIT", "60000"))

SESSION_IDLE_TIMEOUT_MINUTES = int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", "15"))
FEEDBACK_EVERY_N_TURNS = int(os.getenv("FEEDBACK_EVERY_N_TURNS", "3"))

# ── CORS ──────────────────────────────────────────────────────
# Comma-separated list of allowed frontend origins (NO custom domain required —
# use the localhost default for dev, add your deploy URL, e.g.
# https://your-app.vercel.app, at launch).
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

# ── Rate limits (per user, per minute) ────────────────────────
QUERY_RATE_PER_MIN = int(os.getenv("QUERY_RATE_PER_MIN", "20"))
UPLOAD_RATE_PER_MIN = int(os.getenv("UPLOAD_RATE_PER_MIN", "10"))

CHI_SQUARE_MIN_EXPECTED_CELL = int(os.getenv("CHI_SQUARE_MIN_EXPECTED_CELL", "5"))
MIN_SAMPLE_SIZE_PER_GROUP = int(os.getenv("MIN_SAMPLE_SIZE_PER_GROUP", "20"))

# ── Plans / usage caps ────────────────────────────────────────
# Single source of truth for plans. To ADD a plan later, add an entry here
# (backend-only) — the frontend renders whatever GET /billing/plans returns, so
# no frontend change is needed. `product_id` is the Dodo product for paid plans
# (None for free). `monthly_analyses` caps exploratory/confirmatory runs/month.
DEFAULT_PLAN = "free"
PLANS: dict[str, dict] = {
    "free": {
        "name": "Free",
        "monthly_analyses": int(os.getenv("FREE_MONTHLY_ANALYSES", "10")),
        "price_usd": 0,
        "product_id": None,
    },
    "pro": {
        "name": "Pro",
        "monthly_analyses": int(os.getenv("PRO_MONTHLY_ANALYSES", "300")),
        "price_usd": int(os.getenv("PRO_PRICE_USD", "19")),
        "product_id": os.getenv("DODO_PRO_PRODUCT_ID") or None,
    },
}
# Derived for the metering layer (plan id -> monthly cap).
PLAN_LIMITS = {pid: p["monthly_analyses"] for pid, p in PLANS.items()}

# ── Dodo Payments ─────────────────────────────────────────────
# Optional: billing endpoints return 503 until these are set.
DODO_API_KEY = os.getenv("DODO_PAYMENTS_API_KEY", "")
DODO_WEBHOOK_KEY = os.getenv("DODO_PAYMENTS_WEBHOOK_KEY", "")
DODO_ENVIRONMENT = os.getenv("DODO_PAYMENTS_ENVIRONMENT", "test_mode")  # or "live_mode"
DODO_PRO_PRODUCT_ID = os.getenv("DODO_PRO_PRODUCT_ID", "")
# Public URL of the frontend, used to build the post-checkout return URL.
APP_URL = os.getenv("APP_URL", "http://localhost:3000")

_REQUIRED = {
    "FIREWORKS_API_KEY": FIREWORKS_API_KEY,
    "E2B_API_KEY": E2B_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
}

for _name, _value in _REQUIRED.items():
    if not _value:
        raise RuntimeError(f"{_name} is not set. Add it to your .env file and restart the server.")
