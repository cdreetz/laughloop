"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Header } from "@/components/header";
import { StatsBar } from "@/components/stats-bar";
import { ChatMessage, type Message } from "@/components/chat-message";
import { ChatInput } from "@/components/chat-input";
import { EmptyState } from "@/components/empty-state";
import { TypingIndicator } from "@/components/typing-indicator";
import { sendChat, fetchStats as apiFetchStats, type Stats } from "@/lib/api";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshStats = useCallback(async () => {
    try {
      const data = await apiFetchStats();
      setStats(data);
    } catch {
      // Stats fetch is non-critical
    }
  }, []);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const data = await apiFetchStats();
        if (active) setStats(data);
      } catch {
        // Stats fetch is non-critical
      }
    };
    load();
    const interval = setInterval(load, 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const data = await sendChat(text, sessionId);
      if (!sessionId) setSessionId(data.session_id);

      const aiMsg: Message = {
        role: "assistant",
        content: data.response,
        id: data.id,
      };
      setMessages((prev) => [...prev, aiMsg]);
      refreshStats();
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Is this thing on? (Connection error \u2014 check if the backend is running on :8000)",
          id: null,
        },
      ]);
    }
    setLoading(false);
  };

  const handleFeedback = () => {
    setTimeout(refreshStats, 500);
  };

  const handleNewChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <Header onNewChat={handleNewChat} />
      <StatsBar stats={stats} />

      <div className="flex-1 overflow-y-auto py-4">
        {messages.length === 0 ? (
          <EmptyState onSelectPrompt={setInput} />
        ) : (
          <>
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                message={msg}
                index={i}
                onFeedback={handleFeedback}
              />
            ))}
          </>
        )}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      <ChatInput
        value={input}
        onChange={setInput}
        onSend={send}
        loading={loading}
      />
    </div>
  );
}
