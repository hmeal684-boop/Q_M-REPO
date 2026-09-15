import { useEffect, useRef, useState } from "react";

export default function MessageInput({ onSend, isLoading, error }) {
  const [message, setMessage] = useState("");
  const [validationError, setValidationError] = useState("");
  const input = useRef(null);

  useEffect(() => {
    if (!isLoading) {
      input.current?.focus();
    }
  }, [isLoading]);

  function handleSubmit(event) {
    event.preventDefault();
    const trimmedMessage = message.trim();

    if (!trimmedMessage) {
      setValidationError("Please enter a message.");
      input.current?.focus();
      return;
    }

    setValidationError("");
    setMessage("");
    onSend(trimmedMessage);
  }

  const visibleError = validationError || error;

  return (
    <form className="composer" onSubmit={handleSubmit} noValidate>
      <label className="visually-hidden" htmlFor="message-input">
        Message
      </label>
      <input
        ref={input}
        id="message-input"
        name="message"
        type="text"
        value={message}
        placeholder="Type a message"
        autoComplete="off"
        aria-describedby="input-error"
        aria-invalid={Boolean(visibleError)}
        disabled={isLoading}
        onChange={(event) => {
          setMessage(event.target.value);
          setValidationError("");
        }}
      />
      <button type="submit" disabled={isLoading}>
        Send
      </button>
      <p className="input-error" id="input-error" role="alert" hidden={!visibleError}>
        {visibleError}
      </p>
    </form>
  );
}
