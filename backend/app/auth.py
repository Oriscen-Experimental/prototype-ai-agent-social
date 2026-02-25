"""Google OAuth2 authentication module.

Verifies Google ID tokens using Google's OAuth2 library.
"""
from __future__ import annotations

import logging
import os

from google.oauth2 import id_token
from google.auth.transport import requests

logger = logging.getLogger(__name__)


def get_google_client_id() -> str:
    """Get the Google OAuth Client ID from environment."""
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    if not client_id:
        raise RuntimeError(
            "Missing GOOGLE_CLIENT_ID. Set it to your OAuth 2.0 Client ID."
        )
    return client_id


def verify_google_id_token(token: str) -> dict[str, any]:
    """Verify a Google ID token and return user info.

    Args:
        token: The ID token from @react-oauth/google

    Returns:
        dict with: uid, email, displayName, photoURL

    Raises:
        ValueError: If token is invalid or expired
    """
    client_id = get_google_client_id()

    try:
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)

        # Verify the token was issued by Google
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Invalid token issuer")

        return {
            "uid": idinfo["sub"],
            "email": idinfo.get("email"),
            "displayName": idinfo.get("name"),
            "photoURL": idinfo.get("picture"),
        }
    except ValueError as e:
        raise ValueError(f"Invalid ID token: {e}") from e
    except Exception as e:
        raise ValueError(f"Token verification failed: {e}") from e


def google_auth_config_status() -> dict[str, any]:
    """Return Google auth configuration status for health check."""
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()

    if not client_id:
        return {
            "provider": "google",
            "configured": False,
            "hint": "Set GOOGLE_CLIENT_ID to your OAuth 2.0 Client ID",
        }

    # Mask the client ID for security
    masked = client_id[:20] + "..." if len(client_id) > 20 else client_id

    return {
        "provider": "google",
        "configured": True,
        "clientId": masked,
    }
