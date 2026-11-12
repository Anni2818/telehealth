"""Optional Azure OpenAI semantic emergency screening."""

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ALLOWED_STATUSES = {"NORMAL", "POTENTIAL_EMERGENCY", "UNCERTAIN"}
ALLOWED_CATEGORIES = {
    "CHEST_PAIN", "BREATHING", "STROKE", "BLEEDING",
    "UNCONSCIOUS", "ALLERGIC_REACTION", "SELF_HARM",
    "OTHER", "NONE",
}


@dataclass(frozen=True)
class SemanticSafetyResult:
    status: str
    category: str
    reply: str


def _enabled():
    return os.getenv(
        "SEMANTIC_EMERGENCY_SCREENING_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}


def _safe_reply(status, category):
    if category == "SELF_HARM":
        return (
            "Your safety is the priority. If you might act on thoughts "
            "of harming yourself, contact local emergency services now "
            "or go to the nearest emergency department. If possible, "
            "stay with someone you trust and move away from anything "
            "you could use to hurt yourself. Do not wait for a routine appointment."
        )

    if status == "UNCERTAIN":
        return (
            "I couldn't safely determine whether your message describes "
            "an emergency. If you or someone else may be experiencing "
            "severe, sudden, or worsening symptoms, contact local emergency "
            "services or seek urgent medical care now. Do not wait for "
            "this chat to assess an emergency."
        )

    return (
        "Your message may describe symptoms that need immediate medical "
        "attention. Contact local emergency services now or seek immediate "
        "emergency care. Do not wait for a routine appointment or rely on "
        "this assistant for diagnosis or emergency treatment. If someone "
        "is nearby, ask them to help."
    )


def _uncertain():
    return SemanticSafetyResult(
        status="UNCERTAIN",
        category="OTHER",
        reply=_safe_reply("UNCERTAIN", "OTHER"),
    )


def _build_client():
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()

    if not endpoint or not api_key:
        raise RuntimeError("Azure OpenAI endpoint or API key is missing.")

    from openai import AzureOpenAI

    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-10-21"
        ),
        timeout=float(
            os.getenv("SEMANTIC_SCREENING_TIMEOUT_SECONDS", "12")
        ),
        max_retries=0,
    )


def screen_semantic_emergency(message):
    """Return None when disabled; otherwise classify conservatively."""
    if not _enabled():
        return None

    deployment = os.getenv(
        "AZURE_OPENAI_EMERGENCY_DEPLOYMENT", ""
    ).strip()

    if not deployment:
        logger.error("Semantic screening enabled but deployment is missing.")
        return _uncertain()

    try:
        client = _build_client()

        try:
            response = client.chat.completions.create(
                model=deployment,
                temperature=0,
                max_tokens=160,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a conservative emergency-symptom safety "
                            "classifier, not a diagnostic system. Classify the "
                            "user's current message. Detect direct and indirect "
                            "descriptions of possible acute emergencies, including "
                            "chest discomfort, breathing difficulty, stroke signs, "
                            "severe bleeding, unconsciousness, severe allergic "
                            "reaction, and imminent self-harm. Understand plain "
                            "language even without medical terminology. Do not "
                            "treat clearly educational, fictional, or historical "
                            "discussion as a current event. If ambiguous, choose "
                            "UNCERTAIN, not NORMAL. Return ONLY JSON with keys "
                            "status and category. status must be NORMAL, "
                            "POTENTIAL_EMERGENCY, or UNCERTAIN. category must be "
                            "CHEST_PAIN, BREATHING, STROKE, BLEEDING, UNCONSCIOUS, "
                            "ALLERGIC_REACTION, SELF_HARM, OTHER, or NONE."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
            )
            content = response.choices[0].message.content
        finally:
            client.close()

        data = json.loads(content or "")

        if not isinstance(data, dict):
            return _uncertain()

        status = data.get("status")
        category = data.get("category")

        if status not in ALLOWED_STATUSES or category not in ALLOWED_CATEGORIES:
            return _uncertain()

        # Reject contradictory structured output rather than allowing a
        # category/status mismatch to silently pass the safety gate.
        if (
            (status == "NORMAL" and category != "NONE")
            or (status == "POTENTIAL_EMERGENCY" and category == "NONE")
        ):
            return _uncertain()

        if status == "NORMAL":
            return SemanticSafetyResult("NORMAL", "NONE", "")

        return SemanticSafetyResult(
            status=status,
            category=category,
            reply=_safe_reply(status, category),
        )

    except Exception:
        logger.exception(
            "Semantic emergency screening failed; stopping chat flow."
        )
        return _uncertain()
