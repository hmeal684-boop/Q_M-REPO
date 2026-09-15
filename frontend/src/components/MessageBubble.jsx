function formatTime(timestamp) {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return "Now";
  }

  return new Intl.DateTimeFormat([], {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default function MessageBubble({ message }) {
  const isBot = message.sender === "bot";

  return (
    <div className={`message-row message-row--${message.sender}`}>
      {isBot && <div className="assistant-avatar" aria-hidden="true">🦷</div>}
      <article className={`message-bubble message-bubble--${message.sender}`}>
        {isBot && <span className="message-sender">Q&amp;M Assistant</span>}
        <p>{message.text}</p>
        <time className="message-time" dateTime={message.timestamp}>
          {formatTime(message.timestamp)}
        </time>
      </article>
    </div>
  );
}
