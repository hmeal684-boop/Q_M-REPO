const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000";
const apiBaseUrl = configuredBaseUrl.replace(/\/$/, "");

export async function createConversation() {
  return requestJson("/api/conversations", { method: "POST" });
}

export async function getConversationMessages(conversationId) {
  return requestJson(`/api/conversations/${encodeURIComponent(conversationId)}/messages`);
}

export async function sendChatMessage(message, conversationId) {
  return requestJson("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}

async function requestJson(path, options = {}) {
  let response;

  try {
    response = await fetch(`${apiBaseUrl}${path}`, options);
  } catch {
    throw new Error("We’re unable to connect right now. Please try again shortly.");
  }

  const payload = await readJson(response);

  if (!response.ok) {
    throw new Error(payload?.error?.message || "We couldn’t send your message. Please try again.");
  }

  return payload;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}
