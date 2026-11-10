import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyResult:
    status: str
    reply: str
    category: str


EMERGENCY_PATTERNS = {
    "CHEST_PAIN": [
        r"\bchest pain\b",
        r"\bchest pressure\b",
        r"\bchest tightness\b",
        r"\bcrushing chest\b",
        r"\bheart attack\b",
    ],
    "BREATHING": [
        r"\b(can'?t|cannot|unable to)\s+breathe\b",
        r"\b(difficulty|trouble)\s+breathing\b",
        r"\bsevere shortness of breath\b",
        r"\bstruggling to breathe\b",
        r"\bnot breathing\b",
    ],
    "STROKE": [
        r"\bstroke\b",
        r"\bface droop",
        r"\bslurred speech\b",
        r"\bsudden weakness\b",
        r"\bsuddenly (can'?t|cannot) speak\b",
        r"\bsuddenly unable to speak\b",
        r"\bsudden loss of vision\b",
    ],
    "BLEEDING": [
        r"\b(heavy|severe|uncontrolled) bleeding\b",
        r"\bbleeding (heavily|profusely)\b",
        r"\bbleeding (won'?t|will not) stop\b",
    ],
    "UNCONSCIOUS": [
        r"\bunconscious\b",
        r"\bnot waking up\b",
        r"\bwon'?t wake up\b",
        r"\bpassed out\b",
        r"\bunresponsive\b",
    ],
    "ALLERGIC_REACTION": [
        r"\banaphylaxis\b",
        r"\bthroat (is )?closing\b",
        r"\bsevere allergic reaction\b",
        r"\bswollen tongue\b",
    ],
    "SELF_HARM": [
        r"\bwant to kill myself\b",
        r"\bgoing to kill myself\b",
        r"\bwant to end my life\b",
        r"\bplanning to end my life\b",
        r"\babout to hurt myself\b",
    ],
}


HISTORICAL_PATTERNS = [
    r"\blast year\b",
    r"\byears ago\b",
    r"\blast month\b",
    r"\bpreviously\b",
    r"\bin the past\b",
    r"\bused to have\b",
]

EDUCATIONAL_PATTERNS = [
    r"\bwhat is\b",
    r"\bwhat are\b",
    r"\bexplain\b",
    r"\bdefinition of\b",
    r"\bwhat does\b",
    r"\bmeaning of\b",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in patterns
    )


def screen_emergency(message: str) -> SafetyResult | None:
    text = " ".join(message.lower().split())

    if not text:
        return None

    matched_categories = [
        category
        for category, patterns in EMERGENCY_PATTERNS.items()
        if _matches_any(text, patterns)
    ]

    if not matched_categories:
        return None

    # These exceptions are intentionally narrow.
    # Ambiguous symptom reports still receive conservative guidance.
    if (
        _matches_any(text, EDUCATIONAL_PATTERNS)
        and not _matches_any(
            text,
            [
                r"\bi have\b",
                r"\bi am having\b",
                r"\bmy (father|mother|child|friend|wife|husband)\b",
                r"\bsomeone is\b",
                r"\bright now\b",
                r"\bcurrently\b",
                r"\bnot able to\s+breath(?:e)?\b",
                r"\bunable to\s+breath(?:e)?\b",
                r"\b(can'?t|cannot)\s+breath(?:e)?\b",
                r"\bshortness of breath\b",
                r"\bbreathing problem\b",
                r"\bstruggling for breath\b",
            ],
        )
    ):
        return None

    if (
        _matches_any(text, HISTORICAL_PATTERNS)
        and not _matches_any(
            text,
            [
                r"\bnow\b",
                r"\btoday\b",
                r"\bcurrently\b",
                r"\bagain\b",
            ],
        )
    ):
        return None

    if "SELF_HARM" in matched_categories:
        return SafetyResult(
            status="POTENTIAL_EMERGENCY",
            category="SELF_HARM",
            reply=(
                "Your safety is the priority. "
                "If you might act on thoughts of harming yourself, "
                "contact local emergency services immediately "
                "or go to the nearest emergency department. "
                "If possible, stay with someone you trust and "
                "move away from anything you could use to harm yourself. "
                "Please do not wait for a routine appointment."
            ),
        )

    return SafetyResult(
        status="POTENTIAL_EMERGENCY",
        category=matched_categories[0],
        reply=(
            "Your message describes symptoms that may require "
            "immediate medical attention.\n\n"
            "**Please contact your local emergency services now "
            "or seek immediate emergency medical care.**\n\n"
            "Do not wait for a routine appointment or rely on "
            "this assistant for diagnosis or emergency treatment.\n\n"
            "If someone is nearby, ask them to help you contact "
            "emergency services."
        ),
    )