"""Static checks for preserving structured chatbot replies in the existing UI."""

from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_message_bubbles_preserve_paragraphs_bullets_and_line_breaks():
    component = (FRONTEND_ROOT / "components" / "MessageBubble.jsx").read_text(
        encoding="utf-8"
    )
    stylesheet = (FRONTEND_ROOT / "styles.css").read_text(encoding="utf-8")

    assert "{message.text}" in component
    assert ".message-bubble p" in stylesheet
    assert "white-space: pre-wrap" in stylesheet
