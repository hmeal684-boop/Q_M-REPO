"""Flask REST API for the Q&M CrewAI enquiry and enrollment prototype."""

from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from sqlalchemy.exc import SQLAlchemyError

from backend.agents.schemas import AIConfigurationError, AIServiceError
from backend.config import Config
from backend.extensions import db
from backend.models import communications, finance, operations, quality  # noqa: F401
from backend.finance_api import create_finance_blueprint
from backend.integrations_api import register_integrations
from backend.operations_api import create_operations_blueprint
from backend.quality_api import register_quality
from backend.services.chat_service import ChatService, serialize_enrollment, serialize_message
from backend.services.conversation_repository import ConversationRepository
from backend.services.course_catalogue import CourseCatalogue
from backend.services.crewai_service import CrewAIService
from backend.services.database_migrations import apply_additive_migrations
from backend.services.delivery_service import DeliveryService
from backend.services.finance_service import FinanceService
from backend.services.operations_service import OperationsService
from backend.services.security import (
    EncryptedStorage,
    current_participant_id,
    initialize_crypto,
    participant_required,
    register_participant_auth,
    register_staff_auth,
    staff_required,
)


def create_app(test_config=None, ai_service=None, catalogue=None):
    """Create the REST API; tests may inject a model-free agent substitute."""
    app = Flask(
        __name__,
        static_folder=None,
        instance_path=str(Path(__file__).resolve().parent / "data"),
    )
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if app.config.get("PRODUCTION") and app.config["SECRET_KEY"] == "development-only-change-me":
        raise RuntimeError("A private FLASK_SECRET_KEY is required in production.")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    initialize_crypto(app)
    db.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)
    register_participant_auth(app)
    register_staff_auth(app)
    register_quality(app)

    repository = ConversationRepository()
    catalogue = catalogue or CourseCatalogue()
    app.extensions["agent_service"] = ai_service
    app.extensions["catalogue"] = catalogue
    app.extensions["repository"] = repository
    delivery = DeliveryService()
    finance_service = FinanceService(catalogue, delivery, EncryptedStorage())
    operations_service = OperationsService(
        catalogue,
        delivery,
        followup_hours=app.config["FOLLOWUP_HOURS"],
        finance_service=finance_service,
    )
    app.extensions.update(
        delivery=delivery,
        finance=finance_service,
        operations=operations_service,
    )

    with app.app_context():
        db.create_all()
        apply_additive_migrations()

    app.register_blueprint(
        create_operations_blueprint(operations_service, staff_required)
    )
    app.register_blueprint(create_finance_blueprint(finance_service, staff_required))

    def current_ai_service():
        service = app.extensions.get("agent_service")
        if service is None:
            service = CrewAIService(
                api_key=app.config["OPENAI_API_KEY"],
                model=app.config["OPENAI_MODEL"],
            )
            app.extensions["agent_service"] = service
        return service

    @app.post("/api/conversations")
    @participant_required
    def create_conversation():
        conversation = repository.create(user_id=current_participant_id())
        operations_service.lead_for(conversation.id)
        db.session.commit()
        return (
            jsonify(
                {
                    "conversation_id": conversation.id,
                    "status": conversation.status,
                    "created_at": _iso_timestamp(conversation.created_at),
                }
            ),
            201,
        )

    @app.get("/api/conversations/<conversation_id>/messages")
    @participant_required
    def conversation_messages(conversation_id):
        conversation = repository.get_for_user(
            conversation_id, current_participant_id()
        )
        if conversation is None:
            return _error_response(
                "CONVERSATION_NOT_FOUND", "Conversation was not found.", 404
            )
        return jsonify(
            {
                "conversation_id": conversation.id,
                "messages": [
                    serialize_message(message)
                    for message in repository.all_messages(conversation)
                ],
                "active_intent": conversation.active_intent,
                "enrollment": serialize_enrollment(
                    conversation.enrollment_draft, catalogue
                ),
            }
        )

    @app.post("/api/chat")
    @participant_required
    def chat():
        validation_error = _validate_chat_request(request)
        if validation_error:
            return validation_error

        payload = request.get_json()
        conversation = repository.get_for_user(
            payload["conversation_id"], current_participant_id()
        )
        if conversation is None:
            return _error_response(
                "CONVERSATION_NOT_FOUND", "Conversation was not found.", 404
            )

        try:
            service = ChatService(
                repository=repository,
                catalogue=catalogue,
                ai_service=current_ai_service(),
                context_limit=app.config["CONVERSATION_CONTEXT_MESSAGE_LIMIT"],
            )
            return jsonify(service.respond(conversation, payload["message"].strip()))
        except AIConfigurationError:
            db.session.rollback()
            return _error_response(
                "AI_CONFIGURATION_ERROR",
                "The assistant is temporarily unavailable. Please try again later.",
                503,
            )
        except AIServiceError:
            db.session.rollback()
            return _error_response(
                "AI_SERVICE_ERROR",
                "The assistant is temporarily unavailable. Please try again.",
                502,
            )
        except SQLAlchemyError:
            db.session.rollback()
            return _error_response(
                "DATABASE_ERROR",
                "The conversation could not be saved. Please try again.",
                500,
            )

    def consent_state(conversation_id):
        consent = operations_service.consent_for(conversation_id)
        return {
            "accepted": bool(consent and consent.granted),
            "version": app.config["CONSENT_VERSION"],
        }

    @app.post("/api/conversations/<conversation_id>/consent")
    @participant_required
    def participant_consent(conversation_id):
        conversation = repository.get_for_user(
            conversation_id, current_participant_id()
        )
        if conversation is None:
            return _error_response("NOT_FOUND", "Conversation was not found.", 404)
        payload = request.get_json(silent=True) or {}
        if type(payload.get("accepted")) is not bool:
            return _error_response(
                "INVALID_CONSENT", "Consent must be true or false.", 400
            )
        operations_service.set_consent(
            conversation_id,
            payload["accepted"],
            version=app.config["CONSENT_VERSION"],
        )
        db.session.commit()
        return jsonify(consent_state(conversation_id))

    @app.get("/api/conversations/<conversation_id>/status")
    @participant_required
    def participant_status(conversation_id):
        conversation = repository.get_for_user(
            conversation_id, current_participant_id()
        )
        if conversation is None:
            return _error_response("NOT_FOUND", "Conversation was not found.", 404)
        draft = conversation.enrollment_draft
        return jsonify(
            conversation_id=conversation_id,
            consent=consent_state(conversation_id),
            enrollment=serialize_enrollment(draft, catalogue),
            finance=(
                finance_service.serialize_case(finance_service.get_case(draft))
                if draft
                else None
            ),
        )

    @app.post("/api/conversations/<conversation_id>/evidence")
    @participant_required
    def participant_evidence(conversation_id):
        conversation = repository.get_for_user(
            conversation_id, current_participant_id()
        )
        if conversation is None or conversation.enrollment_draft is None:
            return _error_response("NOT_FOUND", "Enrollment was not found.", 404)
        upload = request.files.get("file")
        if upload is None:
            return _error_response(
                "INVALID_UPLOAD", "Attach a payment screenshot.", 400
            )
        try:
            result = finance_service.submit_payment(
                conversation.enrollment_draft,
                upload.read(),
                upload.mimetype,
                channel="web",
                payment_type=request.form.get("payment_type", "paynow"),
            )
            db.session.commit()
            return jsonify(result), 201
        except ValueError as error:
            db.session.rollback()
            return _error_response("INVALID_EVIDENCE", str(error), 400)

    @app.get(
        "/api/conversations/<conversation_id>/documents/<document_id>"
    )
    @participant_required
    def participant_document(conversation_id, document_id):
        document = db.session.get(finance.FinancialDocument, document_id)
        conversation = repository.get_for_user(
            conversation_id, current_participant_id()
        )
        if (
            not document
            or not conversation
            or not conversation.enrollment_draft
            or document.enrollment_id != conversation.enrollment_draft.id
        ):
            return _error_response("NOT_FOUND", "Document was not found.", 404)
        response = send_file(
            BytesIO(EncryptedStorage().read(document.storage_key)),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=document.filename,
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    register_integrations(
        app, repository, catalogue, current_ai_service, consent_state
    )

    @app.get("/health")
    def health():
        return jsonify(
            {
                "service": "q-and-m-training-chatbot",
                "stage": "course-enquiry-enrollment-assistant",
                "status": "ok",
                "ai_configuration": {
                    "api_key_configured": bool(app.config["OPENAI_API_KEY"]),
                    "model_configured": bool(app.config["OPENAI_MODEL"]),
                },
            }
        )

    return app


def _validate_chat_request(incoming_request):
    if not incoming_request.is_json:
        return _error_response(
            "INVALID_CONTENT_TYPE", "Request body must be JSON.", 415
        )
    payload = incoming_request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error_response(
            "INVALID_JSON", "Request body must contain a valid JSON object.", 400
        )
    message = payload.get("message")
    if not isinstance(message, str):
        return _error_response("INVALID_MESSAGE", "Message must be a text value.", 400)
    if not message.strip():
        return _error_response("EMPTY_MESSAGE", "Message cannot be empty.", 400)
    conversation_id = payload.get("conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        return _error_response(
            "INVALID_CONVERSATION_ID",
            "A conversation_id text value is required.",
            400,
        )
    return None


def _error_response(code, message, status_code):
    return jsonify({"error": {"code": code, "message": message}}), status_code


def _iso_timestamp(value):
    if value.tzinfo is None:
        from datetime import timezone

        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


app = create_app()


if __name__ == "__main__":
    app.run(port=app.config["PORT"])
