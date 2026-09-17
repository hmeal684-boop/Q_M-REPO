"""Integrated portal, finance-document and inbound-queue coverage."""

from decimal import Decimal

from werkzeug.security import generate_password_hash

from backend.app import create_app
from backend.extensions import db
from backend.models import EnrollmentDraft


PASSWORD = "safe-test-password"


def register(client, email):
    return client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Participant",
            "email": email,
            "password": PASSWORD,
        },
    )


def csrf_post(client, path, token, **kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    headers["X-CSRF-Token"] = token
    return client.post(path, headers=headers, **kwargs)


def portal_app(tmp_path, fake_ai):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "portal-integration-test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'portal.db').as_posix()}",
            "STORAGE_DIR": str(tmp_path / "private"),
            "AUTOMATION_API_TOKEN": "synthetic-automation-token",
            "STAFF_ACCOUNTS": {
                "accountant": {
                    "password_hash": generate_password_hash("staff-password"),
                    "role": "accountant",
                }
            },
        },
        ai_service=fake_ai,
    )


def staff_login(client):
    response = client.post(
        "/api/staff/login",
        json={"username": "accountant", "password": "staff-password"},
    )
    assert response.status_code == 200
    return response.get_json()["csrf_token"]


def test_invoice_document_delivery_is_owned_and_staff_portal_is_protected(tmp_path, fake_ai):
    app = portal_app(tmp_path, fake_ai)
    owner = app.test_client()
    other = app.test_client()
    owner_auth = register(owner, "invoice-owner@example.com").get_json()
    other_auth = register(other, "invoice-other@example.com").get_json()
    created = csrf_post(owner, "/api/conversations", owner_auth["csrf_token"])
    conversation_id = created.get_json()["conversation_id"]

    with app.app_context():
        draft = EnrollmentDraft(
            conversation_id=conversation_id,
            course="2-Day Basic Certificate in Dental Assisting",
            full_name="Test Student",
            nric="S1234567D",
            email="invoice-owner@example.com",
            mobile_number="91234567",
            payment_method="paynow",
            skillsfuture_amount=Decimal("0"),
            paynow_amount=Decimal("600"),
            status="confirmed",
        )
        db.session.add(draft)
        db.session.commit()
        enrollment_id = draft.id

    assert owner.get(f"/api/conversations/{conversation_id}/status").status_code == 200
    assert other.get(f"/api/conversations/{conversation_id}/status").status_code == 404
    assert app.test_client().get("/api/staff/dashboard").status_code == 401

    staff = app.test_client()
    staff_csrf = staff_login(staff)
    invoice = csrf_post(
        staff,
        f"/api/staff/enrollments/{enrollment_id}/invoice",
        staff_csrf,
    )
    assert invoice.status_code == 200
    document_id = invoice.get_json()["document"]["id"]
    assert staff.get("/api/staff/dashboard").status_code == 200

    owner_download = owner.get(
        f"/api/conversations/{conversation_id}/documents/{document_id}"
    )
    assert owner_download.status_code == 200
    assert owner_download.data.startswith(b"%PDF")
    assert other.get(
        f"/api/conversations/{conversation_id}/documents/{document_id}"
    ).status_code == 404
    assert other_auth["user"]["email"] == "invoice-other@example.com"


def test_inbound_integration_is_authenticated_and_queues_only(tmp_path, fake_ai):
    app = portal_app(tmp_path, fake_ai)
    client = app.test_client()
    payload = {
        "id": "synthetic-inbound-1",
        "from": "synthetic.sender@example.com",
        "body": "What is the course fee?",
    }
    assert client.post("/api/development/inbound", json=payload).status_code == 403
    accepted = client.post(
        "/api/development/inbound",
        json=payload,
        headers={"Authorization": "Bearer synthetic-automation-token"},
    )
    assert accepted.status_code == 202
    assert accepted.get_json()["duplicate"] is False
    duplicate = client.post(
        "/api/development/inbound",
        json=payload,
        headers={"Authorization": "Bearer synthetic-automation-token"},
    )
    assert duplicate.status_code == 202
    assert duplicate.get_json()["duplicate"] is True
