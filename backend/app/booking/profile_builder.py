"""Shared helper to convert user_info dicts into Profile-format dicts for the frontend."""

from __future__ import annotations

from typing import Any


def build_profile(user_info: dict[str, Any], activity: str = "") -> dict[str, Any]:
    """Convert a user_info dict (from DB/mock) into a Profile-format dict."""
    return {
        "id": user_info.get("id", ""),
        "kind": "human",
        "name": user_info.get("nickname", ""),
        "presence": "online",
        "city": user_info.get("location", ""),
        "headline": user_info.get("occupation", ""),
        "score": user_info.get("match_score", 80),
        "badges": [],
        "about": (
            [f"Interested in: {', '.join(user_info.get('interests', [])[:3])}"]
            if user_info.get("interests")
            else []
        ),
        "matchReasons": [f"Matched for {activity}"] if activity else [],
        "topics": user_info.get("interests", [])[:5],
        "runningLevel": user_info.get("running_level"),
        "runningPace": user_info.get("running_pace"),
        "runningDistance": user_info.get("running_distance"),
        "availability": user_info.get("availability", []),
    }


def build_profiles(users: list[dict[str, Any]], activity: str = "") -> list[dict[str, Any]]:
    """Convert a list of user_info dicts into Profile-format dicts."""
    return [build_profile(u, activity) for u in users]
