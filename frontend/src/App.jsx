import { useEffect, useRef, useState } from "react";

import ChatHeader from "./components/ChatHeader.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import MessageInput from "./components/MessageInput.jsx";
import {
  createConversation,
  getConversationMessages,
  sendChatMessage,
} from "./services/chatApi.js";

const STORAGE_KEY = "qm-training-conversation-id";
const welcomeMessage = {
  id: "welcome-message",
  sender: "bot",
  text: (
    "Hi there! 👋 I’m the Q&M Training Assistant. I can answer questions about " +
    "our 2-Day Basic Certificate in Dental Assisting or guide you through " +
    "enrollment. How can I help you today?"
  ),
  timestamp: new Date().toISOString(),
};

const quickActions = [
  { label: "About the course", message: "Tell me about the course" },
  { label: "Course fee", message: "How much is the course fee?" },
  { label: "Available dates", message: "What course dates are available?" },
  { label: "Enroll now", message: "I’d like to enroll" },
];

function makeMessage(sender, text, timestamp = new Date().toISOString(), id) {
  return {
    id: id || `${sender}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    sender,
    text,
    timestamp,
  };
}

function mapStoredMessages(messages) {
  if (!messages.length) {
    return [welcomeMessage];
  }
  return messages.map((message) =>
    makeMessage(
      message.role === "assistant" ? "bot" : "user",
      message.content,
      message.timestamp,
      message.id,
    ),
  );
}

function maskNricForDisplay(text) {
  return text.replace(/\b([STFGM])\d{7}([A-Z])\b/gi, "$1*******$2");
}

export default function App() {
  const [messages, setMessages] = useState([welcomeMessage]);
  const [conversationId, setConversationId] = useState("");
  const [isEnrollmentStarted, setIsEnrollmentStarted] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const initializationStarted = useRef(false);

  useEffect(() => {
    if (initializationStarted.current) return;
    initializationStarted.current = true;

    async function initializeConversation() {
      const savedId = localStorage.getItem(STORAGE_KEY);
      try {
        if (savedId) {
          const history = await getConversationMessages(savedId);
          setConversationId(savedId);
          setMessages(mapStoredMessages(history.messages));
          setIsEnrollmentStarted(Boolean(history.enrollment?.status));
          return;
        }
        await startNewConversation();
      } catch (requestError) {
        localStorage.removeItem(STORAGE_KEY);
        try {
          await startNewConversation();
        } catch (createError) {
          setError(createError.message || requestError.message);
        }
      } finally {
        setIsLoading(false);
      }
    }

    initializeConversation();
  }, []);

  async function startNewConversation() {
    setError("");
    setIsLoading(true);
    try {
      const result = await createConversation();
      localStorage.setItem(STORAGE_KEY, result.conversation_id);
      setConversationId(result.conversation_id);
      setMessages([{ ...welcomeMessage, timestamp: new Date().toISOString() }]);
      setIsEnrollmentStarted(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSend(message) {
    if (!conversationId) {
      setError("A chat could not be started. Please select New Chat and try again.");
      return;
    }

    setError("");
    setMessages((current) => [
      ...current,
      makeMessage("user", maskNricForDisplay(message)),
    ]);
    setIsLoading(true);

    try {
      const response = await sendChatMessage(message, conversationId);
      const reply = response.message;
      setMessages((current) => [
        ...current,
        makeMessage("bot", reply.content, reply.timestamp, reply.id),
      ]);
      setIsEnrollmentStarted(Boolean(response.enrollment?.status));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="chat-shell" aria-labelledby="chat-title">
      <ChatHeader onNewChat={startNewConversation} disabled={isLoading} />
      <ChatWindow
        messages={messages}
        isLoading={isLoading}
        quickActions={isEnrollmentStarted ? [] : quickActions}
        onQuickAction={handleSend}
      />
      <MessageInput onSend={handleSend} isLoading={isLoading} error={error} />
    </main>
  );
}
