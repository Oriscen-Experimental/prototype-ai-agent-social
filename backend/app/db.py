"""
Database connection module.

Provides user data for matching. Two modes:
1. PostgreSQL (if POSTGRES_URI is set) - connects to the shared ai-service DB
2. In-memory mock (fallback) - loads users from JSON seed files
"""

from __future__ import annotations

import json
import logging
import os
import random
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserRecord:
    """Simplified user record for matching."""
    id: str
    email: str
    nickname: str
    gender: str  # "male" | "female"
    birthday: str  # ISO date
    location: str
    occupation: str
    hobby: str
    interests: list[str] = field(default_factory=list)
    archetype: str | None = None
    is_mock: bool = True  # True if generated/mock user, False if real Google-logged-in user


class UserDB:
    """User database abstraction for matching queries."""

    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}
        self._pg_url: str | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize DB - try PostgreSQL first, fall back to JSON seed."""
        self._pg_url = (os.getenv("POSTGRES_URI") or "").strip() or None

        if self._pg_url:
            try:
                self._load_from_postgres()
                self._initialized = True
                return
            except Exception as e:
                logger.warning("[db] PostgreSQL connection failed, falling back to JSON: %s", e)

        self._load_from_json_seed()
        self._initialized = True

    def _load_from_postgres(self) -> None:
        """Load users from PostgreSQL (same DB as ai-service)."""
        import psycopg2

        conn = psycopg2.connect(self._pg_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.id, u.email, u.gender, u.birthday, u.location, u.occupation,
                           uap.profile
                    FROM public.users u
                    LEFT JOIN public.user_ai_profiles uap ON u.id = uap.user_id
                    WHERE u.is_active = true AND u.is_deleted = false
                """)
                for row in cur.fetchall():
                    uid, email, gender, birthday, location, occupation, profile_json = row
                    profile = profile_json if isinstance(profile_json, dict) else {}
                    interests = profile.get("interests", []) or []
                    hobbies = profile.get("hobbies", []) or []
                    archetype = profile.get("archetype")

                    is_mock = bool(email and "@oriscen.generated" in email)

                    self._users[str(uid)] = UserRecord(
                        id=str(uid),
                        email=email or "",
                        nickname=profile.get("name", "") or email or "",
                        gender=(gender or "").lower(),
                        birthday=str(birthday) if birthday else "",
                        location=location or "",
                        occupation=occupation or "",
                        hobby=", ".join(hobbies[:3]) if hobbies else "",
                        interests=interests if isinstance(interests, list) else [],
                        archetype=archetype,
                        is_mock=is_mock,
                    )
            logger.info("[db] loaded %d users from PostgreSQL", len(self._users))
        finally:
            conn.close()

    def _load_from_json_seed(self) -> None:
        """Load users from JSON seed files and generate additional mock users."""
        seed_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "generated_user_samples_10.json"
        )
        # Also try workspace root
        if not os.path.exists(seed_path):
            seed_path = "/workspaces/codespaces-blank/generated_user_samples_10.json"

        seed_users: list[dict[str, Any]] = []
        if os.path.exists(seed_path):
            try:
                with open(seed_path) as f:
                    seed_users = json.load(f)
                logger.info("[db] loaded %d seed users from JSON", len(seed_users))
            except Exception as e:
                logger.warning("[db] failed to load seed JSON: %s", e)

        # Parse seed users
        for item in seed_users:
            user_data = item.get("user", {})
            uid = user_data.get("id", str(uuid.uuid4()))
            self._users[uid] = UserRecord(
                id=uid,
                email=user_data.get("email", ""),
                nickname=user_data.get("nickname", ""),
                gender=(user_data.get("gender") or "").lower(),
                birthday=user_data.get("birthday", ""),
                location=user_data.get("location", ""),
                occupation=user_data.get("occupation", ""),
                hobby=user_data.get("hobby", ""),
                interests=[user_data.get("hobby", "")] if user_data.get("hobby") else [],
                archetype=None,
                is_mock=True,
            )

        # Generate additional mock users to reach ~300 total for demo
        if len(self._users) < 50:
            self._generate_mock_users(300 - len(self._users))

    def _generate_mock_users(self, count: int) -> None:
        """Generate mock users for demo purposes."""
        first_names_f = ["Emma", "Sophia", "Olivia", "Ava", "Mia", "Luna", "Chloe", "Lily",
                         "Zoe", "Emily", "Grace", "Ella", "Hannah", "Aria", "Nora", "Ruby",
                         "Maya", "Iris", "Jade", "Ivy", "Rosa", "Nina", "Sara", "Lena", "Yuki"]
        first_names_m = ["Liam", "Noah", "James", "Oliver", "Ethan", "Lucas", "Mason", "Leo",
                         "Alex", "Ryan", "Jack", "Max", "Sam", "Ben", "Jake", "Tom",
                         "Dan", "Marcus", "Chris", "Kyle", "Derek", "Kai", "Ravi", "Wei", "Jin"]
        last_names = ["Smith", "Chen", "Wang", "Kim", "Park", "Johnson", "Brown", "Garcia",
                      "Lee", "Wilson", "Davis", "Miller", "Taylor", "Thomas", "Zhang", "Li"]
        cities = ["New York", "San Francisco", "Los Angeles", "Chicago", "Seattle",
                  "Austin", "Boston", "Denver", "Portland", "Miami",
                  "Shanghai", "Beijing", "Tokyo", "London", "Singapore"]
        hobbies = ["running", "hiking", "yoga", "tennis", "basketball", "swimming",
                   "photography", "cooking", "reading", "painting", "cycling", "climbing",
                   "surfing", "skiing", "dancing", "gaming", "music", "coffee",
                   "travel", "meditation", "boxing", "badminton", "soccer", "volleyball"]
        occupations = ["Software Engineer", "Designer", "Product Manager", "Teacher",
                       "Marketing Manager", "Data Scientist", "Consultant", "Writer",
                       "Entrepreneur", "Student", "Doctor", "Photographer", "Chef"]
        levels = ["beginner", "intermediate", "advanced"]

        for _ in range(count):
            gender = random.choice(["male", "female"])
            first = random.choice(first_names_m if gender == "male" else first_names_f)
            last = random.choice(last_names)
            city = random.choice(cities)
            hobby_list = random.sample(hobbies, k=random.randint(2, 5))
            age = random.randint(20, 45)
            year = 2026 - age
            month = random.randint(1, 12)
            day = random.randint(1, 28)

            uid = str(uuid.uuid4())
            self._users[uid] = UserRecord(
                id=uid,
                email=f"generated+{uid[:8]}@oriscen.generated",
                nickname=f"{first} {last}",
                gender=gender,
                birthday=f"{year}-{month:02d}-{day:02d}",
                location=city,
                occupation=random.choice(occupations),
                hobby=hobby_list[0],
                interests=hobby_list,
                archetype=random.choice(["Explorer", "Builder", "Artist", "Guardian"]),
                is_mock=True,
            )

        logger.info("[db] generated %d mock users (total: %d)", count, len(self._users))

    def match(
        self,
        *,
        activity: str | None = None,
        location: str | None = None,
        gender: str | None = None,
        exclude_user_id: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """
        Simple matching: hard-filter → random score → sort → top N.

        Returns list of dicts with user info + match score.
        """
        if not self._initialized:
            self.initialize()

        candidates: list[UserRecord] = []
        for user in self._users.values():
            # Exclude the requesting user
            if exclude_user_id and user.id == exclude_user_id:
                continue

            # Hard constraint: gender
            if gender and gender not in ("any", ""):
                if user.gender != gender.lower():
                    continue

            # Hard constraint: location (fuzzy - check if city name appears)
            if location:
                loc_lower = location.lower()
                user_loc_lower = user.location.lower()
                # Match if any part of location matches
                if loc_lower not in user_loc_lower and user_loc_lower not in loc_lower:
                    # Also check city name parts
                    loc_parts = loc_lower.replace(",", " ").split()
                    user_parts = user_loc_lower.replace(",", " ").split()
                    if not any(lp in user_parts for lp in loc_parts) and not any(up in loc_parts for up in user_parts):
                        continue

            # Soft constraint: activity/interest (used for scoring, not filtering)
            candidates.append(user)

        # Assign random scores with activity-based boost
        results: list[dict[str, Any]] = []
        for user in candidates:
            base_score = random.randint(30, 85)

            # Boost if activity matches interests
            if activity:
                act_lower = activity.lower()
                for interest in user.interests:
                    if act_lower in interest.lower() or interest.lower() in act_lower:
                        base_score = min(100, base_score + random.randint(10, 25))
                        break

            results.append({
                "id": user.id,
                "email": user.email,
                "nickname": user.nickname,
                "gender": user.gender,
                "birthday": user.birthday,
                "location": user.location,
                "occupation": user.occupation,
                "hobby": user.hobby,
                "interests": user.interests,
                "archetype": user.archetype,
                "is_mock": user.is_mock,
                "match_score": base_score,
            })

        # Sort by score descending
        results.sort(key=lambda x: x["match_score"], reverse=True)

        return results[:limit]

    def get_user(self, user_id: str) -> UserRecord | None:
        """Get a user by ID."""
        return self._users.get(user_id)

    @property
    def user_count(self) -> int:
        return len(self._users)


# Global singleton
user_db = UserDB()
