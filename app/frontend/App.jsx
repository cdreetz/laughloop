import { useState, useRef, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:8000";

const COLORS = {
  bg: "#0a0a0f",
  surface: "#13131a",
  surfaceHover: "#1a1a24",
  border: "#2a2a3a",
  text: "#e8e8f0",
  textDim: "#7a7a8e",
  accent: "#f5c542",
  accentGlow: "rgba(245, 197, 66, 0.15)",
  funny: "#4ade80",
  funnyGlow: "rgba(74, 222, 128, 0.2)",
  notFunny: "#f87171",
  notFunnyGlow: "rgba(248, 113, 113, 0.15)",
  userBubble: "#1e1e2e",
  aiBubble: "#18182a",
};

function HahaButton({ interactionId, onFeedback }) {
  const [state, setState] = useState("idle"); // idle | funny | notFunny

  const handleFunny = async () => {
    setState("funny");
    onFeedback(interactionId, true);
    try {
      await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interaction_id: interactionId, funny: true }),
      });
    } catch (e) {
      console.error("Feedback failed:", e);
    }
  };

  const handleNotFunny = async () => {
    setState("notFunny");
    onFeedback(interactionId, false);
    try {
      await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interaction_id: interactionId, funny: false }),
      });
    } catch (e) {
      console.error("Feedback failed:", e);
    }
  };

  if (state === "funny") {
    return (
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "4px 12px", borderRadius: 20,
        background: COLORS.funnyGlow, border: `1px solid ${COLORS.funny}`,
        fontSize: 13, color: COLORS.funny, fontWeight: 600,
        animation: "popIn 0.3s ease-out",
      }}>
        😂 Haha!
      </div>
    );
  }
  if (state === "notFunny") {
    return (
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "4px 12px", borderRadius: 20,
        background: COLORS.notFunnyGlow, border: `1px solid ${COLORS.notFunny}`,
        fontSize: 13, color: COLORS.notFunny, fontWeight: 600,
      }}>
        😐 Noted
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
      <button
        onClick={handleFunny}
        style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          padding: "4px 14px", borderRadius: 20, cursor: "pointer",
          background: "transparent", border: `1px solid ${COLORS.border}`,
          color: COLORS.textDim, fontSize: 13, fontFamily: "inherit",
          transition: "all 0.2s ease",
        }}
        onMouseEnter={(e) => {
          e.target.style.borderColor = COLORS.funny;
          e.target.style.color = COLORS.funny;
          e.target.style.background = COLORS.funnyGlow;
        }}
        onMouseLeave={(e) => {
          e.target.style.borderColor = COLORS.border;
          e.target.style.color = COLORS.textDim;
          e.target.style.background = "transparent";
        }}
      >
        😂 Haha
      </button>
      <button
        onClick={handleNotFunny}
        style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          padding: "4px 14px", borderRadius: 20, cursor: "pointer",
          background: "transparent", border: `1px solid ${COLORS.border}`,
          color: COLORS.textDim, fontSize: 13, fontFamily: "inherit",
          transition: "all 0.2s ease",
        }}
        onMouseEnter={(e) => {
          e.target.style.borderColor = COLORS.notFunny;
          e.target.style.color = COLORS.notFunny;
          e.target.style.background = COLORS.notFunnyGlow;
        }}
        onMouseLeave={(e) => {
          e.target.style.borderColor = COLORS.border;
          e.target.style.color = COLORS.textDim;
          e.target.style.background = "transparent";
        }}
      >
        😐 Meh
      </button>
    </div>
  );
}

function StatsBar({ stats }) {
  if (!stats) return null;
  return (
    <div style={{
      display: "flex", gap: 16, padding: "8px 16px",
      borderBottom: `1px solid ${COLORS.border}`,
      fontSize: 12, color: COLORS.textDim, fontFamily: "'DM Mono', monospace",
      background: COLORS.surface, flexWrap: "wrap", alignItems: "center",
    }}>
      <span>
        📊 <strong style={{ color: COLORS.text }}>{stats.total_interactions}</strong> chats
      </span>
      <span>
        😂 <strong style={{ color: COLORS.funny }}>{stats.funny_count}</strong> laughs
      </span>
      <span>
        📈 Haha rate: <strong style={{
          color: stats.haha_rate > 0.5 ? COLORS.funny : COLORS.accent
        }}>{(stats.haha_rate * 100).toFixed(1)}%</strong>
      </span>
      <span style={{ marginLeft: "auto", opacity: 0.6 }}>
        🤖 {stats.current_adapter !== "(base model)" ? `adapter: ${stats.current_adapter.slice(0, 8)}...` : "base model"}
      </span>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div style={{
      display: "flex", gap: 4, padding: "12px 16px", alignItems: "center",
    }}>
      <div style={{
        display: "flex", gap: 4, padding: "10px 16px",
        background: COLORS.aiBubble, borderRadius: "16px 16px 16px 4px",
        border: `1px solid ${COLORS.border}`,
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 7, height: 7, borderRadius: "50%",
            background: COLORS.accent, opacity: 0.5,
            animation: `bounce 1.2s ease-in-out ${i * 0.15}s infinite`,
          }} />
        ))}
      </div>
    </div>
  );
}

export default function LaughLoop() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [stats, setStats] = useState(null);
  const bottomRef = useRef(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/stats`);
      if (res.ok) setStats(await res.json());
    } catch {}
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);

    const userMsg = { role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      const data = await res.json();
      if (!sessionId) setSessionId(data.session_id);

      const aiMsg = {
        role: "assistant",
        content: data.response,
        id: data.id,
      };
      setMessages(prev => [...prev, aiMsg]);
      fetchStats();
    } catch (e) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "🎤 *taps mic* Is this thing on? (Connection error — check if the backend is running on :8000)",
        id: null,
      }]);
    }
    setLoading(false);
  };

  const handleFeedback = () => {
    setTimeout(fetchStats, 500);
  };

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh",
      background: COLORS.bg, color: COLORS.text,
      fontFamily: "'Satoshi', 'DM Sans', system-ui, sans-serif",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;700&family=Playfair+Display:wght@700;900&display=swap');
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-6px); }
        }
        @keyframes popIn {
          0% { transform: scale(0.8); opacity: 0; }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes gradientShift {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${COLORS.border}; border-radius: 3px; }
        input:focus { outline: none; }
      `}</style>

      {/* Header */}
      <div style={{
        padding: "16px 20px", borderBottom: `1px solid ${COLORS.border}`,
        background: COLORS.surface, display: "flex", alignItems: "center", gap: 12,
      }}>
        <div style={{
          fontSize: 28, lineHeight: 1,
          animation: "bounce 2s ease-in-out infinite",
        }}>🎪</div>
        <div>
          <h1 style={{
            fontSize: 22, fontWeight: 900, margin: 0, lineHeight: 1.1,
            fontFamily: "'Playfair Display', serif",
            background: "linear-gradient(135deg, #f5c542, #ff6b6b, #f5c542)",
            backgroundSize: "200% 200%",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent",
            animation: "gradientShift 4s ease infinite",
          }}>
            LaughLoop
          </h1>
          <p style={{
            fontSize: 11, color: COLORS.textDim, marginTop: 2,
            fontFamily: "'DM Mono', monospace", letterSpacing: "0.05em",
          }}>
            CONTINUAL LEARNING COMEDY AI — GETS FUNNIER OVER TIME
          </p>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            onClick={() => {
              setMessages([]);
              setSessionId(null);
            }}
            style={{
              padding: "6px 14px", borderRadius: 8, cursor: "pointer",
              background: "transparent", border: `1px solid ${COLORS.border}`,
              color: COLORS.textDim, fontSize: 12, fontFamily: "'DM Mono', monospace",
              transition: "all 0.2s",
            }}
            onMouseEnter={e => {
              e.target.style.borderColor = COLORS.accent;
              e.target.style.color = COLORS.accent;
            }}
            onMouseLeave={e => {
              e.target.style.borderColor = COLORS.border;
              e.target.style.color = COLORS.textDim;
            }}
          >
            New Chat
          </button>
        </div>
      </div>

      <StatsBar stats={stats} />

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: "auto", padding: "16px 0",
      }}>
        {messages.length === 0 && (
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", height: "100%", gap: 16,
            padding: 40, textAlign: "center",
          }}>
            <div style={{ fontSize: 64 }}>🎭</div>
            <h2 style={{
              fontSize: 24, fontWeight: 700,
              fontFamily: "'Playfair Display', serif",
              color: COLORS.text,
            }}>
              Ready to laugh?
            </h2>
            <p style={{ color: COLORS.textDim, maxWidth: 360, lineHeight: 1.6, fontSize: 14 }}>
              Say anything. I'll try to make it funny.<br />
              Click <strong style={{ color: COLORS.funny }}>😂 Haha</strong> if I land the joke — it helps me learn!
            </p>
            <div style={{
              display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center",
              marginTop: 8,
            }}>
              {["Tell me a joke", "Explain quantum physics", "What's for dinner?", "Roast my code"].map(prompt => (
                <button
                  key={prompt}
                  onClick={() => { setInput(prompt); }}
                  style={{
                    padding: "8px 16px", borderRadius: 20, cursor: "pointer",
                    background: COLORS.surface, border: `1px solid ${COLORS.border}`,
                    color: COLORS.textDim, fontSize: 13, fontFamily: "inherit",
                    transition: "all 0.2s",
                  }}
                  onMouseEnter={e => {
                    e.target.style.borderColor = COLORS.accent;
                    e.target.style.color = COLORS.accent;
                    e.target.style.background = COLORS.accentGlow;
                  }}
                  onMouseLeave={e => {
                    e.target.style.borderColor = COLORS.border;
                    e.target.style.color = COLORS.textDim;
                    e.target.style.background = COLORS.surface;
                  }}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              padding: "4px 20px",
              animation: "slideUp 0.3s ease-out",
              animationFillMode: "backwards",
              animationDelay: `${Math.min(i * 0.05, 0.2)}s`,
            }}
          >
            <div style={{
              display: "flex",
              flexDirection: "column",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start",
              marginBottom: 8,
            }}>
              <div style={{
                maxWidth: "75%", padding: "12px 16px",
                borderRadius: msg.role === "user"
                  ? "16px 16px 4px 16px"
                  : "16px 16px 16px 4px",
                background: msg.role === "user" ? COLORS.userBubble : COLORS.aiBubble,
                border: `1px solid ${COLORS.border}`,
                fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap",
              }}>
                {msg.role === "assistant" && (
                  <span style={{ fontSize: 11, color: COLORS.accent, fontWeight: 600, display: "block", marginBottom: 4 }}>
                    🎪 LaughLoop
                  </span>
                )}
                {msg.content}
              </div>
              {msg.role === "assistant" && msg.id && (
                <div style={{ marginTop: 4, marginLeft: 4 }}>
                  <HahaButton interactionId={msg.id} onFeedback={handleFeedback} />
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: "12px 16px", borderTop: `1px solid ${COLORS.border}`,
        background: COLORS.surface,
      }}>
        <div style={{
          display: "flex", gap: 8, maxWidth: 720, margin: "0 auto",
        }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
            placeholder="Say something... I'll try to make it funny 🎤"
            style={{
              flex: 1, padding: "12px 16px", borderRadius: 12,
              background: COLORS.bg, border: `1px solid ${COLORS.border}`,
              color: COLORS.text, fontSize: 14, fontFamily: "inherit",
              transition: "border-color 0.2s",
            }}
            onFocus={e => e.target.style.borderColor = COLORS.accent}
            onBlur={e => e.target.style.borderColor = COLORS.border}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            style={{
              padding: "12px 20px", borderRadius: 12, cursor: "pointer",
              background: loading || !input.trim() ? COLORS.border : COLORS.accent,
              border: "none", color: COLORS.bg,
              fontSize: 14, fontWeight: 700, fontFamily: "inherit",
              transition: "all 0.2s",
              opacity: loading || !input.trim() ? 0.5 : 1,
            }}
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
        <p style={{
          textAlign: "center", fontSize: 11, color: COLORS.textDim,
          marginTop: 8, fontFamily: "'DM Mono', monospace",
        }}>
          Your feedback trains the model in real-time via reinforcement learning
        </p>
      </div>
    </div>
  );
}
