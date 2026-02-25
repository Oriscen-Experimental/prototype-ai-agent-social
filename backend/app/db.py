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
    # Running-specific fields
    running_level: str | None = None  # "beginner" | "intermediate" | "advanced" | "competitive"
    running_pace: str | None = None  # "easy" | "moderate" | "fast" | "racing" | "any"
    running_distance: str | None = None  # "<5km" | "5-10km" | "10-21km" | "21km+" | "varies"
    availability: list[str] = field(default_factory=list)  # ["weekday_morning", "weekday_evening", "weekend_morning", ...]


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

        # Running-specific attributes
        running_levels = ["beginner", "intermediate", "advanced", "competitive"]
        running_paces = ["easy", "moderate", "fast", "racing"]
        running_distances = ["<5km", "5-10km", "10-21km", "21km+"]
        availability_slots = [
            "weekday_morning", "weekday_lunch", "weekday_evening",
            "weekend_morning", "weekend_afternoon"
        ]

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

            # Generate running attributes if user is a runner
            is_runner = "running" in hobby_list
            running_level = random.choice(running_levels) if is_runner else None
            running_pace = random.choice(running_paces) if is_runner else None
            running_distance = random.choice(running_distances) if is_runner else None
            # Runners have 1-3 available time slots
            user_availability = random.sample(
                availability_slots, k=random.randint(1, 3)
            ) if is_runner else []

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
                running_level=running_level,
                running_pace=running_pace,
                running_distance=running_distance,
                availability=user_availability,
            )

        logger.info("[db] generated %d mock users (total: %d)", count, len(self._users))

    def match(
        self,
        *,
        activity: str | None = None,
        location: str | None = None,
        gender: str | None = None,
        exclude_user_id: str | None = None,
        # Running-specific filters (hard constraints)
        level: str | None = None,
        pace: str | None = None,
        availability_slots: list[str] | None = None,
        headcount: int = 3,
        limit: int = 200,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Enhanced matching with running-specific filters.

        Hard filters: location, gender, level, pace, availability (time slots)

        For availability: finds the BEST slot that has enough candidates,
        so all matched users can meet at the same time.

        Returns:
            - list of dicts with user info + match score
            - stats dict with filtering breakdown and selected_slot
        """
        if not self._initialized:
            self.initialize()

        # Track filtering stats
        stats: dict[str, Any] = {
            "total_users": len(self._users),
            "after_location_filter": 0,
            "after_gender_filter": 0,
            "after_activity_filter": 0,
            "after_level_filter": 0,
            "after_pace_filter": 0,
            "candidates_per_slot": {},  # slot -> count of available users
            "selected_slot": None,  # the chosen time slot for the group
            "final_candidates": 0,
        }

        is_running = activity and activity.lower() in ("running", "run", "jog", "jogging")

        # Phase 1: Filter by location, gender, activity, level, pace
        # (everything except time slot - we need to analyze slots separately)
        pre_slot_candidates: list[UserRecord] = []
        for user in self._users.values():
            # Exclude the requesting user
            if exclude_user_id and user.id == exclude_user_id:
                continue

            # Hard constraint: location (fuzzy - check if city name appears)
            if location:
                loc_lower = location.lower()
                user_loc_lower = user.location.lower()
                if loc_lower not in user_loc_lower and user_loc_lower not in loc_lower:
                    loc_parts = loc_lower.replace(",", " ").split()
                    user_parts = user_loc_lower.replace(",", " ").split()
                    if not any(lp in user_parts for lp in loc_parts) and not any(up in loc_parts for up in user_parts):
                        continue
            stats["after_location_filter"] += 1

            # Hard constraint: gender
            if gender and gender not in ("any", ""):
                if user.gender != gender.lower():
                    continue
            stats["after_gender_filter"] += 1

            # Hard constraint: activity/interest
            if activity:
                act_lower = activity.lower()
                has_interest = any(
                    act_lower in interest.lower() or interest.lower() in act_lower
                    for interest in user.interests
                )
                if not has_interest:
                    continue
            stats["after_activity_filter"] += 1

            # Running-specific: level and pace
            if is_running:
                if level and level not in ("any", ""):
                    if not user.running_level or user.running_level != level.lower():
                        continue
                stats["after_level_filter"] += 1

                if pace and pace not in ("any", ""):
                    if not user.running_pace or user.running_pace != pace.lower():
                        continue
                stats["after_pace_filter"] += 1

            pre_slot_candidates.append(user)

        # Phase 2: Analyze time slots to find the best one
        # Goal: Find a slot where enough people are available to meet together
        candidates: list[UserRecord] = []
        selected_slot: str | None = None

        if is_running and availability_slots:
            # Count candidates per slot
            slot_to_users: dict[str, list[UserRecord]] = {slot: [] for slot in availability_slots}
            for user in pre_slot_candidates:
                user_slots = set(user.availability or [])
                for slot in availability_slots:
                    if slot in user_slots:
                        slot_to_users[slot].append(user)

            # Record stats
            stats["candidates_per_slot"] = {slot: len(users) for slot, users in slot_to_users.items()}

            # Choose the best slot: prefer slots with most candidates (but at least headcount)
            # Sort by: 1) has enough candidates, 2) total count descending
            sorted_slots = sorted(
                availability_slots,
                key=lambda s: (len(slot_to_users[s]) >= headcount, len(slot_to_users[s])),
                reverse=True
            )

            # Pick the best slot
            if sorted_slots:
                selected_slot = sorted_slots[0]
                candidates = slot_to_users[selected_slot]
                stats["selected_slot"] = selected_slot
                logger.info(
                    "[match] Selected slot=%s with %d candidates (requested slots=%s)",
                    selected_slot, len(candidates), availability_slots
                )
        else:
            # No slot filtering needed
            candidates = pre_slot_candidates

        stats["final_candidates"] = len(candidates)

        # Phase 3: Score and rank candidates
        results: list[dict[str, Any]] = []
        for user in candidates:
            base_score = random.randint(50, 85)

            # Boost for exact level match
            if is_running and level and user.running_level == level:
                base_score = min(100, base_score + 10)

            # Boost for exact pace match
            if is_running and pace and user.running_pace == pace:
                base_score = min(100, base_score + 5)

            # Boost for having multiple overlapping slots (more flexible)
            if is_running and availability_slots and user.availability:
                overlap = len(set(user.availability).intersection(set(availability_slots)))
                base_score = min(100, base_score + overlap * 3)

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
                "running_level": user.running_level,
                "running_pace": user.running_pace,
                "running_distance": user.running_distance,
                "availability": user.availability,
            })

        # Sort by score descending
        results.sort(key=lambda x: x["match_score"], reverse=True)

        return results[:limit], stats

    def get_user(self, user_id: str) -> UserRecord | None:
        """Get a user by ID."""
        return self._users.get(user_id)

    @property
    def user_count(self) -> int:
        return len(self._users)

    def create_or_update_user(
        self,
        *,
        google_uid: str,
        email: str,
        display_name: str | None = None,
        photo_url: str | None = None,
    ) -> tuple[str, bool]:
        """
        Create or update user from Google login.

        Args:
            google_uid: Google sub (unique identifier)
            email: User email
            display_name: User display name
            photo_url: User avatar URL

        Returns:
            tuple[str, bool]: (user_id, needs_onboarding)
                - user_id: The database user ID (UUID)
                - needs_onboarding: True if user is new or hasn't completed onboarding
        """
        if not self._pg_url:
            # Fallback: add to in-memory store, always needs onboarding
            user_id = google_uid
            is_new = user_id not in self._users
            if is_new:
                self._users[user_id] = UserRecord(
                    id=user_id,
                    email=email,
                    nickname=display_name or email.split('@')[0],
                    gender="",
                    birthday="",
                    location="",
                    occupation="",
                    hobby="",
                    interests=[],
                    archetype=None,
                    is_mock=False,
                )
            return user_id, is_new

        import psycopg2
        import uuid as uuid_mod

        conn = psycopg2.connect(self._pg_url)
        try:
            with conn.cursor() as cur:
                # Check if user exists by email (Google login uses email as identifier)
                cur.execute(
                    """
                    SELECT id, has_completed_questionnaire
                    FROM public.users
                    WHERE email = %s AND is_deleted = false
                    LIMIT 1
                    """,
                    (email,)
                )
                row = cur.fetchone()

                if row:
                    # User exists - update last_active and return
                    user_id = str(row[0])
                    has_completed = row[1] or False
                    cur.execute(
                        """
                        UPDATE public.users
                        SET last_active_at = NOW(), updated_at = NOW(),
                            nickname = COALESCE(NULLIF(%s, ''), nickname),
                            avatar = COALESCE(NULLIF(%s, ''), avatar)
                        WHERE id = %s::uuid
                        """,
                        (display_name or '', photo_url or '', user_id)
                    )
                    conn.commit()

                    # Update in-memory cache
                    if user_id not in self._users:
                        self._users[user_id] = UserRecord(
                            id=user_id,
                            email=email,
                            nickname=display_name or email.split('@')[0],
                            gender="",
                            birthday="",
                            location="",
                            occupation="",
                            hobby="",
                            interests=[],
                            archetype=None,
                            is_mock=False,
                        )

                    return user_id, not has_completed
                else:
                    # New user - create record
                    user_id = str(uuid_mod.uuid4())
                    cur.execute(
                        """
                        INSERT INTO public.users (
                            id, email, auth_provider, nickname, avatar,
                            has_completed_questionnaire, is_active, is_deleted,
                            created_at, updated_at, last_active_at
                        ) VALUES (
                            %s::uuid, %s, 'google', %s, %s,
                            false, true, false,
                            NOW(), NOW(), NOW()
                        )
                        """,
                        (user_id, email, display_name or email.split('@')[0], photo_url or '')
                    )
                    conn.commit()

                    # Also add to in-memory cache
                    self._users[user_id] = UserRecord(
                        id=user_id,
                        email=email,
                        nickname=display_name or email.split('@')[0],
                        gender="",
                        birthday="",
                        location="",
                        occupation="",
                        hobby="",
                        interests=[],
                        archetype=None,
                        is_mock=False,
                    )

                    return user_id, True  # New user needs onboarding
        except Exception as e:
            logger.warning("[db] create_or_update_user failed: %s", e)
            conn.rollback()
            # Fallback to in-memory
            user_id = google_uid
            if user_id not in self._users:
                self._users[user_id] = UserRecord(
                    id=user_id,
                    email=email,
                    nickname=display_name or email.split('@')[0],
                    gender="",
                    birthday="",
                    location="",
                    occupation="",
                    hobby="",
                    interests=[],
                    archetype=None,
                    is_mock=False,
                )
            return user_id, True
        finally:
            conn.close()

    def save_user_profile(
        self,
        *,
        user_id: str,
        name: str,
        gender: str | None = None,
        age: str | None = None,
        city: str | None = None,
        interests: list[str] | None = None,
        running_profile: dict[str, Any] | None = None,
    ) -> bool:
        """
        Save user onboarding profile data.

        Args:
            user_id: User database ID
            name: Display name
            gender: Gender string
            age: Age as string
            city: City/location
            interests: List of interests
            running_profile: Running-specific profile data

        Returns:
            bool: True if save succeeded
        """
        from datetime import date

        # Update in-memory cache
        if user_id in self._users:
            user = self._users[user_id]
            user.nickname = name
            user.gender = (gender or "").lower()
            user.location = city or ""
            user.interests = interests or []
            if running_profile:
                level = running_profile.get('level', {})
                user.running_level = level.get('experience')
                user.running_pace = level.get('paceRange')
                user.running_distance = level.get('typicalDistance')
                avail = running_profile.get('availability', {})
                user.availability = [
                    k.replace('weekday', 'weekday_').replace('weekend', 'weekend_').lower()
                    for k, v in avail.items() if v
                ]

        if not self._pg_url:
            return True  # In-memory only

        import psycopg2

        conn = psycopg2.connect(self._pg_url)
        try:
            with conn.cursor() as cur:
                # Calculate birthday from age
                birthday_str = None
                if age and age.isdigit():
                    birth_year = date.today().year - int(age)
                    birthday_str = f"{birth_year}-01-01"

                # Build profile JSON for user_ai_profiles
                profile_json = {
                    "name": name,
                    "interests": interests or [],
                    "hobbies": interests or [],
                }
                if running_profile:
                    profile_json["running"] = running_profile

                # Update users table
                cur.execute(
                    """
                    UPDATE public.users SET
                        nickname = %s,
                        gender = NULLIF(%s, ''),
                        birthday = NULLIF(%s, '')::date,
                        location = NULLIF(%s, ''),
                        hobby = %s,
                        has_completed_questionnaire = true,
                        questionnaire_completed_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (
                        name,
                        (gender or "").lower(),
                        birthday_str,
                        city or "",
                        ", ".join(interests[:3]) if interests else "",
                        user_id,
                    )
                )

                # Upsert user_ai_profiles
                profile_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO public.user_ai_profiles (id, user_id, profile, version, created_at, updated_at)
                    VALUES (%s::uuid, %s::uuid, %s::jsonb, 1, NOW(), NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        profile = EXCLUDED.profile,
                        updated_at = NOW(),
                        version = public.user_ai_profiles.version + 1
                    """,
                    (profile_id, user_id, json.dumps(profile_json))
                )

                conn.commit()
                return True
        except Exception as e:
            logger.warning("[db] save_user_profile failed: %s", e)
            conn.rollback()
            return False
        finally:
            conn.close()


# Global singleton
user_db = UserDB()
