"""
Roleplay Chat Service
AI performs "method acting" to roleplay as a generated character
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from .llm import call_gemini_json

logger = logging.getLogger(__name__)


ROLEPLAY_SYSTEM_PROMPT = """
You are an AI performing "method acting" to roleplay as a specific person in a chat conversation.
You must stay in character at all times. Respond naturally as this person would.

**Character Profile:**
{character_profile}

**1. DYNAMIC PERSONA ANALYSIS (Step-by-Step):**
- **Step 1: Identify Your Character:** Read the character's `name`, `headline`, and `about`.
    - Infer and adopt their specific voice from these fields (e.g., if they seem "Anxious", use hedging words; if "Bold", be direct).
    - Your Location: Use ONLY the `city` field provided.
- **Step 2: Understand Your Interests:** Read `topics` for subjects you enjoy discussing.
- **Step 3: Context Awareness:** Use `matchReasons`, `healingReasons` (if present), and `aiNote` (if present) to understand the relationship context.

**2. STRICT DATA RULES (No Hallucinations):**
- **Locations:** Do NOT invent cities. Use the exact `city` provided in the profile.
- **Interests:** Only reference topics from `topics` or facts from `about`.
- **Assumptions:** Do not assume activities or preferences unless explicitly stated in the profile. If not stated, frame it as a question or uncertainty.

**3. CONTENT GENERATION RULES:**
- **Voice:** Casual, lowercase (unless the character seems formal), natural phrasing.
- **Stay in character:** Never break character. Never mention you are an AI.
- **Be conversational:** Respond naturally, keep responses concise and engaging.

**Conversation History:**
{conversation_history}

**Task:**
Respond to the user's latest message as this character. Return ONLY valid JSON:
{{"reply": "Your response as the character"}}
"""


class RoleplayResponse(BaseModel):
    reply: str


def roleplay_chat(profile: dict[str, Any], messages: list[dict[str, str]]) -> str:
    """
    Generate a roleplay response based on the character profile and conversation history.

    Args:
        profile: The character profile dict (name, city, headline, about, topics, etc.)
        messages: List of messages with 'role' ('user' or 'assistant') and 'content'

    Returns:
        The AI's response as the character
    """
    # Format conversation history
    history_lines = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            history_lines.append(f"User: {content}")
        else:
            history_lines.append(f"Character: {content}")

    conversation_history = "\n".join(history_lines) if history_lines else "(No previous messages)"

    # Build the prompt
    prompt = ROLEPLAY_SYSTEM_PROMPT.format(
        character_profile=json.dumps(profile, ensure_ascii=False, indent=2),
        conversation_history=conversation_history,
    )

    try:
        response = call_gemini_json(
            prompt=prompt,
            response_model=RoleplayResponse,
        )
        return response.reply
    except Exception as e:
        logger.error("[roleplay] LLM call failed: %s", e)
        # Fallback response
        name = profile.get("name", "I")
        return f"Hey! Sorry, {name} is having trouble connecting right now. Let's try again?"
