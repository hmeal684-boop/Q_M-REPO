"""Application-controlled enrollment state machine."""

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
        supplied_fields = extraction.extracted_fields.model_dump(exclude_none=True)

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
                "Your enrollment has not been confirmed. "
                "Which detail would you like to correct?"
            ), draft

        missing = self.missing_fields(draft, self.catalogue)
        if missing:
            draft.status = "collecting"
            question = self._question_for(missing[0], draft)
            if is_new_draft and missing[0] == "full_name":
                question = "I’d be happy to help you enroll! ✅ May I have your full name?"
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
        return self._confirmation_summary(draft), draft

    @staticmethod
    def missing_fields(draft, catalogue=None):
        required = list(ENROLLMENT_FIELDS)
        if catalogue is not None and not catalogue.has_intake_dates:
            required.remove("preferred_intake_date")
        return [field for field in required if getattr(draft, field) is None]

    def _question_for(self, field, draft=None):
        questions = {
            "course": (
                "Would you like to enroll in the 2-Day Basic Certificate in "
                "Dental Assisting?"
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
            "payment_method": (
                "Which payment option would you like to use: PayNow, basic-tier "
                "SkillsFuture Credits with any PayNow remainder, or UTAP reimbursement?"
            ),
            "skillsfuture_amount": (
                "How much basic-tier SkillsFuture Credit will you use toward the "
                "S$600 course fee?"
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

    @staticmethod
    def _confirmation_summary(draft):
        name = _first_name(draft.full_name)
        heading = f"{name}, please" if name else "Please"
        return (
            f"{heading} confirm your enrollment details:\n\n"
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
                f"Thank you, {_first_name(draft.full_name)}. Your enrollment details "
                "have been saved. Our upcoming course dates are being updated, and "
                "our team will confirm an available date with you."
            )
        return (
            f"Thank you, {_first_name(draft.full_name)}. Your enrollment has been "
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
                f"{_first_name(draft.full_name)}, your enrollment details are saved. "
                "Our team will confirm an available course date with you."
            )
        return (
            f"{_first_name(draft.full_name)}, your enrollment is already confirmed. "
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
                    "Your SkillsFuture and PayNow amounts must total S$600. Please "
                    "provide the corrected amounts."
                )
        elif method == "paynow":
            if skillsfuture != 0 or paynow != self.catalogue.course_fee:
                return (
                    "For PayNow payment, the SkillsFuture amount must be S$0 and the "
                    "PayNow amount must be S$600."
                )
        elif method == "utap":
            if skillsfuture != 0:
                return "SkillsFuture Credits and UTAP cannot be combined for this course."
            if paynow != self.catalogue.course_fee:
                return (
                    "UTAP is a reimbursement after course completion, so the S$600 "
                    "course fee must first be paid upfront."
                )
        return None

    def _paynow_question(self, draft):
        if draft and draft.payment_method == "utap":
            return (
                "UTAP is claimed after course completion, so the S$600 fee must be "
                "paid upfront. How much will you pay by PayNow?"
            )
        return (
            "How much will you pay by PayNow? Your SkillsFuture and PayNow amounts "
            "should total S$600."
        )


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
