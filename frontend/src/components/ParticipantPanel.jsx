import { useEffect, useRef, useState } from "react";
import { documentUrl, getConversationStatus, uploadEvidence } from "../services/chatApi.js";

const money = (amount) => new Intl.NumberFormat("en-SG", { style: "currency", currency: "SGD" }).format(Number(amount || 0));

export default function ParticipantPanel({ conversationId, revision, onUpdated }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const [paymentType, setPaymentType] = useState("paynow");
  const fileInput = useRef(null);

  useEffect(() => {
    let cancelled = false;
    if (!conversationId) return;
    setLoading(true);
    setError("");
    getConversationStatus(conversationId).then((result) => { if (!cancelled) setStatus(result); }).catch((requestError) => { if (!cancelled) setError(requestError.message); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [conversationId, revision]);

  async function handleUpload(event) {
    event.preventDefault();
    if (!file) { setError("Select a payment screenshot to upload."); return; }
    if (file.size > 10 * 1024 * 1024) { setError("The screenshot must be smaller than 10 MB."); return; }
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await uploadEvidence(conversationId, file, paymentType);
      setNotice(result.message || "Your payment screenshot has been submitted. Your enrollment status will update after verification.");
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      onUpdated();
    } catch (requestError) { setError(requestError.message); } finally { setLoading(false); }
  }

  const finance = status?.finance;
  const invoice = finance?.invoice || finance?.invoices?.[0];
  const documents = finance?.documents || [];
  const hasEnrollment = Boolean(finance?.id || finance?.enrollment_id || invoice);
  const enrollmentStatus = finance?.status || status?.enrollment?.status;
  return <aside className="participant-panel" aria-labelledby="enrollment-panel-title" aria-busy={loading}>
    <span className="eyebrow">Your course journey</span>
    <h2 id="enrollment-panel-title">Enrollment &amp; payment</h2>
    <p className="muted">Invoices, payment updates, and receipts for this conversation.</p>
    {error && <p className="notice-error" role="alert">{error} <button type="button" className="text-button" onClick={onUpdated}>Retry</button></p>}
    {notice && <p className="notice-success" role="status">{notice}</p>}
    {loading && !status && <p role="status">Loading your enrollment…</p>}
    {enrollmentStatus ? <><span className="status-badge">{String(enrollmentStatus).replaceAll("_", " ")}</span>{status?.enrollment?.missing_fields?.length > 0 && <p className="muted">The assistant will help you complete: {status.enrollment.missing_fields.join(", ").replaceAll("_", " ")}.</p>}</> : !loading && <div className="empty-state"><p>You have no enrollment yet.</p><p className="muted">Select “Enroll now” in the chat to get started.</p></div>}
    {invoice && <dl className="detail-list"><div><dt>Invoice</dt><dd>{invoice.number || invoice.invoice_number}</dd></div><div><dt>Course fee</dt><dd>{money(invoice.course_fee)}</dd></div><div><dt>SkillsFuture credits</dt><dd>{money(invoice.skillsfuture_amount)}</dd></div><div><dt>PayNow balance</dt><dd>{money(invoice.net_payable)}</dd></div>{invoice.due_date && <div><dt>Due date</dt><dd>{invoice.due_date.slice(0, 10)}</dd></div>}</dl>}
    {documents.length > 0 && <section className="panel-section"><h3>Your documents</h3><div className="document-links">{documents.map((document) => <a key={document.id} href={documentUrl(document.id, conversationId)} target="_blank" rel="noreferrer">{String(document.kind || document.type || "document").replaceAll("_", " ")} <span>{document.number || "Open PDF"} ↗</span></a>)}</div></section>}
    {hasEnrollment && <section className="panel-section"><h3>Submit payment evidence</h3><p className="muted small-copy">Upload a clear screenshot showing the amount, recipient, date, and transaction reference.</p><form onSubmit={handleUpload} className="stack-form"><label>Payment type<select value={paymentType} onChange={(event) => setPaymentType(event.target.value)}><option value="paynow">PayNow payment</option><option value="skillsfuture">SkillsFuture claim</option></select></label><label>Payment screenshot<input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label><button type="submit" className="primary-button" disabled={loading}>{loading ? "Submitting…" : "Submit screenshot"}</button></form></section>}
    <p className="muted small-copy">Your invoice and receipt are also delivered to your email address on record.</p>
  </aside>;
}
