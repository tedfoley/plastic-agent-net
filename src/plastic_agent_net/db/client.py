"""Supabase client singleton from environment variables."""

from __future__ import annotations

import os

from supabase import Client, create_client

_client: Client | None = None


def get_supabase_client(
    url: str | None = None,
    key: str | None = None,
) -> Client:
    """Return a Supabase client, creating one if needed.

    Uses SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars by default.
    Falls back to SUPABASE_ANON_KEY if service role key is not set.
    """
    global _client
    if _client is not None:
        return _client

    url = url or os.environ.get("SUPABASE_URL", "")
    key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set"
        )

    _client = create_client(url, key)
    return _client


def reset_client() -> None:
    """Reset the singleton (useful for testing)."""
    global _client
    _client = None
