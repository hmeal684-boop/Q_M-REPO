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

        if validation_errors:
            field, error = validation_errors[0]
            if field == "preferred_intake_date" and not self.catalogue.has_intake_dates:
                return error, draft
            return f"{self._name_prefix(draft)}{error}\n\n{self._question_for(field, draft)}", draft

        payment_error = self._payment_error(draft)
        if payment_error:
            return f"{self._name_prefix(draft)}{payment_error}", draft

        if extraction.confirmation == "reject":
            draft.status = "collecting"
            draft.confirmed_at = None
            name = _first_name(draft.full_name)
            opening = f"No problem, {name}." if name else "No problem."
            return (
                f"{opening} "
                "Your enrolment has not been confirmed. "
                "Which detail would you like to correct?"
            ), draft

        missing = self.missing_fields(draft, self.catalogue)
        if missing:
            draft.status = "collecting"
            question = self._question_for(missing[0], draft)
            if is_new_draft and missing[0] == "full_name":
                question = "I’d be happy to help you enrol! ✅ May I have your full name?"
            if correction_acknowledgement:
                question = f"{correction_acknowledgement}\n\n{question}"
            return question, draft

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
            return (
                f"{self._name_prefix(draft)}Please tell me which detail to change and "
                "provide the new value, for example: ‘Change my email to name@example.com’."
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

    def _question_for(self, field, draft=None):
        questions = {
            "course": (
                f"Would you like to enrol in the {self.catalogue.course_name}?"
            ),
            "full_name": "May I have your full name?",
            "nric": "Please provide your NRIC or FIN.",
            "date_of_birth": "What is your date of birth?",
            "email": "What email address should be used for this enrollment?",
            "preferred_intake_date": (
                "Which intake date do you prefer: "
                + " or ".join(
                    item["display"] for item in self.catalogue.course["intakes"]
                )
                + "?"
                if self.catalogue.has_intake_dates
                else self.catalogue.no_intakes_message
            ),
            "mobile_number": "What mobile number should we use to contact you?",
            "payment_method": self.catalogue.payment_question,
            "skillsfuture_amount": (
                "How much basic-tier SkillsFuture Credit will you use toward the "
                f"{self.catalogue.course_fee_display} course fee?"
            ),
            "paynow_amount": self._paynow_question(draft),
        }
        question = questions[field]
        if draft and draft.full_name and field != "full_name":
            name = _first_name(draft.full_name)
            if field == "nric":
                return f"Thanks, {name}. {question}"
            return f"{name}, {question[0].lower()}{question[1:]}"
        return question

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

    @staticmethod
    def _confirmation_summary(draft):
        name = _first_name(draft.full_name)
        heading = f"{name}, please" if name else "Please"
        return (
            f"{heading} confirm your enrolment details:\n\n"
            f"Course: {draft.course}\n"
            f"Full name: {draft.full_name}\n"
            f"NRIC/FIN: {mask_nric(draft.nric)}\n"
            f"Date of birth: {_display_date(draft.date_of_birth)}\n"
            f"Email: {draft.email}\n"
            f"Mobile number: {draft.mobile_number}\n"
            f"Selected intake: {_display_date(draft.preferred_intake_date)}\n"
            f"Payment option: {_payment_method_label(draft.payment_method)}\n"
            f"SkillsFuture amount: {_display_amount(draft.skillsfuture_amount)}\n"
            f"PayNow amount: {_display_amount(draft.paynow_amount)}\n\n"
            "Please confirm that these details are correct, or tell me what to change."
        )

    @staticmethod
    def _confirmed_reply(draft):
        if draft.status == "awaiting_course_date":
            return (
                f"Thank you, {_first_name(draft.full_name)}. Your enrolment details "
                "have been saved. Our upcoming course dates are being updated, and "
                "our team will confirm an available date with you."
            )
        return (
            f"Thank you, {_first_name(draft.full_name)}. Your enrolment has been "
            "recorded successfully.\n\n"
            f"Course: {draft.course}\n"
            f"Participant: {draft.full_name}\n"
            f"NRIC/FIN: {mask_nric(draft.nric)}\n"
            f"Preferred intake: {_display_date(draft.preferred_intake_date)}"
        )

    @staticmethod
    def _already_confirmed_reply(draft):
        if draft.status == "awaiting_course_date":
            return (
                f"{_first_name(draft.full_name)}, your enrolment details are saved. "
                "Our team will confirm an available course date with you."
            )
        return (
            f"{_first_name(draft.full_name)}, your enrolment is already confirmed. "
            "No further action is needed."
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
                updates["paynow_amount"] = None

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

    def _paynow_question(self, draft):
        if draft and draft.payment_method == "utap":
            return (
                "UTAP is claimed after course completion, so the "
                f"{self.catalogue.course_fee_display} fee must be "
                "paid upfront. How much will you pay by PayNow?"
            )
        return (
            "How much will you pay by PayNow? Your SkillsFuture and PayNow amounts "
            f"should total {self.catalogue.course_fee_display}."
        )

    @staticmethod
    def _correction_acknowledgement(draft, corrected_fields):
        name = _first_name(draft.full_name)
        if len(corrected_fields) == 1:
            field = next(iter(corrected_fields))
            label = {
                "course": "course",
                "full_name": "name",
                "nric": "NRIC/FIN",
                "date_of_birth": "date of birth",
                "email": "email address",
                "preferred_intake_date": "selected intake",
                "mobile_number": "mobile number",
                "payment_method": "payment option",
                "skillsfuture_amount": "SkillsFuture amount",
                "paynow_amount": "PayNow amount",
            }[field]
            opening = f"Thanks, {name}." if name else "Thanks."
            return f"{opening} I’ve updated your {label}."
        opening = f"Thanks, {name}." if name else "Thanks."
        return f"{opening} I’ve updated those details."


def _display_date(value):
    if value is None:
        return "Awaiting confirmation from our team"
    return f"{value.day} {value.strftime('%B %Y')}"


def _display_amount(value):
    return f"S${Decimal(value):.2f}"


def _amount_value(value):
    return f"{Decimal(value):.2f}" if value is not None else None


def _payment_method_label(value):
    return {
        "paynow": "PayNow",
        "skillsfuture_paynow": "Basic-tier SkillsFuture Credits with PayNow remainder",
        "utap": "UTAP reimbursement after upfront payment",
    }.get(value, value)


def _first_name(full_name):
    return full_name.split()[0] if full_name else None
