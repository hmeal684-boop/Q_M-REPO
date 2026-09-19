"""Application-controlled, staged enrollment state machine."""

import re
from datetime import date
from decimal import Decimal

from backend.models import utc_now
from backend.services.enrollment_parser import (
    is_explicit_correction,
    parse_enrollment_fields,
    redact_identity_for_ai,
)
from backend.services.privacy import mask_nric
from backend.services.validation import validate_field


IDENTITY_FIELDS = (
    "full_name",
    "nric",
    "date_of_birth",
    "email",
    "mobile_number",
)
PAYMENT_FIELDS = (
    "payment_method",
    "skillsfuture_amount",
    "paynow_amount",
)
ENROLLMENT_FIELDS = (
    "course",
    "preferred_intake_date",
    *IDENTITY_FIELDS,
    *PAYMENT_FIELDS,
)
FINAL_STATUSES = {"confirmed", "awaiting_course_date"}


class EnrollmentService:
    def __init__(self, ai_service, catalogue, repository):
        self.ai_service = ai_service
        self.catalogue = catalogue
        self.repository = repository

    def handle(self, conversation, message, context):
        draft = self.repository.get_or_create_draft(conversation)
        self._hydrate_structured_intake(draft)
        extraction = self.ai_service.extract_enrollment(
            message=redact_identity_for_ai(message),
            context=context,
            draft_state=self._draft_state(draft),
        )
        extracted_fields = extraction.extracted_fields.model_dump(exclude_none=True)
        # Known forms and structured values are resolved deterministically. These
        # values take precedence over model interpretation and still pass through
        # the same validators below.
        parsed_fields = parse_enrollment_fields(message)
        extracted_fields.update(parsed_fields)
        for field, value in self._bare_stage_value(draft, message).items():
            if field not in parsed_fields:
                extracted_fields[field] = value
        supplied_fields = self._newly_supplied_fields(
            draft, message, extracted_fields
        )
        correction_requested = (
            extraction.correction_requested or is_explicit_correction(message)
        )

        if _is_cancel_request(message):
            draft.status = "cancelled"
            draft.confirmed_at = None
            return self.catalogue.enrollment_reply("cancelled"), draft

        if draft.status in FINAL_STATUSES and not supplied_fields:
            return self._already_confirmed_reply(draft), draft

        invalid = []
        saved = {}

        course_value = supplied_fields.pop("course", None)
        course_is_selected = self._course_is_selected(
            draft, message, extraction.confirmation, supplied_fields
        )
        if course_value is not None:
            normalized, error = validate_field(
                "course", course_value, self.catalogue
            )
            if error:
                invalid.append(("course", error))
            else:
                self._save_course(draft, normalized)
                saved["course"] = normalized
        elif draft.course is None and course_is_selected:
            self._save_course(draft, self.catalogue.course_name)
            saved["course"] = draft.course

        if draft.course is None:
            draft.status = "collecting"
            if invalid:
                return self._outcome_reply(draft, saved, invalid), draft
            return self._course_selection_reply(), draft

        intake_value = supplied_fields.get("preferred_intake_date")
        if (
            intake_value is not None
            and not self.catalogue.has_intake_dates
            and _is_awaiting_intake_confirmation(intake_value)
        ):
            supplied_fields.pop("preferred_intake_date")

        previous_payment_method = draft.payment_method
        for field in ENROLLMENT_FIELDS:
            if field == "course" or field not in supplied_fields:
                continue
            normalized, error = validate_field(
                field, supplied_fields[field], self.catalogue
            )
            if error:
                invalid.append((field, error))
            else:
                saved[field] = normalized

        if (
            "payment_method" in saved
            and previous_payment_method is not None
            and saved["payment_method"] != previous_payment_method
        ):
            if "skillsfuture_amount" not in saved:
                draft.skillsfuture_amount = None
            if "paynow_amount" not in saved:
                draft.paynow_amount = None

        if saved:
            self.repository.update_draft(
                draft, {key: value for key, value in saved.items() if key != "course"}
            )
        if "preferred_intake_date" in saved:
            selected, _ = self.catalogue.match_intake_selection(
                supplied_fields["preferred_intake_date"]
            )
            if selected:
                self._save_intake(draft, selected)
        self._apply_payment_defaults(draft, saved)

        if (saved or invalid) and draft.status in {
            "awaiting_confirmation",
            "awaiting_course_date",
            "confirmed",
            "cancelled",
        }:
            draft.status = "collecting"
            draft.confirmed_at = None

        payment_error = self._payment_error(draft)
        if payment_error:
            invalid.append(("payment_allocation", payment_error))

        if invalid:
            draft.status = "collecting"
            return self._outcome_reply(draft, saved, invalid), draft

        missing = self.missing_fields(draft, self.catalogue)
        if missing:
            draft.status = "collecting"
            return self._progress_reply(draft, saved, missing), draft

        if (
            extraction.confirmation == "confirm"
            and draft.status == "awaiting_confirmation"
        ):
            intake_error = self._selected_intake_error(draft)
            if intake_error:
                self._clear_intake(draft)
                draft.status = "collecting"
                return self._outcome_reply(
                    draft, {}, [("preferred_intake_date", intake_error)]
                ), draft
            draft.status = (
                "confirmed"
                if draft.preferred_intake_date is not None
                else "awaiting_course_date"
            )
            draft.confirmed_at = utc_now()
            return self._confirmed_reply(draft), draft

        if extraction.confirmation == "reject":
            draft.status = "collecting"
            draft.confirmed_at = None
            return self.catalogue.enrollment_reply(
                "rejected", opening=self._natural_name_opening(draft, "No problem")
            ), draft

        if correction_requested and not supplied_fields:
            draft.status = "collecting"
            return self.catalogue.enrollment_reply(
                "correction_request", name_prefix=self._name_prefix(draft)
            ), draft

        draft.status = "awaiting_confirmation"
        summary = self._confirmation_summary(draft)
        if correction_requested and saved:
            summary = (
                self._correction_acknowledgement(draft, saved) + "\n\n" + summary
            )
        return summary, draft

    @classmethod
    def missing_fields(cls, draft, catalogue=None):
        if draft is None:
            return []
        if draft.course is None:
            return ["course"]
        if draft.course_fee is None:
            return ["course_fee"]
        if catalogue is not None and catalogue.has_intake_dates:
            if draft.preferred_intake_date is None:
                return ["preferred_intake_date"]

        identity_missing = [
            field for field in IDENTITY_FIELDS if getattr(draft, field) is None
        ]
        if identity_missing:
            return identity_missing
        if draft.payment_method is None:
            return ["payment_method"]
        if draft.payment_method == "paynow":
            return ["paynow_amount"] if draft.paynow_amount is None else []
        if draft.payment_method == "skillsfuture_paynow":
            if draft.skillsfuture_amount is None:
                return ["skillsfuture_amount"]
            if draft.paynow_amount is None:
                return ["paynow_amount"]
        if draft.payment_method == "utap" and draft.paynow_amount is None:
            return ["paynow_amount"]
        return []

    def next_step_prompt(self, draft):
        """Return a short reminder for deterministic greeting interruptions."""
        missing = self.missing_fields(draft, self.catalogue)
        if not missing:
            if draft.status == "awaiting_confirmation":
                return "Please review the summary and reply Confirm, Correct [field], or Cancel."
            return "Your enrolment details are already recorded."
        first = missing[0]
        if first == "course":
            return "Please confirm whether you would like to enrol in the course shown."
        if first == "course_fee":
            return "The course fee requires staff confirmation before enrolment can continue."
        if first == "preferred_intake_date":
            return (
                "Please select one of the demo course intakes."
                if self.catalogue.has_demo_intakes
                else "Please select one of the available course intakes."
            )
        return f"I still need your {self.catalogue.enrollment_field_label(first).casefold()}."

    def _course_selection_reply(self):
        course = self.catalogue.course
        code = course.get("code")
        code_line = f"\n- Course code: {code}" if code else ""
        fee = (
            self.catalogue.course_fee_display
            if self.catalogue.course_fee is not None
            else "Awaiting staff confirmation"
        )
        intake = self.catalogue.course_selection_intake_display
        return self.catalogue.enrollment_reply(
            "course_selection",
            course_name=self.catalogue.course_name,
            course_code_line=code_line,
            course_fee=fee,
            currency=course.get("fee", {}).get("currency", ""),
            duration=course["duration"].capitalize(),
            intake=intake,
            skillsfuture=self.catalogue.skillsfuture_eligibility_display,
        )

    def _progress_reply(self, draft, saved, missing):
        if missing == ["course_fee"]:
            return self.catalogue.enrollment_reply("course_fee_unavailable")
        if missing == ["preferred_intake_date"]:
            demo = self.catalogue.has_demo_intakes
            return self._prepend_saved(
                saved,
                self.catalogue.enrollment_reply(
                    "intake_selection",
                    demo_heading="Demo intake dates — prototype only\n\n" if demo else "",
                    intake_description="a demo intake" if demo else "an available intake",
                    intake_choices=self.catalogue.intake_choices(),
                    demo_footer=(
                        f"\n\n{self.catalogue.demo_intake_notice}" if demo else ""
                    ),
                ),
            )
        if any(field in IDENTITY_FIELDS for field in missing):
            missing_identity = [field for field in missing if field in IDENTITY_FIELDS]
            if saved:
                return self._outcome_reply(draft, saved, [])
            return self.catalogue.enrollment_reply(
                "participant_details",
                intake_notice=(
                    self.catalogue.no_intakes_message + "\n\n"
                    if not self.catalogue.has_intake_dates
                    else ""
                ),
                missing_template=self._participant_template(missing_identity),
            )
        if missing == ["payment_method"]:
            return self._prepend_saved(saved, self._payment_summary(draft))
        return self._prepend_saved(saved, self._payment_amount_prompt(draft, missing))

    def _outcome_reply(self, draft, saved, invalid):
        sections = []
        if saved:
            saved_items = "\n".join(
                f"- {self.catalogue.enrollment_field_label(field)}: "
                f"{self._safe_display(field, value)}"
                for field, value in saved.items()
            )
            sections.append(
                self.catalogue.enrollment_reply(
                    "outcome_saved", saved_items=saved_items
                )
            )
        if invalid:
            invalid_items = "\n".join(
                f"- {self.catalogue.enrollment_field_label(field)}: {error}"
                for field, error in invalid
            )
            sections.append(
                self.catalogue.enrollment_reply(
                    "outcome_invalid", invalid_items=invalid_items
                )
            )

        missing = self.missing_fields(draft, self.catalogue)
        invalid_fields = {field for field, _ in invalid}
        still_required = [field for field in missing if field not in invalid_fields]
        if still_required:
            missing_items = "\n".join(
                f"- {self.catalogue.enrollment_field_label(field)}"
                for field in still_required
            )
            sections.append(
                self.catalogue.enrollment_reply(
                    "outcome_missing", missing_items=missing_items
                )
            )

        if len(invalid) == 1 and invalid[0][0] == "nric":
            closing = self.catalogue.enrollment_reply("correct_nric_only")
        elif invalid:
            closing = self.catalogue.enrollment_reply("correct_fields")
        elif still_required == ["payment_method"]:
            closing = self._payment_summary(draft)
        elif still_required and all(field in IDENTITY_FIELDS for field in still_required):
            closing = self.catalogue.enrollment_reply(
                "continue_participant_details",
                missing_template=self._participant_template(still_required),
            )
        elif still_required:
            closing = self._payment_amount_prompt(draft, still_required)
        else:
            closing = self._confirmation_summary(draft)
            draft.status = "awaiting_confirmation"
        return "\n\n".join([*sections, closing])

    def _payment_summary(self, draft):
        return self.catalogue.enrollment_reply(
            "payment_selection",
            course_name=draft.course,
            course_fee=self._course_fee_display(draft),
            skillsfuture=self.catalogue.skillsfuture_eligibility_display,
            amount_due=self._course_fee_display(draft),
            payment_question=self.catalogue.payment_question,
        )

    def _payment_amount_prompt(self, draft, missing):
        if draft.payment_method == "paynow":
            return self.catalogue.enrollment_reply(
                "paynow_amount", course_fee=self._course_fee_display(draft)
            )
        if draft.payment_method == "utap":
            return self.catalogue.enrollment_reply(
                "utap_upfront_amount", course_fee=self._course_fee_display(draft)
            )
        if missing == ["skillsfuture_amount"]:
            return self.catalogue.enrollment_reply(
                "skillsfuture_amount", course_fee=self._course_fee_display(draft)
            )
        return self.catalogue.enrollment_reply(
            "paynow_remainder",
            remaining=_display_amount(self._remaining_amount(draft)),
            course_fee=self._course_fee_display(draft),
        )

    def _confirmation_summary(self, draft):
        total = Decimal(draft.skillsfuture_amount or 0) + Decimal(
            draft.paynow_amount or 0
        )
        payment_lines = []
        if Decimal(draft.skillsfuture_amount or 0) > 0:
            payment_lines.append(
                f"- SkillsFuture amount: {_display_amount(draft.skillsfuture_amount)}"
            )
        if Decimal(draft.paynow_amount or 0) > 0:
            payment_lines.append(
                f"- PayNow amount: {_display_amount(draft.paynow_amount)}"
            )
        code = self.catalogue.course.get("code")
        demo_note = (
            self.catalogue.enrollment_reply("demo_note") + "\n"
            if draft.intake_is_demo
            else ""
        )
        return self.catalogue.enrollment_reply(
            "confirmation",
            course_name=draft.course,
            course_code_line=f"\n- Course code: {code}" if code else "",
            course_fee=self._course_fee_display(draft),
            duration=self.catalogue.course["duration"].capitalize(),
            training_time=self.catalogue.course["training_time"],
            intake_label=(
                "Selected demo intake"
                if draft.intake_is_demo
                else "Preferred intake"
            ),
            preferred_intake=self._intake_display(draft),
            demo_note=demo_note,
            full_name=draft.full_name,
            masked_nric=mask_nric(draft.nric),
            date_of_birth=_display_date(draft.date_of_birth),
            masked_email=_mask_email(draft.email),
            masked_mobile=_mask_mobile(draft.mobile_number),
            payment_method=_payment_method_label(draft.payment_method),
            payment_lines="\n".join(payment_lines),
            payment_total=_display_amount(total),
            remaining=_display_amount(max(Decimal("0"), self._fee(draft) - total)),
        )

    def _confirmed_reply(self, draft):
        if draft.status == "awaiting_course_date":
            return self.catalogue.enrollment_reply(
                "confirmed_awaiting_course_date",
                first_name=_first_name(draft.full_name),
                enrollment_id=draft.id,
            )
        reply = self.catalogue.enrollment_reply(
            "confirmed_with_course_date",
            first_name=_first_name(draft.full_name),
            preferred_intake=self._intake_display(draft),
            enrollment_id=draft.id,
        )
        if draft.intake_is_demo:
            reply = reply.replace("Selected intake:", "Selected demo intake:")
            reply += "\n\n" + self.catalogue.enrollment_reply("demo_note")
        return reply

    def _already_confirmed_reply(self, draft):
        if draft.status == "awaiting_course_date":
            return self.catalogue.enrollment_reply(
                "already_awaiting_course_date",
                first_name=_first_name(draft.full_name),
            )
        return self.catalogue.enrollment_reply(
            "already_confirmed", first_name=_first_name(draft.full_name)
        )

    def _apply_payment_defaults(self, draft, saved):
        if "payment_method" not in saved and not any(
            field in saved for field in ("skillsfuture_amount", "paynow_amount")
        ):
            return
        updates = {}
        if draft.payment_method in {"paynow", "utap"}:
            updates["skillsfuture_amount"] = Decimal("0.00")
        elif draft.payment_method == "skillsfuture_paynow":
            if draft.skillsfuture_amount == self._fee(draft):
                updates["paynow_amount"] = Decimal("0.00")
            elif "skillsfuture_amount" in saved and "paynow_amount" not in saved:
                updates["paynow_amount"] = None
        if updates:
            self.repository.update_draft(draft, updates)

    def _payment_error(self, draft):
        fee = self._fee(draft)
        method = draft.payment_method
        skillsfuture = draft.skillsfuture_amount
        paynow = draft.paynow_amount
        if not fee or method is None:
            return None
        if method == "paynow" and paynow is not None:
            if skillsfuture != 0 or paynow != fee:
                return self._allocation_difference(fee, Decimal(skillsfuture or 0) + paynow)
        elif method == "skillsfuture_paynow":
            if skillsfuture is not None and skillsfuture <= 0:
                return (
                    "Enter the basic-tier SkillsFuture amount you intend to use, "
                    "or choose PayNow if you will not use SkillsFuture Credits."
                )
            if skillsfuture is not None and paynow is not None:
                total = skillsfuture + paynow
                if total != fee:
                    return self._allocation_difference(fee, total)
        elif method == "utap" and paynow is not None:
            if skillsfuture != 0:
                return "SkillsFuture Credits and UTAP cannot be combined for this course."
            if paynow != fee:
                return self._allocation_difference(fee, paynow)
        return None

    @staticmethod
    def _allocation_difference(fee, total):
        if total < fee:
            return (
                f"The course fee is {_display_amount(fee)}, but the amounts entered "
                f"total {_display_amount(total)}. There is "
                f"{_display_amount(fee - total)} remaining. Please update the allocation."
            )
        return (
            f"The course fee is {_display_amount(fee)}, but the amounts entered total "
            f"{_display_amount(total)}, which is {_display_amount(total - fee)} too much. "
            "Please update the allocation."
        )

    def _save_course(self, draft, course_name):
        switching = draft.course is not None and draft.course != course_name
        draft.course = course_name
        draft.course_fee = self.catalogue.course_fee
        if switching:
            self._clear_intake(draft)
            draft.payment_method = None
            draft.skillsfuture_amount = None
            draft.paynow_amount = None

    @staticmethod
    def _clear_intake(draft):
        draft.preferred_intake_date = None
        draft.intake_id = None
        draft.intake_start_date = None
        draft.intake_end_date = None
        draft.intake_is_demo = None

    @staticmethod
    def _save_intake(draft, intake):
        draft.intake_id = intake["id"]
        draft.intake_start_date = date.fromisoformat(intake["start_date"])
        draft.intake_end_date = date.fromisoformat(intake["end_date"])
        draft.intake_is_demo = bool(intake["is_demo"])
        draft.preferred_intake_date = draft.intake_start_date

    def _hydrate_structured_intake(self, draft):
        if draft.preferred_intake_date is None or draft.intake_start_date is not None:
            return
        intake = self.catalogue.intake_for_start_date(draft.preferred_intake_date)
        if intake:
            self._save_intake(draft, intake)

    def _selected_intake_error(self, draft):
        if draft.preferred_intake_date is None:
            return None
        intake = (
            self.catalogue.intake_for_id(draft.intake_id)
            if draft.intake_id
            else self.catalogue.intake_for_start_date(draft.preferred_intake_date)
        )
        if intake is None:
            return "The selected intake is no longer available. Please choose another intake."
        if intake["status"] == "closed":
            return f"The {intake['display_date']} intake is closed. Please choose another intake."
        if intake["status"] != "open":
            return f"The {intake['display_date']} intake is unavailable. Please choose another intake."
        return None

    def _intake_display(self, draft):
        if draft.intake_start_date and draft.intake_end_date:
            return _display_intake_range(
                draft.intake_start_date, draft.intake_end_date
            )
        return _display_date(draft.preferred_intake_date)

    def _course_is_selected(self, draft, message, confirmation, supplied):
        if draft.course is not None:
            return True
        lowered = " ".join(message.casefold().split())
        explicit = any(
            phrase in lowered
            for phrase in (
                "this course",
                "select the course",
                "choose the course",
                "enrol me in",
                "enroll me in",
                self.catalogue.course_name.casefold(),
            )
        )
        # Supplying participant details after the only approved course was shown
        # also accepts that course, so the entered details are not discarded.
        has_details = any(
            field in supplied
            for field in (*IDENTITY_FIELDS, *PAYMENT_FIELDS, "preferred_intake_date")
        )
        return explicit or has_details or confirmation == "confirm"

    def _bare_stage_value(self, draft, message):
        """Map a safe bare reply to the one field the current stage expects."""
        stripped = message.strip()
        if (
            draft.course is not None
            and self.catalogue.has_intake_dates
            and (
                draft.preferred_intake_date is None
                or is_explicit_correction(message)
            )
        ):
            intake_cue = bool(
                re.search(
                    r"(?i)\b(?:intake|course\s+date|choose|select)\b", stripped
                )
                or re.fullmatch(r"\d+", stripped)
                or re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped)
                or re.fullmatch(
                    r"(?i)\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–]\s*\d{1,2})?\s+"
                    r"(?:january|february|march|april|may|june|july|august|"
                    r"september|october|november|december)(?:\s+\d{4})?",
                    stripped,
                )
            )
            if intake_cue:
                return {"preferred_intake_date": stripped}
        money = re.fullmatch(
            r"(?:S\$|\$)?\s*(-?\d+(?:\.\d{1,2})?)", stripped, re.I
        )
        if not money or draft.payment_method is None:
            return {}
        value = money.group(1)
        if draft.payment_method in {"paynow", "utap"} and draft.paynow_amount is None:
            return {"paynow_amount": value}
        if draft.payment_method == "skillsfuture_paynow":
            if draft.skillsfuture_amount is None:
                return {"skillsfuture_amount": value}
            if draft.paynow_amount is None:
                return {"paynow_amount": value}
        return {}

    @staticmethod
    def _newly_supplied_fields(draft, message, extracted_fields):
        supplied = {}
        for field, value in extracted_fields.items():
            if field not in ENROLLMENT_FIELDS:
                continue
            if not EnrollmentService._usable_extracted_value(value):
                continue
            current_value = getattr(draft, field)
            if current_value is not None and EnrollmentService._values_equivalent(
                field, current_value, value
            ):
                continue
            if not EnrollmentService._message_supports_update(field, value, message):
                continue
            supplied[field] = value
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
            if field == "preferred_intake_date" and (
                re.fullmatch(r"\s*\d+\s*", message)
                or re.search(r"(?i)\b(?:intake|course\s+date|choose|select)\b", message)
            ):
                return True
            return bool(
                re.search(
                    r"\b(?:19|20)\d{2}\b|\b(?:january|february|march|april|may|"
                    r"june|july|august|september|october|november|december)\b",
                    lowered,
                )
            )
        return len(value_text) >= 2 and value_text in lowered

    def _draft_state(self, draft):
        return {
            "course": draft.course,
            "course_fee": _amount_value(draft.course_fee),
            "full_name": draft.full_name,
            "nric": mask_nric(draft.nric),
            "date_of_birth": draft.date_of_birth.isoformat() if draft.date_of_birth else None,
            "email": draft.email,
            "preferred_intake_date": (
                draft.preferred_intake_date.isoformat()
                if draft.preferred_intake_date
                else None
            ),
            "intake_id": draft.intake_id,
            "intake_start_date": (
                draft.intake_start_date.isoformat()
                if draft.intake_start_date
                else None
            ),
            "intake_end_date": (
                draft.intake_end_date.isoformat()
                if draft.intake_end_date
                else None
            ),
            "intake_is_demo": draft.intake_is_demo,
            "mobile_number": draft.mobile_number,
            "payment_method": draft.payment_method,
            "skillsfuture_amount": _amount_value(draft.skillsfuture_amount),
            "paynow_amount": _amount_value(draft.paynow_amount),
            "status": draft.status,
        }

    def _participant_template(self, fields):
        return "\n".join(
            f"{self.catalogue.enrollment_field_label(field)}:" for field in fields
        )

    def _prepend_saved(self, saved, reply):
        if not saved:
            return reply
        items = "\n".join(
            f"- {self.catalogue.enrollment_field_label(field)}: "
            f"{self._safe_display(field, value)}"
            for field, value in saved.items()
        )
        return self.catalogue.enrollment_reply(
            "outcome_saved", saved_items=items
        ) + "\n\n" + reply

    def _safe_display(self, field, value):
        if field == "nric":
            return mask_nric(value)
        if field == "email":
            return _mask_email(value)
        if field == "mobile_number":
            return _mask_mobile(value)
        if field == "preferred_intake_date":
            intake = self.catalogue.intake_for_start_date(value)
            return intake["display_date"] if intake else _display_date(value)
        if field == "date_of_birth":
            return _display_date(value)
        if field in {"skillsfuture_amount", "paynow_amount"}:
            return _display_amount(value)
        if field == "payment_method":
            return _payment_method_label(value)
        return str(value)

    def _remaining_amount(self, draft):
        allocated = Decimal(draft.skillsfuture_amount or 0) + Decimal(
            draft.paynow_amount or 0
        )
        return max(Decimal("0"), self._fee(draft) - allocated)

    def _fee(self, draft):
        return Decimal(draft.course_fee or self.catalogue.course_fee or 0)

    def _course_fee_display(self, draft):
        if draft.course_fee is None:
            return "Awaiting staff confirmation"
        if draft.course_fee == self.catalogue.course_fee:
            return self.catalogue.course_fee_display
        return _display_amount(draft.course_fee)

    def _correction_acknowledgement(self, draft, corrected_fields):
        fields = [field for field in corrected_fields if field != "course"]
        name = _first_name(draft.full_name) or "there"
        if len(fields) == 1:
            label = self.catalogue.enrollment_field_label(fields[0]).casefold()
            return self.catalogue.enrollment_reply(
                "correction_single", first_name=name, field_label=label
            )
        return self.catalogue.enrollment_reply(
            "correction_multiple", first_name=name
        )

    @staticmethod
    def _name_prefix(draft):
        name = _first_name(draft.full_name)
        return f"{name}, " if name else ""

    @staticmethod
    def _natural_name_opening(draft, opening):
        name = _first_name(draft.full_name)
        return f"{opening}, {name}." if name else f"{opening}."


def _display_date(value):
    if value is None:
        return "Awaiting staff confirmation"
    return f"{value.day} {value.strftime('%B %Y')}"


def _display_intake_range(start, end):
    if start == end:
        return _display_date(start)
    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {start.strftime('%B %Y')}"
    if start.year == end.year:
        return f"{start.day} {start.strftime('%B')}–{end.day} {end.strftime('%B %Y')}"
    return (
        f"{start.day} {start.strftime('%B %Y')}–"
        f"{end.day} {end.strftime('%B %Y')}"
    )


def _display_amount(value):
    amount = Decimal(value or 0)
    if amount == amount.to_integral():
        return f"S${amount:.0f}"
    return f"S${amount:.2f}"


def _amount_value(value):
    return f"{Decimal(value):.2f}" if value is not None else None


def _payment_method_label(value):
    return {
        "paynow": "PayNow",
        "skillsfuture_paynow": "Basic-tier SkillsFuture Credits and PayNow",
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


def _is_cancel_request(message):
    normalized = re.sub(r"[^a-z\s]", "", message.casefold()).strip()
    return normalized in {
        "cancel",
        "cancel enrollment",
        "cancel enrolment",
        "stop enrollment",
        "stop enrolment",
    }


def _mask_email(value):
    local, separator, domain = str(value or "").partition("@")
    if not separator:
        return "Protected"
    visible = local[:1] if local else ""
    return f"{visible}***@{domain}"


def _mask_mobile(value):
    text = str(value or "")
    return f"****{text[-4:]}" if len(text) >= 4 else "Protected"


def _first_name(full_name):
    return full_name.split()[0] if full_name else None
