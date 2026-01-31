from __future__ import annotations

from typing import Literal

from .llm import call_gemini_json
from .models import (
    SortingAnswers,
    SortingLabelsResponse,
    SortingNutritionFactLine,
    SortingNutritionFacts,
    SortingTroubleshootingItem,
    SortingUserManual,
    SortingWarningLabel,
)

Archetype = Literal["Explorer", "Builder", "Artist", "Guardian"]


def _clamp_0_3(n: int) -> int:
    return max(0, min(3, int(n)))


def score_sorting(answers: SortingAnswers) -> tuple[int, int]:
    novelty = int(answers.restaurant == "B") + int(answers.travel == "B") + int(answers.birthday == "B")
    security = int(answers.weather in ("A", "B")) + int(answers.noResponse in ("A", "D")) + int(answers.awkwardWave == "B")
    return _clamp_0_3(novelty), _clamp_0_3(security)


def classify_archetype(novelty_score: int, security_score: int) -> Archetype:
    novelty_high = novelty_score >= 2
    security_high = security_score >= 2
    if novelty_high and security_high:
        return "Explorer"
    if (not novelty_high) and security_high:
        return "Builder"
    if novelty_high and (not security_high):
        return "Artist"
    return "Guardian"


def _fallback_warning_label(archetype: Archetype, novelty: int, security: int, answers: SortingAnswers) -> SortingWarningLabel:
    n = _clamp_0_3(novelty)
    s = _clamp_0_3(security)

    security_flavor = (
        "Emotionally waterproof (still has feelings, just carries an umbrella)."
        if s == 3
        else "Generally steady; occasional wobble is purely for plot."
        if s == 2
        else "Reads between the lines… then reads between those lines too."
        if s == 1
        else "May interpret “…” as a full documentary series."
    )
    novelty_flavor = (
        "Will say “we should” and then immediately open a map."
        if n == 3
        else "Enjoys a little chaos, as a treat."
        if n == 2
        else "Likes novelty in small, pre-approved doses."
        if n == 1
        else "If it ain’t broke, don’t “fun” it."
    )

    if archetype == "Explorer":
        warnings = [
            "Can turn “quick coffee” into a 6-hour side quest.",
            "Will befriend strangers, bartenders, and at least one dog.",
            "Says “yes” fast; reads details later.",
            "If you don’t reply fast, this unit may refresh notifications like it’s cardio."
            if answers.noResponse == "C"
            else "Will assume good intent first (then keep moving).",
            novelty_flavor,
            security_flavor,
        ]
        return SortingWarningLabel(
            warnings=warnings,
            bestConsumed=["small groups", "spontaneous plans", "new neighborhoods", "friends who can walk a lot"],
            doNot=["trap in the same spot every Friday", "schedule “fun” in 15-minute blocks"],
        )

    if archetype == "Builder":
        warnings = [
            "Requires calendar invite (bonus points for location + time).",
            "Friendship is built brick-by-brick; no speedruns.",
            "“Maybe” means “let me check my routine and my emotional bandwidth.”",
            "Stores awkward moments in the cloud for later replay." if answers.awkwardWave == "A" else "Recovers from awkwardness quickly (patch deployed).",
            novelty_flavor,
            security_flavor,
        ]
        return SortingWarningLabel(
            warnings=warnings,
            bestConsumed=["weekly rituals", "1-on-1 catchups", "low-drama group chats", "plans made before 9pm"],
            doNot=["surprise 2am adventures", "change the plan mid-plan"],
        )

    if archetype == "Artist":
        warnings = [
            "Feelings arrive in HD with surround sound.",
            "Can go from strangers → soulmates in 12 minutes.",
            "May overthink your “k” for 48 hours (with footnotes).",
            "May run a full post-text “did I sound weird?” audit." if answers.noResponse == "B" else "Reads tone like a detective (sometimes too well).",
            novelty_flavor,
            security_flavor,
        ]
        return SortingWarningLabel(
            warnings=warnings,
            bestConsumed=["creative hangouts", "deep talks", "low-pressure adventures", "friends who text back like humans"],
            doNot=["leave on read with zero context", "force loud group icebreakers"],
        )

    warnings = [
        "Arrives as an observer; leaves as ride-or-die (eventually).",
        "Trust is earned slowly; once in, you’re family.",
        "May rehearse conversations in the shower.",
        "Prefers a clear plan (and will secretly love you for making one)." if answers.travel == "A" else "Will follow the vibe—just don’t call it “random”.",
        novelty_flavor,
        security_flavor,
    ]
    return SortingWarningLabel(
        warnings=warnings,
        bestConsumed=["familiar settings", "predictable plans", "small circles", "gentle introductions"],
        doNot=["spring last-minute plan changes", "weaponize “just be spontaneous”"],
    )


def _fallback_nutrition_facts(archetype: Archetype, novelty: int, security: int, answers: SortingAnswers) -> SortingNutritionFacts:
    n = _clamp_0_3(novelty)
    s = _clamp_0_3(security)

    advance_notice = max(4, min(96, 8 + (3 - n) * 18 + (2 - s) * 6))
    deep = max(10, min(100, 60 + n * 8 + (2 - s) * 10))
    spont = max(0, min(100, 10 + n * 25 + (10 if s >= 2 else 0)))
    smalltalk = max(0, min(100, 70 - deep + (8 if s >= 2 else 0)))

    drain_index = (3 - s) * 1.1 + (3 - n) * 0.6
    drain = "HIGH" if drain_index >= 3.2 else "MED" if drain_index >= 2 else "LOW"
    recovery = max(4, min(72, 6 + (3 - s) * 14 + (3 - n) * 6))

    ingredients = []
    if answers.travel == "B":
        ingredients.append("detours")
    if answers.restaurant == "A":
        ingredients.append("comfort choices")
    if answers.noResponse == "B":
        ingredients.append("text re-reading")
    if answers.noResponse == "C":
        ingredients.append("notification refresh")
    if answers.awkwardWave == "A":
        ingredients.append("post-event replay")
    if not ingredients:
        ingredients.append("good intentions")

    contains = []
    if s <= 1:
        contains.append("overthinking")
    if n >= 2:
        contains.append("curiosity")
    if answers.noResponse == "D":
        contains.append("healthy boundaries")
    if not contains:
        contains.append("quiet confidence")

    may = {
        "Explorer": "impromptu group selfies",
        "Builder": "spreadsheets (lovingly)",
        "Artist": "unexpected depth",
        "Guardian": "ride-or-die loyalty",
    }[archetype]

    servings = {
        "Explorer": "3–5 (if the vibes are right)",
        "Artist": "2–3 (plus a lot of thinking)",
        "Builder": "1–2 (scheduled)",
        "Guardian": "1–2 (trusted circle only)",
    }[archetype]

    return SortingNutritionFacts(
        servingSize="1 hangout",
        servingsPerWeek=servings,
        amountPerServing=[
            SortingNutritionFactLine(label="Advance Notice Required", value=f"{advance_notice} hrs"),
            SortingNutritionFactLine(label="Deep Conversation", value=f"{deep}%"),
            SortingNutritionFactLine(label="Small Talk Tolerance", value=f"{smalltalk}%"),
            SortingNutritionFactLine(label="Spontaneity", value=f"{spont}%"),
        ],
        energyDrainPerHour=drain,
        recoveryTimeNeeded=f"{recovery} hrs",
        ingredients=", ".join(ingredients),
        contains=", ".join(contains),
        mayContain=may,
    )


def _fallback_user_manual(archetype: Archetype, novelty: int, security: int, answers: SortingAnswers) -> SortingUserManual:
    s = _clamp_0_3(security)
    n = _clamp_0_3(novelty)

    model_name = {
        "Explorer": "Side-Quest Navigator 3000",
        "Builder": "Calendar-First Companion 2.0",
        "Artist": "Feelings-in-HD Edition",
        "Guardian": "Loyalty Sentinel (Quiet Mode)",
    }[archetype]

    if archetype == "Explorer":
        quick = [
            "Offer a plan with 2 choices (adventure + fallback).",
            "Be ready to pivot when a cool side quest appears.",
            "Let them talk to strangers; it’s part of the operating system.",
            "Hydrate. This unit forgets time exists.",
        ]
    elif archetype == "Builder":
        quick = [
            "Send a calendar invite with time + location.",
            "Confirm the plan once (not seven times).",
            "Start with something familiar; earn novelty slowly.",
            "Respect the “wrap by X pm” boundary (it’s real).",
        ]
    elif archetype == "Artist":
        quick = [
            "Use full sentences. Warm tone. No “k”.",
            "Pick a vibe-forward place (lighting matters).",
            "Suggest 1–2 real topics (not small-talk trivia).",
            "If they go quiet, assume processing—not disinterest.",
        ]
    else:
        quick = [
            "Start with a gentle invite (details included).",
            "Introduce new people slowly, like adding spice to soup.",
            "Follow through on what you say (trust is the fuel).",
            "Don’t force spontaneity; offer options instead.",
        ]

    group_size = "2–6 people" if archetype == "Explorer" else "1–3 people" if archetype == "Artist" else "1–4 people"
    duration = "2–5 hours" if archetype == "Explorer" else "1.5–3 hours" if archetype == "Builder" else "2–3 hours"
    env = (
        "new spots, walkable neighborhoods"
        if archetype == "Explorer"
        else "cozy cafés, low-noise corners"
        if archetype == "Artist"
        else "known venues, clear plans"
        if archetype == "Builder"
        else "familiar places, low-pressure settings"
    )

    troubleshooting = [
        SortingTroubleshootingItem(
            issue="No reply for a few hours",
            fix="Do nothing. This unit is already calm about it."
            if answers.noResponse == "A"
            else "Do nothing. Let them respond on their timeline."
            if answers.noResponse == "D"
            else "Add context (“no rush”) and step away from the refresh button.",
        ),
        SortingTroubleshootingItem(
            issue="Awkward moment happened",
            fix="Laugh, move on, never mention it again."
            if answers.awkwardWave == "B"
            else "Name it lightly, then change topic. Do not replay in 4K.",
        ),
        SortingTroubleshootingItem(
            issue="Plan feels too random",
            fix="Keep the chaos, but add one anchor (time OR place)." if n >= 2 else "Add structure: time, place, and a clear end time.",
        ),
    ]

    warranty = (
        "Warranty: loyalty backed by a surprisingly long memory."
        if archetype == "Guardian"
        else "Warranty: consistent friendship, limited-time drama support."
        if archetype == "Builder"
        else "Warranty: emotional depth included. Handle with care."
        if archetype == "Artist"
        else "Warranty: good stories guaranteed; receipts may be lost."
    )

    return SortingUserManual(
        modelName=model_name,
        quickStart=quick,
        optimalOperatingConditions=[
            f"Group size: {group_size}",
            f"Duration: {duration}",
            f"Environment: {env}",
            f"Vibe: {'steady + easy' if s >= 2 else 'gentle + reassuring'} (no pressure)",
        ],
        troubleshooting=troubleshooting,
        warranty=warranty,
    )


def _fallback_pack(answers: SortingAnswers) -> SortingLabelsResponse:
    novelty, security = score_sorting(answers)
    archetype = classify_archetype(novelty, security)
    return SortingLabelsResponse(
        noveltyScore=novelty,
        securityScore=security,
        archetype=archetype,
        warningLabel=_fallback_warning_label(archetype, novelty, security, answers),
        nutritionFacts=_fallback_nutrition_facts(archetype, novelty, security, answers),
        userManual=_fallback_user_manual(archetype, novelty, security, answers),
    )


class _LLMArtifacts(SortingLabelsResponse):
    """Used only for Gemini parsing (same schema as response)."""


def build_sorting_labels_prompt(*, name: str | None, answers: SortingAnswers, novelty: int, security: int, archetype: Archetype) -> str:
    # Keep the prompt short + constrained so output stays structured.
    # NOTE: Avoid the word "type" entirely in the generated copy (requested).
    notes = []
    if answers.noResponse == "B":
        notes.append("When someone doesn't reply, they re-read their message and self-audit.")
    if answers.noResponse == "C":
        notes.append("When someone doesn't reply, they check their phone more often.")
    if answers.awkwardWave == "A":
        notes.append("If an awkward moment happens, they may replay it for hours.")
    if answers.awkwardWave == "B":
        notes.append("If an awkward moment happens, they laugh and forget.")
    if answers.travel == "A":
        notes.append("Travel style: guided tour, prefers structure.")
    if answers.travel == "B":
        notes.append("Travel style: wander and discover.")

    name_line = f"User name (optional): {name}\n" if name else ""
    notes_block = "\n".join(f"- {n}" for n in notes) if notes else "- (no extra notes)"

    return (
        "You generate a playful, accurate 'social label pack' for a person.\n"
        "It must be lively, funny, and brutally specific (without being mean).\n"
        "\n"
        "Hard rules:\n"
        "- Output ONLY a single JSON object matching the provided schema.\n"
        "- Keep it short and punchy.\n"
        "- Do NOT use the word \"type\" anywhere.\n"
        "- Do NOT mention diagnoses, disorders, or mental health labels.\n"
        "- No slurs, no harassment, no profanity.\n"
        "- English only.\n"
        "\n"
        "Given scores:\n"
        f"- noveltyScore: {novelty} (0–3)\n"
        f"- securityScore: {security} (0–3)\n"
        f"- archetype: {archetype}\n"
        + name_line +
        "\n"
        "Extra behavioral notes:\n"
        f"{notes_block}\n"
        "\n"
        "Schema you MUST match:\n"
        "{\n"
        '  "noveltyScore": 0-3,\n'
        '  "securityScore": 0-3,\n'
        '  "archetype": "Explorer"|"Builder"|"Artist"|"Guardian",\n'
        '  "warningLabel": { "warnings": [..], "bestConsumed": [..], "doNot": [..] },\n'
        '  "nutritionFacts": {\n'
        '    "servingSize": "...",\n'
        '    "servingsPerWeek": "...",\n'
        '    "amountPerServing": [{"label":"...","value":"..."}],\n'
        '    "energyDrainPerHour": "LOW"|"MED"|"HIGH",\n'
        '    "recoveryTimeNeeded": "...",\n'
        '    "ingredients": "...",\n'
        '    "contains": "...",\n'
        '    "mayContain": "..."\n'
        "  },\n"
        '  "userManual": {\n'
        '    "modelName": "...",\n'
        '    "quickStart": ["...", "...", "..."],\n'
        '    "optimalOperatingConditions": ["...", "...", "..."],\n'
        '    "troubleshooting": [{"issue":"...","fix":"..."}],\n'
        '    "warranty": "..."\n'
        "  }\n"
        "}\n"
        "\n"
        "Make it feel like the screenshots: warning label / nutrition facts / user manual.\n"
        "Make sure every bullet/line is human-funny but also true-to-score.\n"
    )


def generate_sorting_labels(*, name: str | None, answers: SortingAnswers) -> SortingLabelsResponse:
    novelty, security = score_sorting(answers)
    archetype = classify_archetype(novelty, security)

    # If Gemini fails (missing creds / transient), return deterministic fallback.
    try:
        prompt = build_sorting_labels_prompt(name=name, answers=answers, novelty=novelty, security=security, archetype=archetype)
        llm = call_gemini_json(prompt=prompt, response_model=_LLMArtifacts)
        # Ensure scores/archetype are consistent even if model drifts.
        return SortingLabelsResponse(
            noveltyScore=novelty,
            securityScore=security,
            archetype=archetype,
            warningLabel=llm.warningLabel,
            nutritionFacts=llm.nutritionFacts,
            userManual=llm.userManual,
        )
    except Exception:
        return _fallback_pack(answers)

