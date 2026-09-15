"""Flask REST API for the Q&M CrewAI enquiry and enrollment prototype."""

from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy.exc import SQLAlchemyError

from backend.agents.schemas import AIConfigurationError, AIServiceError
from backend.config import Config
from backend.extensions import db
from backend.services.chat_service import ChatService, serialize_enrollment, serialize_message
from backend.services.conversation_repository import ConversationRepository
from backend.services.course_catalogue import CourseCatalogue
from backend.services.crewai_service import CrewAIService
from backend.services.database_migrations import apply_additive_migrations


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

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    CORS(app, origins=app.config["CORS_ORIGINS"])

    repository = ConversationRepository()
    catalogue = catalogue or CourseCatalogue()
    app.extensions["agent_service"] = ai_service

    with app.app_context():
        db.create_all()
        apply_additive_migrations()

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
    def create_conversation():
        conversation = repository.create()
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
    def conversation_messages(conversation_id):
        conversation = repository.get(conversation_id)
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
    def chat():
        validation_error = _validate_chat_request(request)
        if validation_error:
            return validation_error

        payload = request.get_json()
        conversation = repository.get(payload["conversation_id"])
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
