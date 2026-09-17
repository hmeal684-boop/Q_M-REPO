const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000";
export const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");
let csrfToken = "";

export function setCsrfToken(value) {
  csrfToken = value || "";
}

export function getAuthSession() {
  return requestJson("/api/auth/session");
}

export function registerParticipant(fullName, email, password) {
  return postJson("/api/auth/register", { full_name: fullName, email, password });
}

export function loginParticipant(email, password) {
  return postJson("/api/auth/login", { email, password });
}

export function logoutParticipant() {
  return postJson("/api/auth/logout", {});
}

export async function createConversation() {
  return requestJson("/api/conversations", { method: "POST" });
}

export async function getConversationMessages(conversationId) {
  return requestJson(`/api/conversations/${encodeURIComponent(conversationId)}/messages`);
}

export async function sendChatMessage(message, conversationId) {
  return requestJson("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}

export function getConversationStatus(conversationId) {
  return requestJson(`/api/conversations/${encodeURIComponent(conversationId)}/status`);
}

export function uploadEvidence(conversationId, file, paymentType) {
  const body = new FormData();
  body.append("file", file);
  body.append("payment_type", paymentType);
  return requestJson(`/api/conversations/${encodeURIComponent(conversationId)}/evidence`, {
    method: "POST",
    body,
  });
}

export function documentUrl(documentId, conversationId = "") {
  const path = conversationId
    ? `/api/conversations/${encodeURIComponent(conversationId)}/documents/${encodeURIComponent(documentId)}`
    : `/api/staff/documents/${encodeURIComponent(documentId)}`;
  return `${apiBaseUrl}${path}`;
}

export function postJson(path, payload, method = "POST") {
  return requestJson(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function requestJson(path, options = {}) {
  let response;
  const headers = new Headers(options.headers || {});
  if (csrfToken && !["GET", "HEAD", "OPTIONS"].includes(options.method || "GET")) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { ...options, credentials: "include", headers });
  } catch {
    throw new Error("We’re unable to connect right now. Please try again shortly.");
  }
  const payload = await readJson(response);
  if (!response.ok) {
    const error = new Error(payload?.error?.message || "We couldn’t send your message. Please try again.");
    error.status = response.status;
    error.code = payload?.error?.code;
    throw error;
  }
  return payload;
}

async function readJson(response) {
  try { return await response.json(); }
  catch { return {}; }
}
