import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  listThreads,
  createThread,
  getMessages,
  postMessage,
  deleteThread,
  setTakeover,
  postHumanReply,
  sendAudio,
  type Thread,
  type Message,
} from "../api";
import { useLeadScore, getOverrideLevel, setOverrideLevel, type LeadLevel } from "../hooks/useLeadScore";
import { computeLeadScoreFromMessages, levelFromScore } from "../utils/leadScore";
import type { UIMessage } from "../types/lead";
import { INITIAL_FUNNELS } from "../data/funnels";
import { INITIAL_AUDIOS } from "../data/audios";
import type { AutomationAction, FunnelStage } from "../types/funnel";

/** Utils */
function clsx(...xs: Array<string | false | undefined>) {
  return xs.filter(Boolean).join(" ");
}
function formatTime(dt: string | number | Date) {
  const d = new Date(dt);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function formatTimeShort(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString();
}

/** SSE helper (mantido caso volte ao SSE depois) */
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
function sseUrlForThread(threadId: number | string) {
  const token = localStorage.getItem("token") || "";
  return `${API_BASE}/threads/${threadId}/stream?token=${encodeURIComponent(token)}`;
}

/* ==== Lead Tagging ====================================================== */

function colorForLevel(level: LeadLevel) {
  switch (level) {
    case "frio": return { bg: "#0f172a", fg: "#93c5fd", bd: "#1d4ed8" };
    case "morno": return { bg: "#1f2937", fg: "#fde68a", bd: "#f59e0b" };
    case "quente": return { bg: "#2d0f12", fg: "#fecaca", bd: "#dc2626" };
    default: return { bg: "var(--panel)", fg: "var(--muted)", bd: "var(--border)" };
  }
}

function LeadTag({ level, score }: { level: LeadLevel; score?: number }) {
  const { bg, fg, bd } = colorForLevel(level);
  const label =
    level === "quente" ? "Quente" :
    level === "morno" ? "Morno" :
    level === "frio" ? "Frio" : "—";
  const title = typeof score === "number" ? `${label} (${score})` : label;
  return (
    <span
      className="chip"
      title={title}
      style={{
        background: bg,
        color: fg,
        border: `1px solid ${bd}`,
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: 12,
        lineHeight: "16px",
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      <span aria-hidden style={{ width: 8, height: 8, borderRadius: 999, background: bd }} />
      {label}
    </span>
  );
}

/* ======================================================================= */

/** Sidebar de threads */
function Sidebar({
  threads,
  activeId,
  onSelect,
  onNew,
  onDelete,
  loading,
  leadFilter,
  setLeadFilter,
  leadScores,
  isMobile,
  onClose,
}: {
  threads: Thread[];
  activeId?: string;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  loading: boolean;
  leadFilter: LeadLevel | "todos";
  setLeadFilter: (l: LeadLevel | "todos") => void;
  leadScores: Record<string, { score?: number; level: LeadLevel }>;
  isMobile?: boolean;
  onClose?: () => void;
}) {
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    let list = threads;
    if (s) {
      // Busca tanto no nome do contato quanto no título e última mensagem
      list = list.filter((t) => {
        const searchText = (t.contact_name || t.title || "Sem título").toLowerCase();
        const lastMsg = (t.last_message || "").toLowerCase();
        return searchText.includes(s) || lastMsg.includes(s);
      });
    }
    if (leadFilter !== "todos") {
      list = list.filter((t) => (leadScores[String(t.id)]?.level ?? "desconhecido") === leadFilter);
    }
    
    // Ordena por última mensagem (mais recente primeiro) - estilo WhatsApp
    return [...list].sort((a, b) => {
      const timeA = a.last_message_at ? new Date(a.last_message_at).getTime() : (a.created_at ? new Date(a.created_at).getTime() : 0);
      const timeB = b.last_message_at ? new Date(b.last_message_at).getTime() : (b.created_at ? new Date(b.created_at).getTime() : 0);
      return timeB - timeA; // Mais recente primeiro (descendente)
    });
  }, [q, threads, leadFilter, leadScores]);

  return (
    <aside
      style={{
        width: "100%",
        height: "100%",
        maxWidth: "100%",
        maxHeight: "100%",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        background: "var(--panel)",
        boxSizing: "border-box",
      }}
      aria-label="Lista de conversas"
    >
      {/* Header da sidebar */}
      <div style={{ 
        padding: "16px", 
        borderBottom: "1px solid var(--border)", 
        background: "var(--panel)",
        flexShrink: 0,
      }}>
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "space-between", 
          gap: 12,
          marginBottom: 12 
        }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, flex: 1, minWidth: 0 }}>Conversas</h2>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {isMobile && onClose && (
              <button
                onClick={onClose}
                style={{
                  padding: "8px",
                  background: "transparent",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  cursor: "pointer",
                  fontSize: 18,
                  color: "var(--text)",
                  display: "flex",
                  alignItems: "center",
                }}
                aria-label="Fechar lista de conversas"
              >
                ✕
              </button>
            )}
            <button 
              className="btn" 
              onClick={onNew} 
              style={{ 
                padding: "8px 14px",
                borderRadius: 8,
                background: "var(--primary-color)",
                color: "white",
                border: "none",
                cursor: "pointer",
                fontWeight: 600,
                fontSize: 14,
                whiteSpace: "nowrap",
                flexShrink: 0,
              }} 
              aria-label="Criar nova conversa"
            >
              + Nova
            </button>
          </div>
        </div>

        {/* Filtros de temperatura */}
        <div style={{ 
          display: "flex", 
          gap: 6,
          marginBottom: 12,
        }} role="tablist" aria-label="Filtros de temperatura">
          <button
            className={clsx("btn", leadFilter === "todos" ? "" : "soft")}
            onClick={() => setLeadFilter("todos")}
            title="Mostrar todas"
            style={{ flex: 1, padding: "6px 8px", fontSize: 13 }}
            aria-pressed={leadFilter === "todos"}
            aria-label="Mostrar todas as conversas"
          >
            Todos
          </button>
          <button
            className={clsx("btn", leadFilter === "frio" ? "" : "soft")}
            onClick={() => setLeadFilter("frio")}
            title="Somente Frios"
            style={{ flex: 1, padding: "6px 8px", fontSize: 16 }}
            aria-pressed={leadFilter === "frio"}
            aria-label="Filtrar conversas frias"
          >
            ❄️
          </button>
          <button
            className={clsx("btn", leadFilter === "morno" ? "" : "soft")}
            onClick={() => setLeadFilter("morno")}
            title="Somente Mornos"
            style={{ flex: 1, padding: "6px 8px", fontSize: 16 }}
            aria-pressed={leadFilter === "morno"}
            aria-label="Filtrar conversas mornas"
          >
            🌤️
          </button>
          <button
            className={clsx("btn", leadFilter === "quente" ? "" : "soft")}
            onClick={() => setLeadFilter("quente")}
            title="Somente Quentes"
            style={{ flex: 1, padding: "6px 8px", fontSize: 16 }}
            aria-pressed={leadFilter === "quente"}
            aria-label="Filtrar conversas quentes"
          >
            🔥
          </button>
        </div>

        {/* Busca */}
        <input
          className="input"
          placeholder="Buscar ou começar nova conversa"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Buscar conversa"
          type="search"
          style={{
            width: "100%",
            padding: "10px 16px",
            borderRadius: 20,
            border: "1px solid var(--border)",
            background: "var(--bg)",
            fontSize: 14,
            boxSizing: "border-box",
          }}
        />
      </div>

      <div style={{ 
        overflowY: "auto", 
        overflowX: "hidden",
        flex: 1, 
        minHeight: 0,
        maxHeight: "100%",
        boxSizing: "border-box",
      }} role="list" aria-label="Lista de conversas">
        {loading && (
          <div className="small" style={{ color: "var(--muted)", padding: "16px" }} role="status" aria-live="polite">
            Carregando conversas...
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="small" style={{ color: "var(--muted)", padding: "16px" }} role="status">
            Nenhuma conversa encontrada.
          </div>
        )}

        <ul style={{ 
          listStyle: "none", 
          padding: 0, 
          margin: 0, 
          display: "flex", 
          flexDirection: "column",
        }}>
          {filtered.map((t) => {
            const entry = leadScores[String(t.id)] || { level: "desconhecido" as LeadLevel, score: undefined };
            // Prioriza o nome do contato, depois o título, depois "Sem título"
            const displayName = t.contact_name || t.title || "Sem título";
            const lastMsg = t.last_message || "";
            const lastMsgTime = t.last_message_at ? formatTimeShort(t.last_message_at) : "";
            const isActive = activeId === String(t.id);
            return (
              <li key={t.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <button
                  className={clsx("item", isActive && "active")}
                  onClick={() => onSelect(String(t.id))}
                  aria-current={isActive ? "page" : undefined}
                  aria-label={`Conversa com ${displayName}${lastMsg ? `, última mensagem: ${lastMsg}` : ""}`}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    display: "flex",
                    flexDirection: "column",
                    padding: "12px 16px",
                    minHeight: "72px",
                    height: "auto",
                    boxSizing: "border-box",
                    position: "relative",
                    cursor: "pointer",
                    background: isActive ? "var(--bg)" : "transparent",
                    border: "none",
                    gap: 6,
                    transition: "background 0.2s ease",
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.background = "var(--bg)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.background = "transparent";
                  }}
                  title={lastMsg ? `${displayName}\n${lastMsg}` : displayName}
                >
                  {/* Linha superior: Nome + Timestamp + Tag */}
                  <div style={{ 
                    display: "flex", 
                    alignItems: "flex-start", 
                    justifyContent: "space-between", 
                    gap: 8, 
                    width: "100%",
                    marginBottom: 2,
                  }}>
                    <span
                      style={{
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        pointerEvents: "none",
                        fontWeight: 500,
                        fontSize: 15,
                        color: "var(--text)",
                        flex: 1,
                        minWidth: 0,
                        lineHeight: "1.3",
                      }}
                    >
                      {displayName}
                    </span>
                    <div style={{ 
                      display: "flex", 
                      alignItems: "center", 
                      gap: 8, 
                      flexShrink: 0,
                      flexWrap: "wrap",
                    }}>
                      {/* Tag de Suporte/Human Takeover */}
                      {t.human_takeover && (
                        <div style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 3,
                          padding: "2px 8px",
                          borderRadius: 10,
                          fontSize: 9,
                          fontWeight: 700,
                          background: "#dc2626",
                          color: "#ffffff",
                          textTransform: "uppercase",
                          letterSpacing: 0.3,
                          boxShadow: "0 2px 6px rgba(220, 38, 38, 0.4)",
                        }}>
                          🚨
                        </div>
                      )}
                      {lastMsgTime && (
                        <span
                          style={{
                            fontSize: 12,
                            color: "var(--muted)",
                            whiteSpace: "nowrap",
                            pointerEvents: "none",
                            lineHeight: "1.2",
                          }}
                        >
                          {lastMsgTime}
                        </span>
                      )}
                      <LeadTag level={entry.level} score={entry.score} />
                    </div>
                  </div>
                  
                  {/* Linha inferior: Preview da mensagem (limitado a 2 linhas) */}
                  {lastMsg && (
                    <div style={{ 
                      display: "flex", 
                      alignItems: "flex-start", 
                      width: "100%",
                      minHeight: 0,
                      marginTop: 2,
                    }}>
                      <span
                        style={{
                          fontSize: 14,
                          color: "var(--muted)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          lineHeight: "1.5",
                          flex: 1,
                          pointerEvents: "none",
                          wordBreak: "break-word",
                          maxWidth: "100%",
                        }}
                        title={lastMsg}
                      >
                        {lastMsg}
                      </span>
                    </div>
                  )}
                  
                  {!lastMsg && (
                    <div style={{ 
                      fontSize: 14,
                      color: "var(--muted)",
                      fontStyle: "italic",
                      marginTop: 2,
                      pointerEvents: "none",
                      lineHeight: "1.5",
                    }}>
                      Sem mensagens
                    </div>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}

/** Bolha de mensagem */
function Bubble({ m, isMobile, thread }: { m: UIMessage; isMobile?: boolean; thread?: Thread }) {
  const isUser = m.role === "user";
  const assistantLabel = (m as any).is_human ? "Assistente (Humano)" : "Assistente";
  
  // Para mensagens do usuário, tenta pegar o nome do contato
  let userLabel = "Usuário";
  if (isUser && thread) {
    const name = thread.contact_name || 
                 thread.title || 
                 (thread.metadata as any)?.name ||
                 (thread.metadata as any)?.profile_name;
    
    if (name && name.trim()) {
      userLabel = name.trim();
    } else {
      // Fallback: mostra número de telefone
      const phone = (thread.metadata as any)?.wa_id || 
                   (thread.metadata as any)?.phone || 
                   thread.external_user_phone;
      if (phone) {
        const phoneStr = String(phone).replace(/[^\d]/g, "");
        userLabel = phoneStr.length > 4 ? `+${phoneStr}` : phoneStr;
      }
    }
  }
  
  return (
    <div
      className={clsx("bubble", isUser ? "user" : "assistant")}
      aria-label={isUser ? "Mensagem do usuário" : "Resposta do assistente"}
      style={{
        maxWidth: isMobile ? "85%" : "min(720px, 100%)",
        padding: isMobile ? "8px 10px" : "10px 12px",
      }}
    >
      <div className="meta" style={{ 
        fontSize: isMobile ? 11 : 12,
        marginBottom: isMobile ? 4 : 6,
        gap: isMobile ? 6 : 10,
      }}>
        <span className="role">{isUser ? userLabel : assistantLabel}</span>
        <span className="time">{formatTime(m.created_at || Date.now())}</span>
      </div>
      <div className="content" style={{ 
        fontSize: isMobile ? 14 : 14,
        lineHeight: isMobile ? 1.4 : 1.5,
      }}>{m.content}</div>
    </div>
  );
}

/** Indicador de digitando */
function Typing() {
  return (
    <div className="typing">
      <span className="dot" />
      <span className="dot" />
      <span className="dot" />
    </div>
  );
}

/** Componente de lista de áudios */
function AudioList({ 
  audios, 
  threadId, 
  onSendAudio, 
  isMobile 
}: { 
  audios: typeof INITIAL_AUDIOS; 
  threadId?: string; 
  onSendAudio: (audioId: string, audioName: string) => Promise<void>;
  isMobile?: boolean;
}) {
  const [sendingMap, setSendingMap] = useState<Record<number, boolean>>({});
  
  // Mapeia code_name para IDs conhecidos do backend
  const audioIdMap: Record<string, string> = {
    "life_funil_longo_01_boas_vindas_e_qualificacao_inicial": "audio1_boas_vindas",
    "life_funil_longo_02_dor_generica": "audio2_dor_generica",
    "life_funil_longo_03_explicacao_planos": "audio3_explicacao_planos",
    "life_funil_longo_04_recuperacao_pos_nao_compra": "audio4_pos_compra",
    "life_mini_funil_bf_01_oferta_black_friday": "audio_bf_oferta",
    "life_mini_funil_bf_02_followup_sem_resposta": "audio_bf_follow1",
    "life_recuperacao_50_02_audio_followup": "audio_carrinho_abandonado",
    "life_recuperacao_50_03_audio_ultimo_chamado": "audio_bf_follow3",
  };
  
  const handleSend = async (audio: typeof INITIAL_AUDIOS[0]) => {
    if (!threadId || sendingMap[audio.id]) return;
    
    setSendingMap((prev) => ({ ...prev, [audio.id]: true }));
    
    try {
      const audioId = audioIdMap[audio.code_name] || audio.code_name;
      await onSendAudio(audioId, audio.display_name);
    } finally {
      setSendingMap((prev) => ({ ...prev, [audio.id]: false }));
    }
  };
  
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {audios.map((audio) => {
        const sending = sendingMap[audio.id] || false;
        
        return (
          <div
            key={audio.id}
            className="card"
            style={{
              padding: isMobile ? 10 : 12,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>
                {audio.display_name}
              </div>
              {audio.description && (
                <div style={{ fontSize: 11, color: "var(--muted)", lineHeight: 1.4 }}>
                  {audio.description.length > 60 
                    ? audio.description.substring(0, 60) + "..." 
                    : audio.description}
                </div>
              )}
            </div>
            <button
              onClick={() => handleSend(audio)}
              disabled={sending || !threadId}
              className="btn"
              style={{
                padding: isMobile ? "6px 12px" : "8px 16px",
                fontSize: isMobile ? 11 : 12,
                fontWeight: 600,
                borderRadius: 6,
                background: sending ? "var(--muted)" : "var(--primary-color)",
                color: "white",
                border: "none",
                cursor: sending || !threadId ? "not-allowed" : "pointer",
                opacity: sending || !threadId ? 0.6 : 1,
                whiteSpace: "nowrap",
                flexShrink: 0,
              }}
            >
              {sending ? "Enviando..." : "Enviar"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

/** Composer */
function Composer({
  value,
  setValue,
  onSend,
  disabled,
  takeoverActive,
  thread,
  automationActive,
}: {
  value: string;
  setValue: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
  takeoverActive: boolean;
  thread?: Thread;
  automationActive?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = Math.min(220, Math.max(48, el.scrollHeight)) + "px";
  }, [value]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSend();
    }
  }

  const isDisabled = disabled || !takeoverActive;
  const hasAutomation = automationActive || (thread as any)?.automation_active || (thread as any)?.funnel_id;
  const isAutomationOnlyMode = hasAutomation && !takeoverActive; // IA só responde por gatilhos

  return (
    <div style={{ 
      padding: isMobile ? "8px 10px" : "12px 16px", 
      borderTop: "1px solid var(--border)", 
      background: "var(--panel)",
      flexShrink: 0,
      width: "100%",
      maxWidth: "100%",
      boxSizing: "border-box",
      opacity: takeoverActive ? 1 : 0.6,
    }}>
      {/* Aviso quando em automação e takeover não ativo */}
      {isAutomationOnlyMode && (
        <div style={{
          padding: "8px 12px",
          marginBottom: 8,
          background: "#7c3aed15",
          border: "1px solid #7c3aed",
          borderRadius: 8,
          fontSize: isMobile ? 12 : 13,
          color: "#a78bfa",
          textAlign: "center",
        }}>
          Este contato está em automação. O assistente só responde por gatilhos configurados.
        </div>
      )}

      {/* Aviso quando takeover ativo */}
      {takeoverActive && hasAutomation && (
        <div style={{
          padding: "8px 12px",
          marginBottom: 8,
          background: "#1e3a8a15",
          border: "1px solid #1e3a8a",
          borderRadius: 8,
          fontSize: isMobile ? 12 : 13,
          color: "#93c5fd",
          textAlign: "center",
        }}>
          Você está assumindo. A automação é pausada enquanto você responde.
        </div>
      )}

      {!takeoverActive && !isAutomationOnlyMode && (
        <div style={{
          padding: "8px 12px",
          marginBottom: 8,
          background: "var(--bg)",
          border: "1px solid var(--border)",
          borderRadius: 8,
          fontSize: isMobile ? 12 : 13,
          color: "var(--muted)",
          textAlign: "center",
        }}>
          Ative "Assumir conversa" acima para enviar mensagens
        </div>
      )}
      <div className="composer" style={{ 
        display: "flex", 
        gap: isMobile ? 6 : 8, 
        alignItems: "flex-end",
        width: "100%",
        maxWidth: "100%",
        boxSizing: "border-box",
      }}>
        <textarea
          ref={ref}
          className="input"
          placeholder={takeoverActive ? "Você está respondendo como HUMANO..." : "Ative 'Assumir conversa' para enviar mensagens"}
          value={value}
          onChange={(e) => {
            if (takeoverActive) {
              setValue(e.target.value);
            }
          }}
          onKeyDown={handleKeyDown}
          rows={1}
          aria-label="Caixa de mensagem"
          disabled={isDisabled}
          style={{
            flex: 1,
            minWidth: 0,
            maxWidth: "100%",
            borderRadius: isMobile ? 18 : 20,
            padding: isMobile ? "8px 12px" : "10px 16px",
            border: "1px solid var(--border)",
            background: isDisabled ? "var(--panel)" : "var(--bg)",
            resize: "none",
            fontSize: isMobile ? 14 : 14,
            maxHeight: isMobile ? 100 : 120,
            overflowY: "auto",
            minHeight: isMobile ? 36 : 40,
            boxSizing: "border-box",
            cursor: isDisabled ? "not-allowed" : "text",
            opacity: isDisabled ? 0.6 : 1,
          }}
        />
        <button 
          className="btn" 
          onClick={onSend} 
          disabled={isDisabled || !value.trim()}
          style={{
            padding: isMobile ? "8px 16px" : "10px 20px",
            borderRadius: isMobile ? 18 : 20,
            background: isDisabled || !value.trim() ? "var(--muted)" : "var(--primary-color)",
            color: "white",
            border: "none",
            cursor: isDisabled || !value.trim() ? "not-allowed" : "pointer",
            fontWeight: 600,
            fontSize: isMobile ? 13 : 14,
            minWidth: isMobile ? 70 : 80,
            maxWidth: isMobile ? 70 : "none",
            height: isMobile ? 36 : "auto",
            flexShrink: 0,
            boxSizing: "border-box",
            opacity: isDisabled ? 0.5 : 1,
          }}
        >
          Enviar
        </button>
      </div>
      {!isMobile && takeoverActive && (
        <div className="small" style={{ color: "var(--muted)", marginTop: 6, fontSize: 11 }}>
          Enter para enviar • Shift + Enter para nova linha
        </div>
      )}
    </div>
  );
}

/** Página principal do Chat (sem Header interno) */
export default function Chat() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeId, setActiveId] = useState<string | undefined>(undefined);

  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [loadingThreads, setLoadingThreads] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [input, setInput] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // estados de tempo real (mantidos caso você use SSE depois)
  const [isTyping, setIsTyping] = useState(false);
  const [assistantBuffer, setAssistantBuffer] = useState<string>("");

  // takeover (estado local; persistido no backend ao alternar)
  const [takeoverActive, setTakeoverActive] = useState<boolean>(false);
  
  // Automação
  const [showAutomationModal, setShowAutomationModal] = useState<boolean>(false);
  const [automationActive, setAutomationActive] = useState<boolean>(false); // TODO: buscar do backend
  const [automationActions, setAutomationActions] = useState<AutomationAction[]>([]); // TODO: buscar do backend

  // Lead Tagging (tempo real)
  const [leadFilter, setLeadFilter] = useState<LeadLevel | "todos">("todos");
  const [leadScores, setLeadScores] = useState<Record<string, { score?: number; level: LeadLevel }>>({});

  const listRef = useRef<HTMLDivElement | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<number | null>(null);

  async function refreshLeadForThread(t: Thread, msgsCache?: UIMessage[]) {
    const override = getOverrideLevel(String(t.id));
    if (override && override !== "desconhecido") {
      const score = override === "quente" ? 75 : override === "morno" ? 45 : 15;
      setLeadScores((m) => ({
        ...m,
        [String(t.id)]: { score, level: override },
      }));
      return;
    }

    const beScore = t.lead_score;
    const beLevel = t.lead_level;
    const leadStage = (t as any).lead_stage; // "frio", "aquecimento", "aquecido", "quente"

    let msgs = msgsCache;
    if (!msgs && (!beScore || !beLevel)) {
      try {
        msgs = await getMessages(Number(t.id)) as UIMessage[];
      } catch {
        setLeadScores((m) => ({ ...m, [String(t.id)]: { score: undefined, level: "desconhecido" } }));
        return;
      }
    }

    // Usa o hook logic (mas não pode usar hook aqui, então usa as funções diretamente)
    const score = beScore ?? (msgs ? computeLeadScoreFromMessages(msgs) : 0);
    
    // Mapeia lead_stage para lead_level (temperatura)
    // lead_stage: "frio" | "aquecimento" | "aquecido" | "quente" | "pos_compra" | etc.
    // lead_level: "frio" | "morno" | "quente"
    let level: LeadLevel;
    if (leadStage) {
      if (leadStage === "quente" || leadStage === "pos_compra" || leadStage === "assinante") {
        level = "quente";
      } else if (leadStage === "aquecido" || leadStage === "fatura_pendente") {
        level = "morno";
      } else if (leadStage === "aquecimento") {
        level = "morno";
      } else {
        level = "frio"; // "frio" ou qualquer outro
      }
    } else {
      // Fallback: usa beLevel se disponível, senão calcula do score
      level = beLevel ? beLevel : levelFromScore(score);
    }
    
    setLeadScores((m) => ({ ...m, [String(t.id)]: { score, level } }));
  }

  /** Carrega threads e pontua todas em background */
  useEffect(() => {
    (async () => {
      try {
        setLoadingThreads(true);
        const ts = await listThreads();
        // Ordena por última mensagem (mais recente primeiro) - estilo WhatsApp
        const sorted = [...ts].sort((a, b) => {
          const timeA = a.last_message_at ? new Date(a.last_message_at).getTime() : (a.created_at ? new Date(a.created_at).getTime() : 0);
          const timeB = b.last_message_at ? new Date(b.last_message_at).getTime() : (b.created_at ? new Date(b.created_at).getTime() : 0);
          return timeB - timeA; // Mais recente primeiro
        });
        setThreads(sorted);
        if (sorted.length > 0) setActiveId(String(sorted[0].id));

        const CONC = 4;
        for (let i = 0; i < sorted.length; i += CONC) {
          await Promise.all(sorted.slice(i, i + CONC).map(t => refreshLeadForThread(t)));
        }
      } catch (e: any) {
        setErrorMsg(e?.message || "Falha ao carregar conversas.");
      } finally {
        setLoadingThreads(false);
      }
    })();
  }, []);

  /** Carrega mensagens ao trocar de thread + repontua a ativa */
  useEffect(() => {
    if (!activeId) return;
    (async () => {
      try {
        if (esRef.current) {
          esRef.current.close();
          esRef.current = null;
        }

        setLoadingMessages(true);
        setErrorMsg(null);
        const msgs = await getMessages(Number(activeId));
        setMessages(msgs as any);
        setTakeoverActive(false);
        setAssistantBuffer("");
        setIsTyping(false);

        const t = threads.find(x => String(x.id) === activeId);
        if (t) refreshLeadForThread(t, msgs as any);

        requestAnimationFrame(() => {
          listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
        });
      } catch (e: any) {
        setErrorMsg(e?.message || "Falha ao carregar mensagens.");
      } finally {
        setLoadingMessages(false);
      }
    })();
  }, [activeId]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Polling de mensagens da ativa a cada 2s (merge) */
  useEffect(() => {
    if (!activeId) return;

    if (pollRef.current) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }

    const fetchAndMerge = async () => {
      try {
        const serverMsgs = await getMessages(Number(activeId));
        let shouldClearTyping = false;
        
        setMessages((prev) => {
          const map = new Map(prev.map((m) => [String(m.id), m]));
          
          // Remove mensagens temporárias que já têm correspondente real
          const tempToRemove: string[] = [];
          for (const [id, msg] of map.entries()) {
            if (id.startsWith("temp-")) {
              // Verifica se já existe mensagem real com mesmo conteúdo e role
              const hasReal = serverMsgs.some((m: UIMessage) => 
                m.role === msg.role && 
                m.content.trim() === msg.content.trim() &&
                Math.abs(new Date(m.created_at).getTime() - new Date(msg.created_at).getTime()) < 5000
              );
              if (hasReal) {
                tempToRemove.push(id);
              }
            }
          }
          tempToRemove.forEach(id => map.delete(id));
          
          // Adiciona/atualiza mensagens do servidor
          for (const m of serverMsgs as UIMessage[]) {
            map.set(String(m.id), m);
          }
          
          // Verifica se a última mensagem do servidor é do assistente
          // e se é mais recente que a última mensagem do usuário
          if (serverMsgs.length > 0) {
            const lastMsg = serverMsgs[serverMsgs.length - 1];
            const lastUserMsg = [...serverMsgs].reverse().find((m: UIMessage) => m.role === "user");
            
            // Se a última mensagem é do assistente e é mais recente que a última do usuário,
            // significa que o assistente já respondeu
            if (lastMsg.role === "assistant") {
              if (!lastUserMsg || new Date(lastMsg.created_at) > new Date(lastUserMsg.created_at)) {
                shouldClearTyping = true;
              }
            }
          }
          
          return Array.from(map.values()).sort((a, b) => {
            const ai = String(a.id), bi = String(b.id);
            if (ai.startsWith("temp-") && !bi.startsWith("temp-")) return -1;
            if (!ai.startsWith("temp-") && bi.startsWith("temp-")) return 1;
            return Number(a.id) - Number(b.id);
          });
        });
        
        // Limpa isTyping se o assistente já respondeu
        if (shouldClearTyping) {
          setIsTyping(false);
          setAssistantBuffer("");
        }

        // repontua a ativa e atualiza thread (move para o topo se tiver nova mensagem)
        const t = threads.find(x => String(x.id) === activeId);
        if (t) {
          refreshLeadForThread(t, serverMsgs as any);
          // Atualiza a thread na lista para refletir nova mensagem
          if (serverMsgs && serverMsgs.length > 0) {
            const lastMsg = serverMsgs[serverMsgs.length - 1];
            setThreads((prev) => {
              const updated = prev.map((th) => 
                String(th.id) === activeId
                  ? { ...th, last_message: lastMsg.content, last_message_at: lastMsg.created_at }
                  : th
              );
              // Reordena: thread atualizada vai para o topo
              return updated.sort((a, b) => {
                const timeA = a.last_message_at ? new Date(a.last_message_at).getTime() : (a.created_at ? new Date(a.created_at).getTime() : 0);
                const timeB = b.last_message_at ? new Date(b.last_message_at).getTime() : (b.created_at ? new Date(b.created_at).getTime() : 0);
                return timeB - timeA;
              });
            });
          }
        }
      } catch {
        // silencioso
      }
    };

    fetchAndMerge();
    pollRef.current = window.setInterval(fetchAndMerge, 2000) as unknown as number;

    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [activeId, threads]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Polling leve para TODAS as threads a cada 15s (atualiza do backend primeiro) */
  useEffect(() => {
    if (!threads.length) return;
    const interval = window.setInterval(async () => {
      try {
        // Atualiza threads do backend primeiro para pegar beScore/beLevel atualizados
        const ts = await listThreads();
        // Ordena por última mensagem (mais recente primeiro) - estilo WhatsApp
        const sorted = [...ts].sort((a, b) => {
          const timeA = a.last_message_at ? new Date(a.last_message_at).getTime() : (a.created_at ? new Date(a.created_at).getTime() : 0);
          const timeB = b.last_message_at ? new Date(b.last_message_at).getTime() : (b.created_at ? new Date(b.created_at).getTime() : 0);
          return timeB - timeA; // Mais recente primeiro
        });
        setThreads(sorted);
        
        const CONC = 3;
        for (let i = 0; i < sorted.length; i += CONC) {
          await Promise.all(sorted.slice(i, i + CONC).map(t => refreshLeadForThread(t)));
        }
      } catch {
        // silencioso
      }
    }, 15000);
    return () => window.clearInterval(interval);
  }, [threads.length]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Scroll automático quando chegam novas mensagens */
  useEffect(() => {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
    });
  }, [messages.length, assistantBuffer]);

  async function handleNewThread() {
    try {
      const t = await createThread();
      setThreads((prev) => [t, ...prev]);
      setActiveId(String(t.id));
      setMessages([]);
      setInput("");
      setTakeoverActive(false);
      setAssistantBuffer("");
      setIsTyping(false);
      refreshLeadForThread(t); // já calcula
    } catch (e: any) {
      setErrorMsg(e?.message || "Não foi possível criar a conversa.");
    }
  }

  async function handleDeleteThread(id: string) {
    try {
      await deleteThread(Number(id));
      setThreads((prev) => prev.filter((t) => String(t.id) !== id));
      if (activeId === id) {
        const rest = threads.filter((t) => String(t.id) !== id);
        setActiveId(rest[0] ? String(rest[0].id) : undefined);
        setMessages([]);
        setTakeoverActive(false);
        setAssistantBuffer("");
        setIsTyping(false);
      }
    } catch (e: any) {
      setErrorMsg(e?.message || "Não foi possível excluir a conversa.");
    }
  }

  async function toggleTakeover(next: boolean) {
    if (!activeId) return;
    try {
      await setTakeover(Number(activeId), next);
      setTakeoverActive(next);
    } catch (e: any) {
      setErrorMsg(e?.message || "Falha ao alternar takeover.");
    }
  }

  async function handleSend() {
    if (!activeId) {
      await handleNewThread();
    }
    if (!activeId) return;
    const content = input.trim();
    if (!content) return;

    const optimistic: UIMessage = {
      id: "temp-" + Date.now(),
      role: takeoverActive ? "assistant" : "user",
      is_human: takeoverActive ? true : undefined,
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setInput("");
    setSending(true);
    if (!takeoverActive) setIsTyping(true);
    setErrorMsg(null);

    try {
      if (takeoverActive) {
        await postHumanReply(Number(activeId), content);
        setIsTyping(false);
      } else {
        await postMessage(Number(activeId), content);
        // isTyping será limpo quando a resposta do assistente chegar via polling
      }
    } catch (e: any) {
      setErrorMsg(e?.response?.data?.detail || e?.message || "Falha ao enviar. Tente novamente.");
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setInput(content);
      setIsTyping(false);
    } finally {
      setSending(false);
      const t = threads.find(x => String(x.id) === activeId);
      if (t) {
        refreshLeadForThread(t); // repontua depois do envio
        // Atualiza thread e move para o topo (estilo WhatsApp)
        setThreads((prev) => {
          const now = new Date().toISOString();
          const updated = prev.map((th) => 
            String(th.id) === activeId
              ? { ...th, last_message: content, last_message_at: now }
              : th
          );
          // Reordena: thread atualizada vai para o topo
          return updated.sort((a, b) => {
            const timeA = a.last_message_at ? new Date(a.last_message_at).getTime() : (a.created_at ? new Date(a.created_at).getTime() : 0);
            const timeB = b.last_message_at ? new Date(b.last_message_at).getTime() : (b.created_at ? new Date(b.created_at).getTime() : 0);
            return timeB - timeA;
          });
        });
      }
    }
  }

  const activeLead = useMemo(() => {
    if (!activeId) return { level: "desconhecido" as LeadLevel, score: undefined as number | undefined };
    const entry = leadScores[activeId];
    return entry || { level: "desconhecido" as LeadLevel, score: undefined };
  }, [activeId, leadScores]);

  function handleOverride(level: LeadLevel | null) {
    if (!activeId) return;
    if (level) {
      setOverrideLevel(activeId, level);
    } else {
      localStorage.removeItem(`lead_override_${activeId}`);
    }
    const t = threads.find(x => String(x.id) === activeId);
    if (t) refreshLeadForThread(t, messages); // aplica na hora
  }

  const [showSidebar, setShowSidebar] = useState(true); // Para mobile
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  // Detecta mudanças no tamanho da tela
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (!mobile) {
        setShowSidebar(true); // Sempre mostra sidebar no desktop
      }
    };
    window.addEventListener("resize", handleResize);
    handleResize(); // Chama uma vez no mount
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // No mobile, esconde sidebar quando chat está aberto
  useEffect(() => {
    if (activeId && isMobile) {
      setShowSidebar(false);
    }
  }, [activeId, isMobile]);

  return (
    <div
      style={{
        height: "calc(100vh - 56px)",
        width: "100vw",
        maxHeight: "calc(100vh - 56px)",
        maxWidth: "100vw",
        minHeight: 0,
        minWidth: 0,
        overflow: "hidden",
        background: "var(--bg)",
        color: "var(--text)",
        display: "flex",
        position: "fixed",
        top: 56,
        left: 0,
        right: 0,
        bottom: 0,
        boxSizing: "border-box",
      }}
    >
      {/* Sidebar - Lista de Conversas */}
      <div
        style={{
          width: activeId && isMobile && !showSidebar ? 0 : isMobile ? "100%" : 350,
          minWidth: activeId && isMobile && !showSidebar ? 0 : isMobile ? 0 : 350,
          maxWidth: activeId && isMobile && !showSidebar ? 0 : isMobile ? "100%" : 350,
          height: "100%",
          maxHeight: "100%",
          borderRight: isMobile ? "none" : "1px solid var(--border)",
          background: "var(--panel)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          transition: "all 0.3s ease",
          position: isMobile ? "absolute" : "relative",
          zIndex: isMobile ? 10 : 1,
          left: isMobile && !showSidebar ? "-100%" : 0,
          top: 0,
          boxShadow: isMobile && showSidebar ? "2px 0 8px rgba(0,0,0,0.1)" : "none",
          boxSizing: "border-box",
        }}
      >
        <Sidebar
          threads={threads}
          activeId={activeId}
          onSelect={(id) => {
            setActiveId(id);
            if (isMobile) setShowSidebar(false);
          }}
          onNew={handleNewThread}
          onDelete={handleDeleteThread}
          loading={loadingThreads}
          leadFilter={leadFilter}
          setLeadFilter={setLeadFilter}
          leadScores={leadScores}
          isMobile={isMobile}
          onClose={() => setShowSidebar(false)}
        />
      </div>

      {/* Área do Chat */}
      {activeId ? (
        <main
          style={{
            flex: 1,
            height: "100%",
            maxHeight: "100%",
            width: isMobile && showSidebar ? 0 : "100%",
            minHeight: 0,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            background: "var(--bg)",
            overflow: "hidden",
            boxSizing: "border-box",
          }}
          aria-label="Janela do chat"
        >
          {/* Header consolidado do Chat */}
          <div
            style={{
              borderBottom: "1px solid var(--border)",
              background: "var(--surface)",
              flexShrink: 0,
              boxSizing: "border-box",
              boxShadow: "var(--shadow-sm)",
              position: "relative",
              zIndex: 10,
            }}
          >
            {/* Linha superior: Nome do contato e controles principais */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: isMobile ? "12px 14px" : "14px 16px",
                gap: isMobile ? 8 : 12,
                flexWrap: "wrap",
              }}
            >
              {/* Esquerda: Botão voltar + Info do contato */}
              <div style={{ 
                flex: 1, 
                display: "flex", 
                alignItems: "center", 
                gap: isMobile ? 8 : 12,
                minWidth: 0,
                overflow: "hidden",
              }}>
                {/* Botão voltar/fechar */}
                <button
                  onClick={() => {
                    setActiveId(undefined);
                    if (isMobile) {
                      setShowSidebar(true);
                    }
                  }}
                  className="btn ghost"
                  style={{
                    padding: "8px",
                    minWidth: 36,
                    height: 36,
                    fontSize: 18,
                    flexShrink: 0,
                  }}
                  aria-label="Fechar chat e voltar para lista"
                  title="Fechar chat"
                >
                  {isMobile ? "←" : "✕"}
                </button>

                {/* Info do contato */}
                <div style={{ minWidth: 0, flex: 1, overflow: "hidden" }}>
                  <div style={{ 
                    fontWeight: 600, 
                    fontSize: isMobile ? 15 : 16,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 4,
                  }}>
                    <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {(() => {
                        const thread = threads.find(t => String(t.id) === activeId);
                        if (!thread) return "Nova conversa";
                        
                        const name = thread.contact_name || 
                                     thread.title || 
                                     (thread.metadata as any)?.name ||
                                     (thread.metadata as any)?.profile_name;
                        
                        if (name && name.trim()) return name.trim();
                        
                        const phone = (thread.metadata as any)?.wa_id || 
                                     (thread.metadata as any)?.phone || 
                                     thread.external_user_phone;
                        if (phone) {
                          const phoneStr = String(phone).replace(/[^\d]/g, "");
                          return `Contato • ${phoneStr.slice(-4)}`;
                        }
                        
                        return "Nova conversa";
                      })()}
                    </span>
                    {/* Tag de Suporte/Human Takeover */}
                    {(() => {
                      const thread = threads.find(t => String(t.id) === activeId);
                      if (thread?.human_takeover) {
                        return (
                          <div className="badge badge-danger" style={{ flexShrink: 0 }}>
                            Precisa Atenção
                          </div>
                        );
                      }
                      return null;
                    })()}
                  </div>
                  {!isMobile && (
                    <div style={{ 
                      fontSize: 12, 
                      color: "var(--text-muted)", 
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 6,
                      alignItems: "center",
                    }}>
                      {(() => {
                        const thread = threads.find(t => String(t.id) === activeId);
                        if (!thread) return null;
                        
                        const phone = (thread.metadata as any)?.wa_id || 
                                     (thread.metadata as any)?.phone || 
                                     thread.external_user_phone;
                        const phoneFormatted = phone 
                          ? String(phone).replace(/[^\d]/g, "").replace(/^(\d{2})(\d{2})(\d{4,5})(\d{4})$/, "+$1 ($2) $3-$4")
                          : null;
                        
                        const funnelId = (thread as any).funnel_id || (thread as any).metadata?.funnel_id;
                        const stageId = (thread as any).stage_id || (thread as any).metadata?.stage_id;
                        const source = (thread as any).source || (thread as any).metadata?.source;
                        const tags = (thread as any).tags || (thread as any).metadata?.tags || [];
                        
                        let stageName = null;
                        let funnelName = null;
                        if (funnelId && stageId) {
                          const funnel = INITIAL_FUNNELS.find(f => String(f.id) === String(funnelId));
                          if (funnel) {
                            funnelName = funnel.name;
                            const stage = funnel.stages.find(s => String(s.id) === String(stageId));
                            if (stage) {
                              stageName = stage.name;
                            }
                          }
                        }
                        
                        return (
                          <>
                            {phoneFormatted && <span style={{ whiteSpace: "nowrap" }}>{phoneFormatted}</span>}
                            {funnelName && <span style={{ whiteSpace: "nowrap" }}>{funnelName}</span>}
                            {stageName && <span style={{ whiteSpace: "nowrap" }}>{stageName}</span>}
                            {source && <span style={{ whiteSpace: "nowrap" }}>{source}</span>}
                            {tags && tags.length > 0 && (
                              <span style={{ whiteSpace: "nowrap" }}>{tags.slice(0, 2).join(", ")}{tags.length > 2 ? "..." : ""}</span>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  )}
                </div>
              </div>

              {/* Direita: LeadTag + Temperatura */}
              <div style={{ 
                display: "flex", 
                alignItems: "center", 
                gap: isMobile ? 6 : 8,
                flexShrink: 0,
                flexWrap: "wrap",
              }}>
                <LeadTag level={activeLead.level} score={activeLead.score} />
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ 
                    fontSize: 12, 
                    color: "var(--text-muted)",
                    whiteSpace: "nowrap",
                  }}>
                    {isMobile ? "Temp:" : "Temp.:"}
                  </span>
                  <select
                    className="select"
                    value={getOverrideLevel(activeId || "") || "auto"}
                    onChange={(e) => {
                      const v = e.target.value as LeadLevel | "auto";
                      handleOverride(v === "auto" ? null : (v as LeadLevel));
                    }}
                    style={{ 
                      fontSize: 12, 
                      padding: "6px 10px",
                      minWidth: isMobile ? 80 : 100,
                    }}
                  >
                    <option value="auto">Auto</option>
                    <option value="frio">Frio</option>
                    <option value="morno">Morno</option>
                    <option value="quente">Quente</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Linha inferior: Controles de ação */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: isMobile ? 6 : 8,
                padding: isMobile ? "6px 14px" : "8px 16px",
                borderTop: "1px solid var(--border)",
                background: "var(--panel)",
                flexWrap: "wrap",
                fontSize: 12,
              }}
            >
              <div style={{ 
                display: "flex", 
                alignItems: "center", 
                gap: isMobile ? 6 : 8,
                flexWrap: "wrap",
              }}>
                <label style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  gap: 6, 
                  cursor: "pointer", 
                  fontSize: 12,
                }}>
                  <input
                    type="checkbox"
                    checked={takeoverActive}
                    onChange={(e) => toggleTakeover(e.target.checked)}
                    style={{ width: 14, height: 14, cursor: "pointer" }}
                  />
                  <span>Assumir conversa</span>
                </label>

                {takeoverActive && (
                  <span className="chip badge-primary" style={{ fontSize: 10, padding: "2px 8px" }}>
                    Modo humano ativo
                  </span>
                )}

                {/* Tag de automação */}
                {(() => {
                  const thread = threads.find(t => String(t.id) === activeId);
                  const hasAutomation = automationActive || (thread as any)?.automation_active || (thread as any)?.funnel_id;
                  
                  if (hasAutomation) {
                    return (
                      <span className="chip" style={{ 
                        background: "var(--secondary-color)", 
                        color: "white", 
                        fontSize: 10,
                        padding: "2px 8px",
                      }}>
                        Em fluxo de automação
                      </span>
                    );
                  }
                  return null;
                })()}

                {/* Botão Ver fluxo */}
                {(() => {
                  const thread = threads.find(t => String(t.id) === activeId);
                  const hasAutomation = automationActive || (thread as any)?.automation_active || (thread as any)?.funnel_id;
                  
                  if (hasAutomation) {
                    return (
                      <button
                        className="btn soft btn-sm"
                        onClick={() => setShowAutomationModal(true)}
                        style={{ fontSize: 11, padding: "4px 10px" }}
                      >
                        Ver fluxo
                      </button>
                    );
                  }
                  return null;
                })()}
              </div>
            </div>
          </div>

          {/* Lista de mensagens */}
          <div
            ref={listRef}
            style={{
              overflowY: "auto",
              overflowX: "hidden",
              padding: isMobile ? "8px 6px" : "12px 16px",
              background: "var(--bg)",
              minHeight: 0,
              flex: 1,
              maxHeight: "100%",
              boxSizing: "border-box",
            }}
          >
          {loadingMessages && (
            <div className="small" style={{ 
              color: "var(--muted)", 
              padding: isMobile ? 6 : 8,
              fontSize: isMobile ? 12 : 13,
            }}>
              Carregando mensagens...
            </div>
          )}

          {!loadingMessages && messages.length === 0 && (
            <div className="card" style={{ 
              maxWidth: isMobile ? "90%" : 560, 
              margin: isMobile ? "20px auto" : "40px auto", 
              textAlign: "center", 
              padding: isMobile ? 16 : 20 
            }}>
              <h3 style={{ marginTop: 0, fontSize: isMobile ? 18 : 20 }}>Bem-vindo 👋</h3>
              <p className="small" style={{ 
                color: "var(--muted)",
                fontSize: isMobile ? 12 : 13,
              }}>
                Comece uma conversa enviando uma mensagem abaixo ou crie uma nova conversa.
              </p>
            </div>
          )}

          <div style={{ 
            display: "flex", 
            flexDirection: "column",
            gap: isMobile ? 8 : 10,
            paddingBottom: isMobile ? 8 : 12,
          }}>
            {messages.map((m) => {
              const thread = threads.find(t => String(t.id) === activeId);
              return <Bubble key={m.id} m={m} isMobile={isMobile} thread={thread} />;
            })}

            {assistantBuffer && (
              <div 
                className="bubble assistant"
                style={{
                  maxWidth: isMobile ? "85%" : "min(720px, 100%)",
                  padding: isMobile ? "8px 10px" : "10px 12px",
                }}
              >
                <div className="meta" style={{ 
                  fontSize: isMobile ? 11 : 12,
                  marginBottom: isMobile ? 4 : 6,
                  gap: isMobile ? 6 : 10,
                }}>
                  <span className="role">Assistente</span>
                  <span className="time">{formatTime(Date.now())}</span>
                </div>
                <div className="content" style={{ 
                  fontSize: isMobile ? 14 : 14,
                  lineHeight: isMobile ? 1.4 : 1.5,
                }}>{assistantBuffer}</div>
              </div>
            )}

            {!assistantBuffer && !takeoverActive && isTyping && (
              <div 
                className="bubble assistant"
                style={{
                  maxWidth: isMobile ? "85%" : "min(720px, 100%)",
                  padding: isMobile ? "8px 10px" : "10px 12px",
                }}
              >
                <div className="meta" style={{ 
                  fontSize: isMobile ? 11 : 12,
                  marginBottom: isMobile ? 4 : 6,
                  gap: isMobile ? 6 : 10,
                }}>
                  <span className="role">Assistente</span>
                  <span className="time">{formatTime(Date.now())}</span>
                </div>
                <Typing />
              </div>
            )}
          </div>

          {errorMsg && (
            <div
              role="alert"
              style={{
                border: "1px solid #7f1d1d",
                background: "#1b0f10",
                color: "#fecaca",
                padding: isMobile ? "8px 10px" : "10px 12px",
                borderRadius: 10,
                fontSize: isMobile ? 12 : 14,
                marginTop: isMobile ? 8 : 12,
                maxWidth: isMobile ? "90%" : 560,
              }}
            >
              {errorMsg}{" "}
              <button
                className="btn soft"
                onClick={() => {
                  setErrorMsg(null);
                  if (messages.length === 0) return;
                  const lastUser = [...messages].reverse().find((m) => m.role === "user");
                  if (lastUser) setInput(lastUser.content);
                }}
                style={{ marginLeft: 8 }}
              >
                Recarregar / Reenviar
              </button>
            </div>
          )}
        </div>

          {/* Composer - Só funciona quando takeover está ativo */}
          <Composer
            value={input}
            setValue={setInput}
            onSend={handleSend}
            disabled={sending || !takeoverActive}
            takeoverActive={takeoverActive}
            thread={threads.find(t => String(t.id) === activeId)}
            automationActive={automationActive}
          />
        </main>
      ) : (
        /* Tela quando nenhuma conversa está selecionada */
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "var(--bg)",
            color: "var(--muted)",
            textAlign: "center",
            padding: 40,
          }}
        >
          <div>
            <h3 style={{ margin: "0 0 8px 0", color: "var(--text)" }}>Selecione uma conversa</h3>
            <p style={{ margin: 0, fontSize: 14 }}>
              Escolha uma conversa da lista ao lado para começar a conversar
            </p>
          </div>
        </div>
      )}

      {/* Modal lateral de automação */}
      {showAutomationModal && (() => {
        const modalIsMobile = window.innerWidth < 768;
        return (
          <>
            <div
              style={{
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: "rgba(0,0,0,0.5)",
                zIndex: 10000,
              }}
              onClick={() => setShowAutomationModal(false)}
            />
            <div
              style={{
                position: "fixed",
                top: 0,
                right: 0,
                bottom: 0,
                width: modalIsMobile ? "90vw" : 400,
                maxWidth: "90vw",
                background: "var(--panel)",
                borderLeft: "1px solid var(--border)",
                boxShadow: "-4px 0 12px rgba(0,0,0,0.15)",
                zIndex: 10001,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
              }}
            >
            {/* Header do modal */}
            <div
              style={{
                padding: modalIsMobile ? "12px 14px" : "16px 20px",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexShrink: 0,
              }}
            >
              <h3 style={{ margin: 0, fontSize: modalIsMobile ? 16 : 18, fontWeight: 600 }}>
                Fluxo de Automação
              </h3>
              <button
                onClick={() => setShowAutomationModal(false)}
                style={{
                  padding: "6px 10px",
                  background: "transparent",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontSize: 18,
                  color: "var(--text)",
                }}
                aria-label="Fechar modal"
              >
                ✕
              </button>
            </div>

            {/* Conteúdo do modal */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: modalIsMobile ? "12px 14px" : "16px 20px",
              }}
            >
              {(() => {
                const thread = threads.find(t => String(t.id) === activeId);
                const hasAutomation = automationActive || (thread as any)?.automation_active || (thread as any)?.funnel_id;
                
                // Busca informações do funil e etapa
                const funnelId = (thread as any)?.funnel_id || (thread as any)?.metadata?.funnel_id;
                const stageId = (thread as any)?.stage_id || (thread as any)?.metadata?.stage_id;
                const leadStage = (thread as any)?.lead_stage || (thread as any)?.metadata?.lead_stage; // "frio", "aquecimento", "aquecido", "quente", etc.
                const leadLevel = (thread as any)?.lead_level;
                const leadScore = (thread as any)?.lead_score;
                
                const funnel = funnelId ? INITIAL_FUNNELS.find(f => Number(f.id) === Number(funnelId)) : null;
                
                // Mapeia lead_stage para a etapa correta do funil
                let stage: FunnelStage | null = null;
                if (funnel && leadStage) {
                  // Primeiro tenta encontrar por phase exato
                  stage = funnel.stages.find(s => s.phase === leadStage) || null;
                  // Se não encontrou, tenta mapear parcialmente
                  if (!stage) {
                    stage = funnel.stages.find(s => 
                      leadStage.includes(s.phase) || s.phase.includes(leadStage)
                    ) || null;
                  }
                }
                // Se ainda não encontrou, usa stage_id
                if (!stage && funnel && stageId) {
                  stage = funnel.stages.find(s => Number(s.id) === Number(stageId)) || null;
                }
                
                const automationName = funnel?.name || (thread as any)?.automation_name || (thread as any)?.funnel_name || "Automação ativa";
                const stageName = stage?.name || (thread as any)?.stage_name || ((thread as any)?.stage_id ? `Etapa #${(thread as any).stage_id}` : leadStage ? `Etapa: ${leadStage}` : "Etapa atual");
                const stageLabel = leadStage ? `${leadStage.charAt(0).toUpperCase() + leadStage.slice(1).replace(/_/g, " ")}` : null;
                
                // Busca nome do áudio se houver
                const audioName = stage?.audio_id ? INITIAL_AUDIOS.find(a => a.id === stage.audio_id)?.display_name : null;

                return (
                  <div style={{ display: "grid", gap: 16 }}>
                    {/* Automação ativa */}
                    {hasAutomation ? (
                      <div className="card" style={{ padding: modalIsMobile ? 12 : 16 }}>
                        <div style={{ 
                          fontSize: 12, 
                          color: "var(--muted)", 
                          marginBottom: 8,
                          fontWeight: 600,
                          textTransform: "uppercase",
                          letterSpacing: 0.5,
                        }}>
                          Fluxo de Automação
                        </div>
                        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
                          {automationName}
                        </div>
                        
                        {/* Lead Stage (atualizado pela automação em tempo real) */}
                        {leadStage && (
                          <div style={{ marginBottom: 12 }}>
                            <div style={{ 
                              fontSize: 11,
                              color: "var(--muted)",
                              marginBottom: 4,
                              fontWeight: 600,
                            }}>
                              Estágio Atual (atualizado pela IA)
                            </div>
                            <div style={{ 
                              padding: "6px 12px",
                              background: leadStage === "quente" ? "#dc262615" : 
                                          leadStage === "aquecido" ? "#ef444415" : 
                                          leadStage === "aquecimento" ? "#f59e0b15" : 
                                          leadStage === "assinante" ? "#10b98115" : "#3b82f615",
                              color: leadStage === "quente" ? "#dc2626" : 
                                     leadStage === "aquecido" ? "#ef4444" : 
                                     leadStage === "aquecimento" ? "#f59e0b" : 
                                     leadStage === "assinante" ? "#10b981" : "#3b82f6",
                              borderRadius: 8,
                              fontSize: 14,
                              fontWeight: 600,
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 6,
                            }}>
                              {stageLabel}
                            </div>
                          </div>
                        )}
                        
                        {/* Etapa do Funil */}
                        {stage && (
                          <div style={{ 
                            padding: 10,
                            background: "var(--bg)",
                            borderRadius: 8,
                            fontSize: 12,
                            color: "var(--text)",
                            marginBottom: 8,
                          }}>
                            <div style={{ marginBottom: 6, fontWeight: 600, fontSize: 13 }}>
                              Etapa: {stageName}
                            </div>
                            <div style={{ marginBottom: 4, color: "var(--muted)" }}>
                              Ordem: {stage.order} • Fase: {stage.phase}
                            </div>
                            {audioName && (
                              <div style={{ color: "var(--muted)", marginTop: 4 }}>
                                Áudio configurado: {audioName}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {/* Lead Level e Score */}
                        {(leadLevel || leadScore !== undefined) && (
                          <div style={{ 
                            padding: 10,
                            background: "var(--bg)",
                            borderRadius: 8,
                            fontSize: 12,
                            display: "flex",
                            gap: 12,
                            flexWrap: "wrap",
                          }}>
                            {leadLevel && (
                              <div>
                                <span style={{ color: "var(--muted)", fontSize: 11 }}>Nível:</span>{" "}
                                <strong style={{ color: "var(--text)" }}>{leadLevel}</strong>
                              </div>
                            )}
                            {leadScore !== undefined && leadScore !== null && (
                              <div>
                                <span style={{ color: "var(--muted)", fontSize: 11 }}>Score:</span>{" "}
                                <strong style={{ color: "var(--text)" }}>{leadScore}</strong>
                              </div>
                            )}
                          </div>
                        )}
                        
                        {/* Aviso se não há lead_stage */}
                        {!leadStage && (
                          <div style={{ 
                            padding: 8,
                            background: "#fef3c7",
                            borderRadius: 6,
                            fontSize: 11,
                            color: "#92400e",
                          }}>
                            ⚠️ Este contato ainda não tem um estágio definido. O estágio será atualizado automaticamente quando a automação detectar gatilhos.
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="card" style={{ padding: modalIsMobile ? 12 : 16, background: "#f3f4f6" }}>
                        <div style={{ fontSize: 13, color: "var(--muted)", textAlign: "center" }}>
                          ⚠️ Nenhuma automação ativa para este contato
                        </div>
                      </div>
                    )}

                    {/* Enviar Áudios */}
                    <div>
                      <div style={{ 
                        fontSize: 12, 
                        color: "var(--muted)", 
                        marginBottom: 12,
                        fontWeight: 600,
                        textTransform: "uppercase",
                        letterSpacing: 0.5,
                      }}>
                        Enviar Áudios
                      </div>
                      <AudioList 
                        audios={INITIAL_AUDIOS}
                        threadId={activeId}
                        onSendAudio={async (audioId: string, audioName: string) => {
                          if (!activeId) return;
                          
                          try {
                            await sendAudio(Number(activeId), audioId);
                            
                            // Atualiza mensagens para mostrar o áudio enviado
                            const newMsg: UIMessage = {
                              id: "temp-audio-" + Date.now(),
                              role: "assistant",
                              content: `[Áudio enviado manualmente: ${audioName}]`,
                              created_at: new Date().toISOString(),
                              is_human: true,
                            };
                            setMessages((prev) => [...prev, newMsg]);
                            
                            // Scroll para baixo
                            setTimeout(() => {
                              listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
                            }, 100);
                          } catch (error: any) {
                            setErrorMsg(error?.message || "Erro ao enviar áudio");
                          }
                        }}
                        isMobile={modalIsMobile}
                      />
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </>
        );
      })()}
    </div>
  );
}
