"""Application-controlled enrollment state machine."""

import re
from decimal import Decimal

from backend.models import utc_now
from backend.services.privacy import mask_nric
from backend.services.validation import validate_field


ENROLLMENT_FIELDS = (
    "course",
    "full_name",
    "nric",
    "date_of_birth",
    "email",
    "preferred_intake_date",
    "mobile_number",
    "payment_method",
    "skillsfuture_amount",
    "paynow_amount",
)

FINAL_STATUSES = {"confirmed", "awaiting_course_date"}


class EnrollmentService:
    def __init__(self, ai_service, catalogue, repository):
        self.ai_service = ai_service
        self.catalogue = catalogue
        self.repository = repository

    def handle(self, conversation, message, context):
        is_new_draft = conversation.enrollment_draft is None
        draft = self.repository.get_or_create_draft(conversation)
        extraction = self.ai_service.extract_enrollment(
            message=message,
            context=context,
            draft_state=self._draft_state(draft),
        )
        extracted_fields = extraction.extracted_fields.model_dump(exclude_none=True)
        supplied_fields = self._newly_supplied_fields(
            draft, message, extracted_fields
        )

        if draft.status in FINAL_STATUSES and not supplied_fields:
            return self._already_confirmed_reply(draft), draft

        if draft.course is None:
            # There is exactly one supported MVP course. The final summary still asks
            # the participant to explicitly confirm it before the record is final.
            draft.course = self.catalogue.course_name

        intake_value = supplied_fields.get("preferred_intake_date")
        if (
            intake_value is not None
            and not self.catalogue.has_intake_dates
            and _is_awaiting_intake_confirmation(intake_value)
        ):
            supplied_fields.pop("preferred_intake_date")

        validation_errors = []
        validated_fields = {}
        for field in ENROLLMENT_FIELDS:
            if field not in supplied_fields:
                continue
            normalized, error = validate_field(
                field, supplied_fields[field], self.catalogue
            )
            if error:
                validation_errors.append((field, error))
            else:
                validated_fields[field] = normalized

        if validated_fields:
            self.repository.update_draft(draft, validated_fields)
        self._apply_payment_defaults(draft, supplied_fields)
        correction_acknowledgement = None
        if extraction.correction_requested and validated_fields:
            correction_acknowledgement = self._correction_acknowledgement(
                draft, validated_fields
            )

        if supplied_fields and draft.status in {
            "awaiting_confirmation",
            "awaiting_course_date",
            "confirmed",
        }:
            draft.status = "collecting"
            draft.confirmed_at = None

        payment_error = self._payment_error(draft)
        missing = self.missing_fields(draft, self.catalogue)
        invalid_fields = {field for field, _ in validation_errors}
        missing_without_invalid = [
            field for field in missing if field not in invalid_fields
        ]
        if validation_errors or payment_error:
            draft.status = "collecting"
            corrections = list(validation_errors)
            if payment_error:
                corrections.append(("payment_allocation", payment_error))
            return (
                self._validation_reply(
                    draft, corrections, missing_without_invalid
                ),
                draft,
            )

        if extraction.confirmation == "reject":
            draft.status = "collecting"
            draft.confirmed_at = None
            name = _first_name(draft.full_name)
            opening = f"No problem, {name}." if name else "No problem."
            return self.catalogue.enrollment_reply(
                "rejected", opening=opening
            ), draft

        if missing:
            draft.status = "collecting"
            if is_new_draft and not self._has_participant_details(draft):
                return self._introduction_reply(draft), draft
            reply = self._partial_reply(draft, missing)
            if correction_acknowledgement:
                reply = f"{correction_acknowledgement}\n\n{reply}"
            return reply, draft

        if extraction.confirmation == "confirm" and draft.status == "awaiting_confirmation":
            draft.status = (
                "confirmed"
                if self.catalogue.has_intake_dates
                else "awaiting_course_date"
            )
            draft.confirmed_at = utc_now()
            return self._confirmed_reply(draft), draft

        if extraction.correction_requested and not supplied_fields:
            draft.status = "collecting"
            return self.catalogue.enrollment_reply(
                "correction_request", name_prefix=self._name_prefix(draft)
            ), draft

        draft.status = "awaiting_confirmation"
        summary = self._confirmation_summary(draft)
        if correction_acknowledgement:
            summary = f"{correction_acknowledgement}\n\n{summary}"
        return summary, draft

    @staticmethod
    def missing_fields(draft, catalogue=None):
        required = list(ENROLLMENT_FIELDS)
        if catalogue is not None and not catalogue.has_intake_dates:
            required.remove("preferred_intake_date")
        return [field for field in required if getattr(draft, field) is None]

    def _introduction_reply(self, draft):
        return self.catalogue.enrollment_reply(
            "introduction", greeting=self._friendly_greeting(draft)
        )

    def _partial_reply(self, draft, missing):
        items = "\n".join(
            f"{index}. {self.catalogue.enrollment_field_label(field)}"
            for index, field in enumerate(missing, start=1)
        )
        return self.catalogue.enrollment_reply(
            "partial",
            greeting=self._friendly_greeting(draft),
            missing_items=items,
        )

    def _validation_reply(self, draft, corrections, missing):
        sections = []
        if corrections:
            correction_items = "\n".join(
                f"- {self.catalogue.enrollment_field_label(field)}: {error}"
                for field, error in corrections
            )
            sections.append(
                self.catalogue.enrollment_reply(
                    "validation_corrections",
                    correction_items=correction_items,
                )
            )
        if missing:
            missing_items = "\n".join(
                f"- {self.catalogue.enrollment_field_label(field)}"
                for field in missing
            )
            sections.append(
                self.catalogue.enrollment_reply(
                    "validation_missing", missing_items=missing_items
                )
            )
        name = _first_name(draft.full_name)
        greeting = f"Hi {name}" if name else "Hello"
        return self.catalogue.enrollment_reply(
            "validation",
            greeting=greeting,
            sections="\n\n".join(sections),
        )

    @staticmethod
    def _friendly_greeting(draft):
        name = _first_name(draft.full_name)
        return f"Hi {name} 👋" if name else "Hi 👋"

    @staticmethod
    def _has_participant_details(draft):
        return any(
            getattr(draft, field) is not None
            for field in ENROLLMENT_FIELDS
            if field != "course"
        )

    @staticmethod
    def _name_prefix(draft):
        name = _first_name(draft.full_name)
        return f"{name}, " if name else ""

    @staticmethod
    def _draft_state(draft):
        return {
            "course": draft.course,
            "full_name": draft.full_name,
            "nric": mask_nric(draft.nric),
            "date_of_birth": (
                draft.date_of_birth.isoformat() if draft.date_of_birth else None
            ),
            "email": draft.email,
            "preferred_intake_date": (
                draft.preferred_intake_date.isoformat()
                if draft.preferred_intake_date
                else None
            ),
            "mobile_number": draft.mobile_number,
            "payment_method": draft.payment_method,
            "skillsfuture_amount": _amount_value(draft.skillsfuture_amount),
            "paynow_amount": _amount_value(draft.paynow_amount),
            "status": draft.status,
        }

    @classmethod
    def _newly_supplied_fields(cls, draft, message, extracted_fields):
        """Keep only usable values that the current message can safely update."""
        supplied = {}
        for field, value in extracted_fields.items():
            if not cls._usable_extracted_value(value):
                continue

            current_value = getattr(draft, field)
            if current_value is not None and cls._values_equivalent(
                field, current_value, value
            ):
                continue
            if not cls._message_supports_update(field, value, message):
                continue

            supplied[field] = value

        # Payment wording in the current message is stronger evidence than a
        # model-produced label. In particular, do not reduce an explicit
        # SkillsFuture/PayNow split to PayNow merely because PayNow appears last.
        lowered = message.casefold()
        if "skillsfuture" in lowered and (
            "paynow" in lowered or "pay now" in lowered
        ):
            supplied["payment_method"] = "SkillsFuture and PayNow"
        return supplied

    @staticmethod
    def _usable_extracted_value(value):
        if value is None:
            return False
        if not isinstance(value, str):
            return True

        normalized = value.strip()
        if not normalized:
            return False
        if "*" in normalized or "redacted" in normalized.casefold():
            return False
        return normalized.casefold() not in {"null", "none", "n/a", "unknown"}

    @staticmethod
    def _values_equivalent(field, current_value, extracted_value):
        if field in {"skillsfuture_amount", "paynow_amount"}:
            try:
                return Decimal(current_value) == Decimal(str(extracted_value))
            except (ArithmeticError, ValueError):
                return False
        if field in {"nric", "mobile_number"}:
            current = re.sub(r"\W", "", str(current_value)).casefold()
            extracted = re.sub(r"\W", "", str(extracted_value)).casefold()
            return current == extracted
        current = " ".join(str(current_value).casefold().split())
        extracted = " ".join(str(extracted_value).casefold().split())
        return current == extracted

    @staticmethod
    def _message_supports_update(field, value, message):
        lowered = message.casefold()
        value_text = " ".join(str(value).casefold().split())
        cues = {
            "course": ("course", "programme"),
            "full_name": ("name", "call me"),
            "nric": ("nric", "fin"),
            "date_of_birth": ("date of birth", "dob", "born"),
            "email": ("email", "e-mail"),
            "preferred_intake_date": ("intake", "course date", "preferred date"),
            "mobile_number": ("mobile", "phone", "handphone", "hp", "contact number"),
            "payment_method": ("payment", "paynow", "pay now", "skillsfuture", "utap"),
            "skillsfuture_amount": ("skillsfuture", "sfc"),
            "paynow_amount": ("paynow", "pay now"),
        }
        if any(cue in lowered for cue in cues[field]):
            return True

        compact_message = re.sub(r"\W", "", lowered)
        compact_value = re.sub(r"\W", "", value_text)
        if field == "nric":
            return bool(
                re.fullmatch(r"[stfgm]\d{7}[a-z]", compact_value)
                and compact_value in compact_message
            )
        if field == "mobile_number":
            return len(compact_value) >= 8 and compact_value in compact_message
        if field == "email":
            return "@" in value_text and value_text in lowered
        if field in {"date_of_birth", "preferred_intake_date"}:
            return bool(
                re.search(
                    r"\b(?:19|20)\d{2}\b|\b(?:january|february|march|april|may|"
                    r"june|july|august|september|october|november|december)\b",
                    lowered,
                )
            )
        if len(value_text) >= 2 and value_text in lowered:
            return True
        return len(compact_value) >= 4 and compact_value in compact_message

    def _confirmation_summary(self, draft):
        total = Decimal(draft.skillsfuture_amount) + Decimal(draft.paynow_amount)
        return self.catalogue.enrollment_reply(
            "confirmation",
            greeting=self._friendly_greeting(draft),
            course_name=draft.course,
            course_fee=self.catalogue.course_fee_display,
            duration=self.catalogue.course["duration"].capitalize(),
            training_time=self.catalogue.course["training_time"],
            preferred_intake=_display_date(draft.preferred_intake_date),
            full_name=draft.full_name,
            masked_nric=mask_nric(draft.nric),
            date_of_birth=_display_date(draft.date_of_birth),
            email=draft.email,
            mobile_number=draft.mobile_number,
            payment_method=_payment_method_label(draft.payment_method),
            skillsfuture_amount=_display_amount(draft.skillsfuture_amount),
            paynow_amount=_display_amount(draft.paynow_amount),
            payment_total=_display_amount(total),
        )

    def _confirmed_reply(self, draft):
        if draft.status == "awaiting_course_date":
            return self.catalogue.enrollment_reply(
                "confirmed_awaiting_course_date",
                first_name=_first_name(draft.full_name),
            )
        return self.catalogue.enrollment_reply(
            "confirmed_with_course_date",
            first_name=_first_name(draft.full_name),
            preferred_intake=_display_date(draft.preferred_intake_date),
        )

    def _already_confirmed_reply(self, draft):
        if draft.status == "awaiting_course_date":
            return self.catalogue.enrollment_reply(
                "already_awaiting_course_date",
                first_name=_first_name(draft.full_name),
            )
        return self.catalogue.enrollment_reply(
            "already_confirmed", first_name=_first_name(draft.full_name)
        )

    def _apply_payment_defaults(self, draft, supplied_fields):
        if "payment_method" not in supplied_fields:
            return

        updates = {}
        if draft.payment_method in {"paynow", "utap"}:
            if "skillsfuture_amount" not in supplied_fields:
                updates["skillsfuture_amount"] = Decimal("0.00")
            if "paynow_amount" not in supplied_fields:
                updates["paynow_amount"] = self.catalogue.course_fee
        elif draft.payment_method == "skillsfuture_paynow":
            if "skillsfuture_amount" not in supplied_fields:
                updates["skillsfuture_amount"] = None
            if "paynow_amount" not in supplied_fields:
                updates["paynow_amount"] = (
                    Decimal("0.00")
                    if draft.skillsfuture_amount == self.catalogue.course_fee
                    else None
                )

        if updates:
            self.repository.update_draft(draft, updates)

    def _payment_error(self, draft):
        method = draft.payment_method
        skillsfuture = draft.skillsfuture_amount
        paynow = draft.paynow_amount
        if method is None or skillsfuture is None or paynow is None:
            return None

        if method == "skillsfuture_paynow":
            if skillsfuture <= 0:
                return (
                    "Please enter the basic-tier SkillsFuture amount you intend to use, "
                    "or choose PayNow if you will not use SkillsFuture Credits."
                )
            if skillsfuture + paynow != self.catalogue.course_fee:
                return (
                    "Your SkillsFuture and PayNow amounts must total "
                    f"{self.catalogue.course_fee_display}. Please "
                    "provide the corrected amounts."
                )
        elif method == "paynow":
            if skillsfuture != 0 or paynow != self.catalogue.course_fee:
                return (
                    "For PayNow payment, the SkillsFuture amount must be S$0 and the "
                    f"PayNow amount must be {self.catalogue.course_fee_display}."
                )
        elif method == "utap":
            if skillsfuture != 0:
                return "SkillsFuture Credits and UTAP cannot be combined for this course."
            if paynow != self.catalogue.course_fee:
                return (
                    "UTAP is a reimbursement after course completion, so the "
                    f"{self.catalogue.course_fee_display} "
                    "course fee must first be paid upfront."
                )
        return None

    def _correction_acknowledgement(self, draft, corrected_fields):
        name = _first_name(draft.full_name)
        if len(corrected_fields) == 1:
            field = next(iter(corrected_fields))
            label = self.catalogue.enrollment_field_label(field).casefold()
            return self.catalogue.enrollment_reply(
                "correction_single",
                first_name=name or "there",
                field_label=label,
            )
        return self.catalogue.enrollment_reply(
            "correction_multiple", first_name=name or "there"
        )


def _display_date(value):
    if value is None:
        return "Awaiting staff confirmation"
    return f"{value.day} {value.strftime('%B %Y')}"


def _display_amount(value):
    amount = Decimal(value)
    if amount == amount.to_integral():
        return f"S${amount:.0f}"
    return f"S${amount:.2f}"


def _amount_value(value):
    return f"{Decimal(value):.2f}" if value is not None else None


def _payment_method_label(value):
    return {
        "paynow": "PayNow",
        "skillsfuture_paynow": "SkillsFuture Credits and PayNow",
        "utap": "UTAP reimbursement after upfront payment",
    }.get(value, value)


def _is_awaiting_intake_confirmation(value):
    normalized = " ".join(str(value).casefold().split())
    return normalized in {
        "awaiting confirmation",
        "awaiting staff confirmation",
        "next available intake",
        "next available",
        "to be confirmed",
        "tbc",
    }


def _first_name(full_name):
    return full_name.split()[0] if full_name else None
