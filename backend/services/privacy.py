"""Small privacy helpers used at API and model boundaries."""

import re


NRIC_PATTERN = re.compile(r"\b([STFGM])\d{7}([A-Z])\b", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
ISO_DATE_PATTERN = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
SLASH_DATE_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/(?:19|20)?\d{2}\b")
TEXT_DATE_PATTERN = re.compile(
    r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)


def mask_nric(value):
    if not value:
        return None
    cleaned = value.strip().upper()
    if len(cleaned) < 2:
        return "*" * len(cleaned)
    return f"{cleaned[0]}{'*' * (len(cleaned) - 2)}{cleaned[-1]}"


def mask_nrics_in_text(value):
    if not value:
        return value
    return NRIC_PATTERN.sub(lambda match: mask_nric(match.group(0)), value)


def redact_for_classification(value):
    """Remove contact/identity values that classification does not need."""
    redacted = mask_nrics_in_text(value or "")
    redacted = EMAIL_PATTERN.sub("[EMAIL REDACTED]", redacted)
    redacted = ISO_DATE_PATTERN.sub("[DATE REDACTED]", redacted)
    redacted = SLASH_DATE_PATTERN.sub("[DATE REDACTED]", redacted)
    return TEXT_DATE_PATTERN.sub("[DATE REDACTED]", redacted)
