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
      className="px-5 animate-[fade-in_0.2s_ease-out_backwards]"
      style={{ animationDelay: `${Math.min(index * 0.03, 0.15)}s` }}
    >
      <div
        className={`flex flex-col mb-3 ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        {!isUser && (
          <span className="mb-1 ml-1 text-[11px] font-medium text-text-dim">
            LaughLoop
          </span>
        )}
        <div
          className={`max-w-3/4 px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
            isUser
              ? "rounded-lg bg-foreground text-surface"
              : "rounded-lg border border-border-custom bg-surface"
          }`}
        >
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
