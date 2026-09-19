"""Staff finance API; public participants use scoped conversation routes in app."""

from functools import wraps
from io import BytesIO

from flask import Blueprint, Response, jsonify, request, send_file, session
from sqlalchemy.exc import IntegrityError

from backend.extensions import db
from backend.models import EnrollmentDraft
from backend.models.finance import CreditNoteRequest, PaymentEvidence, PaymentReview


def create_finance_blueprint(
    finance_service, staff_required, master_invoice_service=None
):
    blueprint = Blueprint("finance", __name__)
    finance = finance_service

    def action(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                result = function(*args, **kwargs)
                db.session.commit()
                return result
            except LookupError as error:
                db.session.rollback()
                return jsonify(error={"code": "NOT_FOUND", "message": str(error)}), 404
            except (ValueError, IntegrityError) as error:
                db.session.rollback()
                message = str(error) if isinstance(error, ValueError) else "This financial action conflicts with a previously recorded action"
                return jsonify(error={"code": "FINANCE_VALIDATION", "message": message}), 400
        return wrapped

    def draft(enrollment_id):
        result = db.session.get(EnrollmentDraft, enrollment_id)
        if result is None:
            raise LookupError("Enrollment not found")
        return result

    def payload():
        result = request.get_json(silent=True)
        if not isinstance(result, dict):
            raise ValueError("A JSON object is required")
        return result

    def actor():
        return session.get("staff_username", "staff")

    accountant = staff_required(roles=("accountant", "admin"))

    @blueprint.get("/api/staff/enrollments")
    @staff_required
    @action
    def list_enrollments():
        finance.sync_delivery_status()
        return jsonify(enrollments=finance.list_enrollments(request.args.get("status")))

    @blueprint.get("/api/staff/enrollments/<enrollment_id>")
    @staff_required
    @action
    def enrollment_detail(enrollment_id):
        finance.sync_delivery_status()
        return jsonify(finance.serialize_enrollment(draft(enrollment_id)))

    @blueprint.get("/api/staff/dashboard")
    @staff_required
    @action
    def dashboard():
        finance.sync_delivery_status()
        return jsonify(finance.dashboard())

    @blueprint.post("/api/staff/enrollments/<enrollment_id>/invoice")
    @staff_required
    @action
    def invoice(enrollment_id):
        participant = draft(enrollment_id)
        if finance._invoice(participant):
            document = finance.regenerate_invoice(participant, actor())
        else:
            finance.create_invoice(participant)
            document = finance._latest_document(participant, "invoice")
        return jsonify(document=finance.serialize_document(document), enrollment=finance.serialize_enrollment(participant))

    @blueprint.post("/api/staff/enrollments/<enrollment_id>/documents/resend")
    @staff_required
    @action
    def resend(enrollment_id):
        participant = draft(enrollment_id)
        outbound = finance.resend_document(participant, payload().get("kind"))
        return jsonify(queued=outbound is not None, delivery_id=outbound.id if outbound else None, enrollment=finance.serialize_enrollment(participant))

    @blueprint.post("/api/staff/enrollments/<enrollment_id>/receipt")
    @accountant
    @action
    def receipt(enrollment_id):
        participant = draft(enrollment_id)
        document = finance.issue_receipt(participant)
        return jsonify(document=finance.serialize_document(document), enrollment=finance.serialize_enrollment(participant))

    @blueprint.get("/api/staff/payment-reviews")
    @accountant
    @action
    def reviews():
        query = db.select(PaymentReview).order_by(PaymentReview.created_at.desc())
        status = request.args.get("status")
        if status:
            query = query.where(PaymentReview.status == status)
        return jsonify(reviews=[finance.serialize_review(row) for row in db.session.execute(query).scalars()])

    @blueprint.post("/api/staff/payment-reviews/<review_id>/decision")
    @accountant
    @action
    def decide_review(review_id):
        data = payload()
        review = finance.decide_payment_review(review_id, data.get("decision"), actor(), data.get("note"), reference=data.get("reference"), amount=data.get("amount"), transaction_date=data.get("transaction_date"))
        return jsonify(review=finance.serialize_review(review), enrollment=finance.serialize_enrollment(draft(review.enrollment_id)))

    @blueprint.post("/api/staff/enrollments/<enrollment_id>/skillsfuture/confirm")
    @accountant
    @action
    def skillsfuture_confirm(enrollment_id):
        data, participant = payload(), draft(enrollment_id)
        payment = finance.confirm_skillsfuture(participant, data.get("reference"), data.get("transaction_date"), actor(), data.get("note"))
        return jsonify(payment_id=payment.id, enrollment=finance.serialize_enrollment(participant))

    @blueprint.get("/api/staff/credit-notes")
    @accountant
    @action
    def credit_notes():
        query = db.select(CreditNoteRequest).order_by(CreditNoteRequest.created_at.desc())
        if request.args.get("status"):
            query = query.where(CreditNoteRequest.status == request.args["status"])
        return jsonify(credit_notes=[finance.serialize_credit_note(row) for row in db.session.execute(query).scalars()])

    @blueprint.post("/api/staff/enrollments/<enrollment_id>/credit-notes")
    @staff_required
    @action
    def request_credit(enrollment_id):
        participant = draft(enrollment_id)
        record = finance.request_credit_note(participant, payload().get("reason"), actor())
        return jsonify(credit_note=finance.serialize_credit_note(record), enrollment=finance.serialize_enrollment(participant))

    @blueprint.post("/api/staff/credit-notes/<request_id>/decision")
    @accountant
    @action
    def decide_credit(request_id):
        data = payload()
        record = finance.decide_credit_note(request_id, data.get("decision"), actor(), data.get("note"))
        return jsonify(credit_note=finance.serialize_credit_note(record), enrollment=finance.serialize_enrollment(draft(record.enrollment_id)))

    @blueprint.get("/api/staff/documents/<document_id>")
    @staff_required
    @action
    def document_download(document_id):
        document = finance.get_document(document_id)
        response = send_file(BytesIO(finance.document_bytes(document)), mimetype="application/pdf", as_attachment=True, download_name=document.filename)
        response.headers["Cache-Control"] = "no-store"
        return response

    @blueprint.get("/api/staff/evidence/<evidence_id>")
    @accountant
    @action
    def evidence_download(evidence_id):
        evidence = db.session.get(PaymentEvidence, evidence_id)
        if not evidence:
            raise LookupError("Payment evidence not found")
        response = send_file(BytesIO(finance.storage.read(evidence.storage_key)), mimetype=evidence.mime_type, as_attachment=True, download_name=f"payment-evidence-{evidence.id}")
        response.headers["Cache-Control"] = "no-store"
        return response

    @blueprint.get("/api/staff/reports/payments.csv")
    @accountant
    @action
    def report():
        return Response(finance.payment_report_csv(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=payment-status.csv", "Cache-Control": "no-store"})

    @blueprint.post("/api/staff/reports/payments/send")
    @accountant
    @action
    def send_report():
        outbound = finance.queue_nightly_report()
        return jsonify(queued=outbound is not None, delivery_id=outbound.id if outbound else None)

    if master_invoice_service is not None:
        @blueprint.get("/api/staff/master-invoice/status")
        @accountant
        @action
        def master_invoice_status():
            return jsonify(master_invoice=master_invoice_service.status())

        @blueprint.get("/api/staff/master-invoice/download")
        @accountant
        @action
        def master_invoice_download():
            workbook = master_invoice_service.download(actor())
            response = send_file(
                workbook,
                mimetype=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                as_attachment=True,
                download_name="Master_Invoice_List.xlsx",
            )
            response.headers["Cache-Control"] = "no-store"
            return response

        @blueprint.post("/api/staff/master-invoice/regenerate")
        @accountant
        @action
        def master_invoice_regenerate():
            return jsonify(
                master_invoice=master_invoice_service.regenerate(actor())
            )

        @blueprint.post("/api/staff/master-invoice/retry")
        @accountant
        @action
        def master_invoice_retry():
            master_invoice_service.retry_failed(actor())
            return jsonify(master_invoice=master_invoice_service.status())

    return blueprint
