"""
Helpers for producing bearer tokens in tests and scripts without relying on mock tokens.

Tokens are generated with the configured JWT secret; callers can also supply an
explicit token via environment variable (e.g. LOAD_TEST_BEARER_TOKEN) to avoid
regenerating on every invocation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config import get_settings
from reranker.jwt_auth import JWTAuthenticator


@dataclass
class TokenOptions:
    email: str
    role: str = "user"
    user_id: int | None = None
    env_var: str = "LOAD_TEST_BEARER_TOKEN"


def resolve_bearer_token(options: TokenOptions) -> str:
    """
    Return a ready-to-use bearer token for API requests.

    Precedence:
    1. Use the token provided in the configured environment variable.
    2. Generate a short-lived JWT using the configured JWT secret.
    """
    existing = os.getenv(options.env_var, "").strip()
    if existing:
        return existing

    settings = get_settings()
    token_user_id = options.user_id if options.user_id is not None else _fallback_user_id(options.email)
    return JWTAuthenticator.generate_token(user_id=token_user_id, email=options.email, role=options.role)


def _fallback_user_id(email: str) -> int:
    normalized = email.strip().lower()
    # Mirror deterministic hash in app for consistency when DB user rows are seeded.
    import hashlib

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return int(digest[:7], 16)
