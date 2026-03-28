"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Header } from "@/components/header";
import { StatsBar } from "@/components/stats-bar";
import { ChatMessage, type Message } from "@/components/chat-message";
import { ChatInput } from "@/components/chat-input";
import { EmptyState } from "@/components/empty-state";
import { TypingIndicator } from "@/components/typing-indicator";
import { LogViewer } from "@/components/log-viewer";
import { PipelinePanel } from "@/components/pipeline-panel";
import { sendChat, fetchStats as apiFetchStats, type Stats } from "@/lib/api";

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
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

  const triggerRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

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
      triggerRefresh();
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
    setTimeout(() => {
      refreshStats();
      triggerRefresh();
    }, 500);
  };

  const handleNewChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <Header onNewChat={handleNewChat} />

      <div className="flex min-h-0 flex-1">
        {/* Left: Chat Panel */}
        <div className="flex w-1/2 flex-col border-r border-border-custom">
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

        {/* Right: Log Viewer + Pipeline */}
        <div className="flex w-1/2 flex-col">
          {/* Top-right: Log Viewer */}
          <div className="flex-1 overflow-hidden border-b border-border-custom">
            <LogViewer refreshKey={refreshKey} />
          </div>

          {/* Bottom-right: Training Pipeline */}
          <div className="flex-1 overflow-hidden">
            <PipelinePanel refreshKey={refreshKey} />
          </div>
        </div>
      </div>
    </div>
  );
}
