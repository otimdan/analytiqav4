"""Supabase JWT verification for the FastAPI backend.

The frontend authenticates with Supabase Auth and sends the resulting access
token as `Authorization: Bearer <jwt>` on every request. We verify that token and
extract the user id so the backend can scope data to the authenticated user
instead of trusting the `X-Session-Id` header alone.

This project uses Supabase's **JWT Signing Keys** (asymmetric, ECC/ES256), so
tokens are verified against the project's public keys published at the JWKS
endpoint — no shared secret needed. A legacy HS256 path (shared secret) is kept
as a fallback for older tokens if `SUPABASE_JWT_SECRET` happens to be set.
"""
import asyncio
import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException

from app.config import SUPABASE_URL, SUPABASE_JWT_SECRET


class AuthUser:
    def __init__(self, id: str, email: str | None = None):
        self.id = id
        self.email = email


_jwks_client: PyJWKClient | None = None


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        # PyJWKClient caches fetched keys, so this is one network call, then cached.
        _jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def _verify(token: str) -> dict:
    """Synchronous verify (runs in a worker thread). Chooses the method from the
    token's own `alg`: asymmetric keys via JWKS, or legacy HS256 shared secret."""
    alg = jwt.get_unverified_header(token).get("alg", "")
    if alg == "HS256":
        if not SUPABASE_JWT_SECRET:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
        return jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
    signing_key = _jwks().get_signing_key_from_jwt(token)
    return jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"], audience="authenticated")


async def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated. Please sign in.")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = await asyncio.to_thread(_verify, token)
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your session expired. Please sign in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")
    except Exception:
        # JWKS fetch failures, unknown key id, etc.
        raise HTTPException(status_code=401, detail="Could not verify authentication token.")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication token is missing a subject.")
    return AuthUser(id=user_id, email=payload.get("email"))
