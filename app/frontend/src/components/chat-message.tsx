"use client";

import { HahaButton } from "./haha-button";

export interface Message {
  role: "user" | "assistant";
  content: string;
  id?: string | null;
}

interface ChatMessageProps {
  message: Message;
  index: number;
  onFeedback: () => void;
}

export function ChatMessage({ message, index, onFeedback }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div
      className="px-5 animate-[slide-up_0.3s_ease-out_backwards]"
      style={{ animationDelay: `${Math.min(index * 0.05, 0.2)}s` }}
    >
      <div
        className={`flex flex-col mb-2 ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        <div
          className={`max-w-3/4 px-4 py-3 border border-border-custom text-sm leading-relaxed whitespace-pre-wrap ${
            isUser
              ? "rounded-2xl rounded-br-sm bg-user-bubble"
              : "rounded-2xl rounded-bl-sm bg-ai-bubble"
          }`}
        >
          {!isUser && (
            <span className="mb-1 block text-xs font-semibold text-accent">
              LaughLoop
            </span>
          )}
          {message.content}
        </div>
        {!isUser && message.id && (
          <div className="mt-1 ml-1">
            <HahaButton interactionId={message.id} onFeedback={onFeedback} />
          </div>
        )}
      </div>
    </div>
  );
}
