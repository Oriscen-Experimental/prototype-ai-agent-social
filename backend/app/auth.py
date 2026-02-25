"""Firebase Admin SDK authentication module.

Verifies Google ID tokens using the Firebase Admin SDK.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

FIREBASE_PROJECT_ID = "oriscen-social-ios"


@lru_cache(maxsize=1)
def _get_firebase_app():
    """Initialize Firebase Admin SDK with service account credentials.

    Supports FIREBASE_SERVICE_ACCOUNT_JSON as:
    - A file path (e.g., /etc/secrets/firebase-credentials.json)
    - Raw JSON string content
    """
    import firebase_admin
    from firebase_admin import credentials

    env_value = (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()

    if not env_value:
        raise RuntimeError(
            "Missing FIREBASE_SERVICE_ACCOUNT_JSON. "
            "Set it to a file path or raw JSON string."
        )

    cred = None

    # Check if it's a file path
    if os.path.exists(env_value):
        logger.info("[auth] using firebase service account file=%s", env_value)
        cred = credentials.Certificate(env_value)
    else:
        # Try to parse as JSON string
        try:
            service_account_info = json.loads(env_value)
            logger.info("[auth] using firebase service account from JSON string")
            cred = credentials.Certificate(service_account_info)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"FIREBASE_SERVICE_ACCOUNT_JSON is not a valid file path or JSON: {e}"
            ) from e

    return firebase_admin.initialize_app(cred, {
        "projectId": FIREBASE_PROJECT_ID,
    })


def verify_google_id_token(id_token: str) -> dict[str, any]:
    """Verify a Google ID token and return user info.

    Args:
        id_token: The ID token from Google Sign-In (frontend)

    Returns:
        dict with: uid, email, displayName, photoURL

    Raises:
        ValueError: If token is invalid or expired
    """
    from firebase_admin import auth

    # Ensure Firebase app is initialized
    _get_firebase_app()

    try:
        decoded_token = auth.verify_id_token(id_token)

        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "displayName": decoded_token.get("name"),
            "photoURL": decoded_token.get("picture"),
        }
    except auth.InvalidIdTokenError as e:
        raise ValueError(f"Invalid ID token: {e}") from e
    except auth.ExpiredIdTokenError as e:
        raise ValueError(f"Expired ID token: {e}") from e
    except Exception as e:
        raise ValueError(f"Token verification failed: {e}") from e


def firebase_config_status() -> dict[str, any]:
    """Return Firebase configuration status for health check."""
    env_value = (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()

    if not env_value:
        return {
            "provider": "firebase",
            "projectId": FIREBASE_PROJECT_ID,
            "configured": False,
            "hint": "Set FIREBASE_SERVICE_ACCOUNT_JSON to a file path or raw JSON string",
        }

    is_file = os.path.exists(env_value)

    return {
        "provider": "firebase",
        "projectId": FIREBASE_PROJECT_ID,
        "configured": True,
        "authMode": "file" if is_file else "json_string",
    }
