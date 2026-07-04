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

CHI_SQUARE_MIN_EXPECTED_CELL = int(os.getenv("CHI_SQUARE_MIN_EXPECTED_CELL", "5"))
MIN_SAMPLE_SIZE_PER_GROUP = int(os.getenv("MIN_SAMPLE_SIZE_PER_GROUP", "20"))

_REQUIRED = {
    "FIREWORKS_API_KEY": FIREWORKS_API_KEY,
    "E2B_API_KEY": E2B_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
}

for _name, _value in _REQUIRED.items():
    if not _value:
        raise RuntimeError(f"{_name} is not set. Add it to your .env file and restart the server.")
