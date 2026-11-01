import re


def normalize(text):
    return (
        text.lower()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("–", "-")
    )


def matches(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)


HAZARDS = [
    r"\bgas\s+(?:leak|leaking)\b",
    r"\b(?:smell|odor|odour|smelling)\b.{0,40}\bgas\b",
    r"\bgas\b.{0,40}\b(?:smell|odor|leak)\b",
    r"\bcarbon monoxide\b.{0,60}\b(?:alarm|detector|leak|detected)\b",
    r"\b(?:alarm|detector)\b.{0,60}\bcarbon monoxide\b",
    r"\b(?:fire|smoke)\s+alarm\b.{0,50}\b(?:broken|disabled|not working|failed)\b",
    r"\b(?:broken|disabled|not working|failed)\b.{0,50}\b(?:fire|smoke)\s+alarm\b",
    r"\b(?:sparks?|sparking|exposed wiring|live wire)\b",
    r"\b(?:water|leak|leaking|dripping)\b.{0,65}\b(?:outlet|socket|electrical panel)\b",
    r"\b(?:outlet|socket|electrical panel)\b.{0,65}\b(?:water|leak|leaking|dripping)\b",
    r"\b(?:security door|security gate|entrance lock|front door lock)\b.{0,55}\b(?:broken|unlocked|stuck open|doesn't lock|open all night)\b",
    r"\b(?:broken|unlocked)\b.{0,55}\b(?:security door|security gate|entrance lock|front door lock)\b",

    r"\b(?:entrance|security|front|building|apartment|door)\s+(?:security\s+)?(?:door\s+)?lock\b.{0,55}\b(?:broken|unlocked|damaged|stuck open|doesn't lock|does not lock|not locking|won't lock)\b",
    r"\b(?:broken|unlocked|damaged)\b.{0,40}\b(?:entrance|security|front|building|apartment|door)\s+(?:security\s+)?(?:door\s+)?lock\b",

    r"\b(?:emergency exit|fire exit)\b.{0,45}\b(?:blocked|locked|broken)\b",
    r"\b(?:blocked|locked|broken)\b.{0,45}\b(?:emergency exit|fire exit)\b",
    r"\b(?:heat|heating)\s+(?:is\s+)?(?:out|broken|not working)\b",
    r"\b(?:no|without|lost)\s+(?:running\s+)?(?:water|heat|heating|hot water)\b",
    r"\b(?:freezing|very cold)\b.{0,65}\b(?:heat|heating)\b",
    r"\b(?:flooding|sewage backup|black mold|toxic mold)\b",
    r"\b(?:threatened|assaulted|attacked|stalking|break-in|burglary)\b",
    r"\b(?:smell|smelling)\b.{0,35}\b(?:burning|smoke)\b",
    r"\b(?:burning smell|smoke in the hallway|actual fire)\b",

    r"\b(?:emergency stairwell|stairwell exit|emergency stairwell exit)\b.{0,65}\b(?:blocked|locked|obstructed|inaccessible)\b",
    r"\b(?:blocked|locked|obstructed|inaccessible)\b.{0,65}\b(?:emergency stairwell|stairwell exit|emergency stairwell exit)\b",
    r"\b(?:furniture|boxes|objects|items)\b.{0,40}\b(?:blocking|obstructing)\b.{0,45}\b(?:stairwell|emergency exit|fire exit)\b",
    r"\b(?:stairwell|emergency exit|fire exit)\b.{0,45}\b(?:blocked by|obstructed by)\b",

]

ACCESSIBILITY_AND_HARASSMENT = [
    r"\b(?:harassed|harassing|harassment|discrimination|discriminated)\b",
    r"\b(?:wheelchair|mobility scooter|mobility device|walker)\b.{0,110}\b(?:broken|blocked|inaccessible|cannot|can't|out of service|not working)\b",
    r"\b(?:broken|blocked|inaccessible|cannot|can't|out of service|not working)\b.{0,110}\b(?:wheelchair|mobility scooter|mobility device|walker)\b",
    r"\b(?:cannot|can't|unable to)\s+access\b.{0,85}\b(?:laundry|elevator|ramp|entrance|building)\b",
]

# Remove known harmless or explicitly negated phrases before hazard matching.
HARMLESS_PHRASES = [
    r"\bsmoke[- ]free\b",
    r"\bfire\s+(?:pit|place|drill)\b",
    r"\b(?:no|not|never)\s+(?:smoke|fire|gas leak|gas smell|smell of gas)\b",
    r"\b(?:smoke|fire|gas smell)\s+(?:is|was)\s+(?:gone|resolved)\b",
]

POSITIVE = [
    r"\b(?:love|excellent|wonderful|amazing|fantastic|great|perfect)\b",
    r"\b(?:clean|quiet|friendly|helpful|responsive|comfortable)\b",
    r"\b(?:very happy|highly recommend|fixed quickly|works perfectly)\b",
]

NEGATIVE = [
    r"\b(?:hate|terrible|awful|horrible|disappointing|unacceptable)\b",
    r"\b(?:broken|dirty|filthy|noisy|loud|rude|unsafe)\b",
    r"\b(?:doesn't work|does not work|never replies|never answers)\b",
    r"\b(?:ignored|dismissed|not fixed|still broken|failed again)\b",
]

VAGUE = {"fine", "ok", "okay", "meh", "hmm", "whatever", "idk", "not sure"}


def simple_tone(comment):
    text = normalize(comment)

    # Avoid treating sarcastic "Great, another..." as clear praise.
    if re.search(
        r"\b(?:great|wonderful|fantastic|perfect),?\s+"
        r"(?:another|the)\b.{0,90}"
        r"\b(?:broken|failed|without|no |again|out)\b",
        text
    ):
        return "unknown"

    text = re.sub(
        r"\b(?:not|isn't|wasn't|aren't|weren't)\s+"
        r"(?:very\s+)?(?:clean|quiet|friendly|helpful|great|perfect)\b",
        "negative_description",
        text
    )

    positive = matches(text, POSITIVE)
    negative = (
        matches(text, NEGATIVE)
        or "negative_description" in text
    )

    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    return "unknown"


def review_reasons(comment, rating, label, error=None):
    if not isinstance(comment, str) or not comment.strip():
        return []

    text = normalize(comment.strip())
    reasons = []

    if error or label is None:
        reasons.append("Classification failed or invalid")

    simplified = re.sub(r"[^a-z0-9 ]", "", text).strip()
    if simplified in VAGUE:
        reasons.append("Vague feedback")

    hazard_text = text
    for pattern in HARMLESS_PHRASES:
        hazard_text = re.sub(pattern, " ", hazard_text, flags=re.I)

    if matches(hazard_text, HAZARDS):
        reasons.append("Potential safety or living-condition hazard")

    if matches(text, ACCESSIBILITY_AND_HARASSMENT):
        reasons.append("Potential harassment or accessibility concern")

    if rating is not None:
        tone = simple_tone(comment)

        if tone == "positive" and rating <= 2:
            reasons.append("Positive wording conflicts with low rating")
        elif tone == "negative" and rating == 5:
            reasons.append("Negative wording conflicts with high rating")

    return reasons
