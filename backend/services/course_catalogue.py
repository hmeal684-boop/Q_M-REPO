"""Provider for company-supplied course and enrollment information."""

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


CATALOGUE_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "course_information.json"
)

MONEY_PATTERN = re.compile(r"(?:S\$|\$)\s*([0-9][0-9,]*(?:\.\d{1,2})?)", re.I)
UEN_PATTERN = re.compile(r"\b\d{9}[A-Z]\b", re.I)
CALENDAR_DATE_PATTERN = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}(?:st|nd|rd|th)?\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{4}|(?:January|February|March|April|May|June|"
    r"July|August|September|October|November|December)\s+\d{4})\b",
    re.I,
)


class CourseCatalogue:
    """Load editable company course information from disk."""

    def __init__(self, path=CATALOGUE_PATH):
        with Path(path).open(encoding="utf-8") as catalogue_file:
            self._data = json.load(catalogue_file)

    @property
    def course(self):
        return self._data["course"]

    @property
    def course_name(self):
        return self.course["name"]

    @property
    def course_fee(self):
        return Decimal(str(self.course["fee"]["amount"]))

    @property
    def course_fee_display(self):
        return self.course["fee"]["display"]

    @property
    def intake_dates(self):
        return [item["date"] for item in self.course["intakes"]]

    @property
    def has_intake_dates(self):
        return bool(self.intake_dates)

    @property
    def no_intakes_message(self):
        return self.course["no_intakes_message"]

    @property
    def staff_confirmation_message(self):
        return self._data["reply_style"]["staff_confirmation_message"]

    @property
    def venue_customer_reply(self):
        return self.course["venue"]["customer_reply"]

    @property
    def venue_confirmation_required(self):
        return self.course["venue"]["confirmation_required"]

    @property
    def payment_question(self):
        return self.course["enrollment"]["payment_question"]

    def agent_context(self):
        return json.dumps(self._data, indent=2, ensure_ascii=False)

    def approved_faq_reply(self, topics):
        """Compose only staff-approved FAQ copy selected by the FAQ agent."""
        answers = {
            item["topic"].casefold(): item["answer"] for item in self._data["faqs"]
        }
        selected = []
        for topic in topics or []:
            normalized_topic = str(topic).strip().casefold()
            if normalized_topic == "course dates":
                answer = self._course_dates_reply()
            else:
                answer = answers.get(normalized_topic)
            if answer and answer not in selected:
                selected.append(answer)
        return "\n\n".join(selected) if selected else self.staff_confirmation_message

    def _course_dates_reply(self):
        if not self.has_intake_dates:
            return self.no_intakes_message
        dates = "\n".join(
            f"- {item['display']}" for item in self.course["intakes"]
        )
        return f"Our available course dates are:\n{dates} 📅"

    def ground_faq_answer(self, answer):
        """Reject high-risk numeric claims that are absent from approved content."""
        candidate = (answer or "").strip()
        if not candidate:
            return self.staff_confirmation_message

        approved_content = self.agent_context()
        allowed_money = {
            amount
            for amount in (_money_value(match) for match in MONEY_PATTERN.findall(approved_content))
            if amount is not None
        }
        allowed_money.add(self.course_fee)
        claimed_money = {
            amount
            for amount in (_money_value(match) for match in MONEY_PATTERN.findall(candidate))
            if amount is not None
        }
        if not claimed_money.issubset(allowed_money):
            return self.staff_confirmation_message

        approved_uens = {value.upper() for value in UEN_PATTERN.findall(approved_content)}
        claimed_uens = {value.upper() for value in UEN_PATTERN.findall(candidate)}
        if not claimed_uens.issubset(approved_uens):
            return self.staff_confirmation_message

        if not self.has_intake_dates and CALENDAR_DATE_PATTERN.search(candidate):
            return self.staff_confirmation_message

        return candidate

    def public_summary(self):
        return self._data.copy()


def _money_value(value):
    try:
        return Decimal(value.replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None
