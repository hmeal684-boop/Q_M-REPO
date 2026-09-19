"""Provider for company-supplied course and enrollment information."""

import json
import re
from copy import deepcopy
from datetime import date, timedelta
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

    def __init__(self, path=CATALOGUE_PATH, enable_demo_intakes=False):
        with Path(path).open(encoding="utf-8") as catalogue_file:
            self._data = json.load(catalogue_file)
        self.enable_demo_intakes = bool(enable_demo_intakes)
        self._validate_demo_intakes()

    @property
    def course(self):
        return self._data["course"]

    @property
    def course_name(self):
        return self.course["name"]

    @property
    def course_fee(self):
        amount = self.course.get("fee", {}).get("amount")
        if amount in (None, ""):
            return None
        return Decimal(str(amount))

    @property
    def course_fee_display(self):
        return self.course.get("fee", {}).get("display") or (
            f"{self.course.get('fee', {}).get('currency', 'SGD')} "
            f"{self.course_fee:.2f}"
            if self.course_fee is not None
            else "Awaiting staff confirmation"
        )

    @property
    def skillsfuture_eligibility_display(self):
        funding = self.course.get("skillsfuture", {})
        if not funding:
            return "Awaiting staff confirmation"
        if funding.get("basic_tier_accepted") and not funding.get(
            "mid_career_tier_accepted"
        ):
            return (
                "Basic-tier SkillsFuture Credits are accepted; Mid-Career "
                "SkillsFuture Credits cannot be used."
            )
        return funding.get("customer_reply") or "Awaiting staff confirmation"

    @property
    def approved_intakes(self):
        return [
            self._normalise_intake(item, is_demo=False, index=index)
            for index, item in enumerate(self.course.get("intakes", []), start=1)
        ]

    @property
    def demo_intakes(self):
        return [
            self._normalise_intake(item, is_demo=True, index=index)
            for index, item in enumerate(self.course.get("demo_intakes", []), start=1)
        ]

    @property
    def intakes(self):
        return [
            *self.approved_intakes,
            *(self.demo_intakes if self.enable_demo_intakes else []),
        ]

    @property
    def selectable_intakes(self):
        return [item for item in self.intakes if item["status"] == "open"]

    @property
    def intake_dates(self):
        return [item["start_date"] for item in self.selectable_intakes]

    @property
    def has_intake_dates(self):
        return bool(self.intake_dates)

    @property
    def has_demo_intakes(self):
        return any(item["is_demo"] for item in self.selectable_intakes)

    @property
    def demo_intake_notice(self):
        return self.course.get(
            "demo_intake_notice",
            "Demo intake dates — prototype only. These dates require staff confirmation.",
        )

    @property
    def course_selection_intake_display(self):
        if not self.has_intake_dates:
            return "Awaiting staff confirmation"
        if self.has_demo_intakes:
            return "Demo intake dates available — prototype only"
        return ", ".join(item["display_date"] for item in self.selectable_intakes)

    def intake_choices(self):
        return "\n".join(
            f"{index}. {item['display_date']}"
            for index, item in enumerate(self.selectable_intakes, start=1)
        )

    def intake_for_start_date(self, value):
        key = value.isoformat() if isinstance(value, date) else str(value or "")
        return next(
            (item for item in self.intakes if item["start_date"] == key), None
        )

    def intake_for_id(self, intake_id):
        return next(
            (item for item in self.intakes if item["id"] == intake_id), None
        )

    def match_intake_selection(self, value):
        """Resolve a numbered, dated or natural-language intake selection."""
        if not self.intakes:
            return None, self.no_intakes_message

        supplied = _normalise_intake_text(value)
        available = self.selectable_intakes
        number = re.fullmatch(r"\d+", supplied)
        if number:
            position = int(number.group())
            if 1 <= position <= len(available):
                return available[position - 1], None
            return None, self._intake_clarification(
                "Please choose one of the available intake numbers."
            )

        exact = []
        for item in self.intakes:
            aliases = {
                _normalise_intake_text(item["id"]),
                _normalise_intake_text(item["start_date"]),
                _normalise_intake_text(item["display_date"]),
                _normalise_intake_text(
                    f"{item['start_date']} to {item['end_date']}"
                ),
            }
            if supplied in aliases or any(alias and alias in supplied for alias in aliases):
                exact.append(item)

        matches = exact or self._natural_intake_matches(supplied)
        unique = {item["id"]: item for item in matches}
        if len(unique) > 1:
            return None, self._intake_clarification(
                "That choice could refer to more than one intake."
            )
        if len(unique) == 1:
            selected = next(iter(unique.values()))
            if selected["status"] == "closed":
                return None, self._intake_clarification(
                    f"The {selected['display_date']} intake is closed."
                )
            if selected["status"] != "open":
                return None, self._intake_clarification(
                    f"The {selected['display_date']} intake is unavailable."
                )
            return selected, None
        return None, self._intake_clarification(
            "That date is not one of the available intakes."
        )

    def _natural_intake_matches(self, supplied):
        month_names = (
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        )
        mentioned_months = {
            index for index, name in enumerate(month_names, start=1) if name in supplied
        }
        if not mentioned_months:
            return []
        day_match = re.search(r"\b([0-3]?\d)(?:st|nd|rd|th)?\b", supplied)
        year_match = re.search(r"\b(20\d{2})\b", supplied)
        day = int(day_match.group(1)) if day_match else None
        year = int(year_match.group(1)) if year_match else None
        matches = []
        for item in self.intakes:
            start = date.fromisoformat(item["start_date"])
            if start.month not in mentioned_months:
                continue
            if day is not None and start.day != day:
                continue
            if year is not None and start.year != year:
                continue
            matches.append(item)
        return matches

    def _intake_clarification(self, reason):
        if not self.selectable_intakes:
            return f"{reason} No open intake is currently available. Staff confirmation is required."
        return f"{reason}\n\nAvailable choices:\n{self.intake_choices()}"

    def _validate_demo_intakes(self):
        ids = set()
        for item in self.demo_intakes:
            if not item["id"] or item["id"] in ids:
                raise ValueError("Every demo intake must have a unique stable ID.")
            ids.add(item["id"])
            start = date.fromisoformat(item["start_date"])
            end = date.fromisoformat(item["end_date"])
            if end != start + timedelta(days=1):
                raise ValueError("Demo intake dates must be two consecutive days.")
            if not item["is_demo"]:
                raise ValueError("Every demo intake must be marked is_demo=true.")

    @staticmethod
    def _normalise_intake(item, is_demo, index):
        start = item.get("start_date") or item.get("date")
        if not start:
            raise ValueError("Every intake must provide a start date.")
        end = item.get("end_date") or start
        start_date = date.fromisoformat(str(start))
        end_date = date.fromisoformat(str(end))
        return {
            "id": item.get("id") or f"approved-{start_date.isoformat()}-{index}",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "display_date": item.get("display_date")
            or item.get("display")
            or _display_intake_range(start_date, end_date),
            "status": str(item.get("status", "open")).casefold(),
            "is_demo": bool(item.get("is_demo", is_demo)),
        }

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

    @property
    def enrollment_templates(self):
        return self.course["enrollment"]["reply_templates"]

    def enrollment_reply(self, template_name, **values):
        """Render centrally maintained enrolment wording with validated values."""
        return self.enrollment_templates[template_name].format(**values)

    def enrollment_field_label(self, field):
        return self.course["enrollment"]["field_labels"].get(
            field, field.replace("_", " ").title()
        )

    @property
    def enrollment_faq_resume_prompt(self):
        return self.enrollment_templates["faq_resume"]

    def agent_context(self):
        context = deepcopy(self._data)
        context["course"]["intakes"] = self.intakes
        context["course"].pop("demo_intakes", None)
        if not self.enable_demo_intakes:
            context["course"].pop("demo_intake_notice", None)
        context["demo_intakes_enabled"] = self.enable_demo_intakes
        return json.dumps(context, indent=2, ensure_ascii=False)

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
            f"- {item['display_date']}" for item in self.selectable_intakes
        )
        if self.has_demo_intakes:
            return f"{self.demo_intake_notice}\n\nDemo intake dates:\n{dates}"
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
        if self.course_fee is not None:
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
        return deepcopy(self._data)


def _money_value(value):
    try:
        return Decimal(value.replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, AttributeError):
        return None


def _normalise_intake_text(value):
    return " ".join(
        str(value or "")
        .casefold()
        .replace("–", "-")
        .replace("—", "-")
        .replace(",", " ")
        .split()
    ).strip(" .")


def _display_intake_range(start, end):
    if start == end:
        return f"{start.day} {start.strftime('%B %Y')}"
    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {start.strftime('%B %Y')}"
    if start.year == end.year:
        return f"{start.day} {start.strftime('%B')}–{end.day} {end.strftime('%B %Y')}"
    return (
        f"{start.day} {start.strftime('%B %Y')}–"
        f"{end.day} {end.strftime('%B %Y')}"
    )
