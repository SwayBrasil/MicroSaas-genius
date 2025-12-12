// frontend/src/pages/Kanban.tsx
import React, { useEffect, useMemo, useState } from "react";
import { listThreads, updateThread, getMessages, type Thread } from "../api";
import { INITIAL_FUNNELS } from "../data/funnels";
import type { Funnel, FunnelStage } from "../types/funnel";

type UIMessage = { id: number | string; role: "user" | "assistant"; content: string; created_at?: string };

// ===== Config de layout =====
const CARD_HEIGHT = 200;

// ===== Helpers =====
function name(t: Thread) {
  return (
    (t.title || "").trim() ||
    `Contato • ${(t.metadata?.wa_id || t.metadata?.phone || "").toString().slice(-4) || "—"}`
  );
}

function phone(t: Thread) {
  const wa = (t.metadata?.wa_id || t.metadata?.phone || "").toString();
  return wa ? (wa.startsWith("+") ? wa : `+${wa}`) : "";
}

function getPhaseColor(phase: string): { bg: string; border: string; text: string } {
  const map: Record<string, { bg: string; border: string; text: string }> = {
    frio: { bg: "#eff6ff", border: "#3b82f6", text: "#1e40af" },
    aquecimento: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
    aquecido: { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
    quente: { bg: "#dc2626", border: "#dc2626", text: "#ffffff" },
    assinante: { bg: "#d1fae5", border: "#10b981", text: "#065f46" },
    assinante_fatura_pendente: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
  };
  return map[phase] || { bg: "#f3f4f6", border: "#6b7280", text: "#374151" };
}

// ===== Tipagem enriquecida =====
type Row = Thread & {
  _phone?: string;
  _lastAt?: string;
  _lastText?: string;
  funnel_id?: number | string | null;
  stage_id?: number | string | null;
};

export default function Kanban() {
  const [items, setItems] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [selectedFunnelId, setSelectedFunnelId] = useState<number | string>(1); // Funil Longo por padrão

  const selectedFunnel = useMemo(() => {
    return INITIAL_FUNNELS.find(f => f.id === selectedFunnelId) || INITIAL_FUNNELS[0];
  }, [selectedFunnelId]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Carrega threads
  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const ts = await listThreads();
        const base: Row[] = ts.map((t) => ({
          ...t,
          _phone: phone(t),
          funnel_id: (t as any).funnel_id || (t.metadata as any)?.funnel_id || null,
          stage_id: (t as any).stage_id || (t.metadata as any)?.stage_id || null,
          lead_stage: (t as any).lead_stage || (t.metadata as any)?.lead_stage || null,
        }));
        setItems(base);

        // Completa com última mensagem
        const CONC = 4;
        for (let i = 0; i < base.length; i += CONC) {
          await Promise.all(
            base.slice(i, i + CONC).map(async (t) => {
              try {
                const msgs = (await getMessages(Number(t.id))) as UIMessage[];
                if (!msgs?.length) return;
                const last = msgs[msgs.length - 1];
                setItems((prev) =>
                  prev.map((r) =>
                    r.id === t.id
                      ? {
                          ...r,
                          _lastText: last.content,
                          _lastAt: last.created_at,
                        }
                      : r
                  )
                );
              } catch {
                /* silencioso */
              }
            })
          );
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Refresh leve a cada 10s para acompanhar mudanças de fluxo em tempo real
  useEffect(() => {
    const id = window.setInterval(async () => {
      const ts = await listThreads();
      setItems((prev) => {
        const map = new Map(prev.map((x) => [String(x.id), x]));
        for (const t of ts) {
          const r = map.get(String(t.id));
          const funnelId = (t as any).funnel_id || ((t.metadata as any)?.funnel_id);
          const stageId = (t as any).stage_id || ((t.metadata as any)?.stage_id);
          const leadStage = (t as any).lead_stage || ((t.metadata as any)?.lead_stage);
          
          if (r) {
            map.set(String(t.id), { 
              ...r, 
              origin: t.origin,
              lead_level: t.lead_level,
              lead_score: t.lead_score,
              funnel_id: funnelId || r.funnel_id,
              stage_id: stageId || r.stage_id,
              lead_stage: leadStage || r.lead_stage,
            });
          } else {
            map.set(String(t.id), { 
              ...(t as Row), 
              _phone: phone(t),
              funnel_id: funnelId,
              stage_id: stageId,
              lead_stage: leadStage,
            });
          }
        }
        return Array.from(map.values());
      });
    }, 10000); // Atualiza a cada 10 segundos
    return () => clearInterval(id);
  }, []);

  // Filtra e agrupa por etapa
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    let filteredItems = items;
    
    if (s) {
      filteredItems = items.filter(
        (t) =>
          name(t).toLowerCase().includes(s) ||
          (t._phone || "").toLowerCase().includes(s) ||
          (t._lastText || "").toLowerCase().includes(s) ||
          ((t as any).source || "").toLowerCase().includes(s)
      );
    }

    // Filtra apenas contatos que estão no funil selecionado (ou sem funil)
    filteredItems = filteredItems.filter(t => {
      const tFunnelId = t.funnel_id || (t.metadata as any)?.funnel_id;
      // Mostra contatos que estão no funil selecionado OU contatos sem funil (para adicionar)
      return !tFunnelId || Number(tFunnelId) === Number(selectedFunnelId);
    });

    return filteredItems;
  }, [q, items, selectedFunnelId]);

  // Agrupa contatos por etapa do funil
  const byStage = useMemo(() => {
    const out: Record<string, Row[]> = {};
    
    // Inicializa todas as etapas
    selectedFunnel.stages.forEach(stage => {
      out[String(stage.id)] = [];
    });
    
    // Adiciona uma coluna para "Sem etapa" (contatos no funil mas sem stage_id)
    out["none"] = [];

    // Agrupa contatos usando lead_stage (prioridade) ou stage_id como fallback
    filtered.forEach((t) => {
      // Prioriza lead_stage do backend (sempre atualizado pela automação)
      const leadStage = (t as any).lead_stage || (t.metadata as any)?.lead_stage;
      const stageId = t.stage_id || (t.metadata as any)?.stage_id;
      
      // Mapeia lead_stage para stage_id do funil
      let mappedStageId: string | null = null;
      
      if (leadStage) {
        // Busca a etapa que corresponde ao phase do lead_stage
        // lead_stage pode ser: "frio", "aquecimento", "aquecido", "quente", "assinante", etc.
        const matchedStage = selectedFunnel.stages.find(s => s.phase === leadStage);
        if (matchedStage) {
          mappedStageId = String(matchedStage.id);
        } else {
          // Se não encontrou por phase exato, tenta mapear por nome similar
          // Ex: "quente_recebeu_oferta" pode mapear para etapa com phase "quente"
          const partialMatch = selectedFunnel.stages.find(s => 
            leadStage.includes(s.phase) || s.phase.includes(leadStage)
          );
          if (partialMatch) {
            mappedStageId = String(partialMatch.id);
          }
        }
      }
      
      // Se não encontrou por lead_stage, usa stage_id direto
      // Se stage_id não corresponde ao funil selecionado, vai para "none"
      const key = mappedStageId || (stageId ? String(stageId) : "none");
      
      if (out[key] !== undefined) {
        out[key].push(t);
      } else {
        // Se a etapa não existe no funil selecionado, coloca em "none"
        out["none"].push(t);
      }
    });

    // Ordena cada coluna por última mensagem (mais recente primeiro)
    Object.keys(out).forEach(key => {
      out[key].sort((a, b) => {
        const ta = a._lastAt ? new Date(a._lastAt).getTime() : 0;
        const tb = b._lastAt ? new Date(b._lastAt).getTime() : 0;
        return tb - ta;
      });
    });

    return out;
  }, [filtered, selectedFunnel]);

  async function moveToStage(t: Row, stage: FunnelStage) {
    const id = t.id;
    const prevStageId = t.stage_id || (t.metadata as any)?.stage_id;
    const prevFunnelId = t.funnel_id || (t.metadata as any)?.funnel_id;
    
    setItems((prevItems) => 
      prevItems.map((x) => 
        x.id === id 
          ? { 
              ...x, 
              stage_id: stage.id,
              funnel_id: selectedFunnelId,
              metadata: {
                ...(x.metadata || {}),
                stage_id: Number(stage.id),
                funnel_id: Number(selectedFunnelId),
              },
            } 
          : x
      )
    );

    try {
      // Atualiza via metadata já que o backend aceita metadata como dict
      await updateThread(Number(id), { 
        metadata: {
          ...(t.metadata || {}),
          stage_id: Number(stage.id),
          funnel_id: Number(selectedFunnelId),
        },
      } as any);
    } catch {
      setItems((prevItems) => 
        prevItems.map((x) => 
          x.id === id 
            ? { 
                ...x, 
                stage_id: prevStageId || null,
                funnel_id: prevFunnelId || null,
                metadata: {
                  ...(x.metadata || {}),
                  ...(prevStageId ? { stage_id: Number(prevStageId) } : {}),
                  ...(prevFunnelId ? { funnel_id: Number(prevFunnelId) } : {}),
                },
              } 
            : x
        )
      );
      alert("Falha ao atualizar a etapa.");
    }
  }

  function onDragStart(e: React.DragEvent, t: Row) {
    e.dataTransfer.setData("text/plain", String(t.id));
  }

  function onDrop(e: React.DragEvent, stage: FunnelStage) {
    e.preventDefault();
    const id = e.dataTransfer.getData("text/plain");
    const t = items.find((x) => String(x.id) === id);
    if (t) moveToStage(t, stage);
  }

  function onDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  function StageColumn({ stage }: { stage: FunnelStage }) {
    const data = byStage[String(stage.id)] || [];
    const phaseStyle = getPhaseColor(stage.phase);

    return (
      <div
        className="card"
        style={{
          display: "flex",
          flexDirection: "column",
          border: `2px solid ${phaseStyle.border}`,
          background: "var(--bg)",
          minHeight: isMobile ? "auto" : "calc(100vh - 220px)",
          maxHeight: isMobile ? "calc((100vh - 240px) / 2)" : "calc(100vh - 220px)",
          width: "100%",
          overflow: "hidden",
        }}
        onDragOver={onDragOver}
        onDrop={(e) => onDrop(e, stage)}
      >
        {/* Header da etapa */}
        <div
          style={{
            background: phaseStyle.bg,
            color: phaseStyle.text,
            padding: isMobile ? "8px 10px" : "12px 16px",
            display: "flex",
            flexDirection: "column",
            gap: 6,
            borderTopLeftRadius: 10,
            borderTopRightRadius: 10,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ 
                fontSize: isMobile ? 16 : 18, 
                fontWeight: 700,
              }}>
                {stage.order}
              </span>
              <strong style={{ fontSize: isMobile ? 13 : 14 }}>{stage.name}</strong>
            </div>
            <span
              style={{
                background: phaseStyle.border,
                color: "white",
                borderRadius: 20,
                padding: "2px 10px",
                fontSize: isMobile ? 11 : 12,
                fontWeight: 600,
              }}
            >
              {data.length}
            </span>
          </div>
          
          {/* Badge de fase */}
          <div style={{ fontSize: 11, opacity: 0.8 }}>
            {stage.phase === "frio" && "❄️"}
            {stage.phase === "aquecimento" && "🌤️"}
            {stage.phase === "aquecido" && "🔥"}
            {stage.phase === "quente" && "🔥🔥"}
            {stage.phase === "assinante" && "✅"}
            {stage.phase === "assinante_fatura_pendente" && "⚠️"}
            {" "}
            {stage.phase.charAt(0).toUpperCase() + stage.phase.slice(1).replace(/_/g, " ")}
          </div>
        </div>

        {/* Lista de contatos */}
        <div style={{ 
          flex: 1, 
          overflowY: "auto", 
          padding: isMobile ? 8 : 12, 
          display: "grid", 
          gap: isMobile ? 8 : 10 
        }}>
          {data.map((t) => (
            <div
              key={t.id}
              draggable
              onDragStart={(e) => onDragStart(e, t)}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 10,
                background: "var(--panel)",
                padding: isMobile ? 10 : 12,
                display: "flex",
                flexDirection: "column",
                gap: 8,
                minHeight: CARD_HEIGHT,
                boxSizing: "border-box",
                cursor: "grab",
                transition: "all 0.2s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.1)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              {/* Nome */}
              <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                <strong
                  style={{
                    flex: 1,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    fontSize: isMobile ? 13 : 14,
                    color: "var(--text)",
                  }}
                  title={name(t)}
                >
                  {name(t)}
                </strong>
                {/* Tag de Suporte/Human Takeover */}
                {t.human_takeover && (
                  <div 
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "4px 10px",
                      borderRadius: 12,
                      fontSize: 10,
                      fontWeight: 700,
                      background: "#dc2626",
                      color: "#ffffff",
                      textTransform: "uppercase",
                      letterSpacing: 0.5,
                      boxShadow: "0 2px 8px rgba(220, 38, 38, 0.4)",
                      animation: "pulse 2s ease-in-out infinite",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = "scale(1.05)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = "scale(1)";
                    }}
                  >
                    Precisa Atenção
                  </div>
                )}
              </div>

              {/* Telefone */}
              {t._phone && (
                <div className="small" style={{ color: "var(--muted)", fontSize: 11 }}>
                  {t._phone}
                </div>
              )}

              {/* Origem */}
              {t.origin && (
                <div className="small" style={{ color: "var(--muted)", fontSize: 11 }}>
                  {t.origin.replace(/_/g, " ")}
                </div>
              )}

              {/* Lead Stage (atualizado pela automação) */}
              {(t as any).lead_stage && (
                <div style={{ 
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "2px 8px",
                  borderRadius: 12,
                  fontSize: 10,
                  fontWeight: 600,
                  background: (t as any).lead_stage === "quente" ? "#dc262615" : 
                              (t as any).lead_stage === "aquecido" ? "#ef444415" : 
                              (t as any).lead_stage === "aquecimento" ? "#f59e0b15" : 
                              (t as any).lead_stage === "assinante" ? "#10b98115" : "#3b82f615",
                  color: (t as any).lead_stage === "quente" ? "#dc2626" : 
                         (t as any).lead_stage === "aquecido" ? "#ef4444" : 
                         (t as any).lead_stage === "aquecimento" ? "#f59e0b" : 
                         (t as any).lead_stage === "assinante" ? "#10b981" : "#3b82f6",
                  width: "fit-content",
                }}>
                  {(t as any).lead_stage.charAt(0).toUpperCase() + (t as any).lead_stage.slice(1).replace(/_/g, " ")}
                </div>
              )}

              {/* Tags */}
              {((t as any).tags && Array.isArray((t as any).tags) && (t as any).tags.length > 0) && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {(t as any).tags.slice(0, 2).map((tag: string, idx: number) => (
                    <span key={idx} className="chip soft" style={{ fontSize: 9, padding: "2px 6px" }}>
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {/* Espaçador */}
              <div style={{ flex: 1, minHeight: 0 }} />

              {/* Última mensagem */}
              {t._lastText && (
                <div
                  className="small"
                  style={{
                    color: "var(--muted)",
                    borderTop: "1px dashed var(--border)",
                    paddingTop: 8,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                    fontSize: 11,
                    lineHeight: 1.4,
                  }}
                  title={t._lastText}
                >
                  "{t._lastText}"
                </div>
              )}

              {/* Última atualização */}
              {t._lastAt && (
                <div className="small" style={{ color: "var(--muted)", fontSize: 10 }}>
                  {new Date(t._lastAt).toLocaleString([], { 
                    day: "2-digit", 
                    month: "2-digit", 
                    hour: "2-digit", 
                    minute: "2-digit" 
                  })}
                </div>
              )}

              {/* Botão para abrir chat */}
              <a
                href={`/#/chat?thread=${t.id}`}
                className="btn soft"
                style={{
                  fontSize: isMobile ? 11 : 12,
                  padding: "6px 10px",
                  textAlign: "center",
                  textDecoration: "none",
                  display: "block",
                }}
                onClick={(e) => e.stopPropagation()}
              >
                💬 Abrir chat
              </a>
            </div>
          ))}
          
          {data.length === 0 && (
            <div 
              className="small" 
              style={{ 
                color: "var(--muted)", 
                textAlign: "center", 
                padding: 20,
                border: "2px dashed var(--border)",
                borderRadius: 8,
              }}
            >
              Arraste contatos aqui
            </div>
          )}
        </div>
      </div>
    );
  }

  // Coluna para contatos sem etapa
  function NoneColumn() {
    const data = byStage["none"] || [];

    return (
      <div
        className="card"
        style={{
          display: "flex",
          flexDirection: "column",
          border: "2px dashed var(--border)",
          background: "var(--bg)",
          minHeight: isMobile ? "auto" : "calc(100vh - 220px)",
          maxHeight: isMobile ? "calc((100vh - 240px) / 2)" : "calc(100vh - 220px)",
          width: "100%",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            background: "var(--panel)",
            color: "var(--muted)",
            padding: isMobile ? "8px 10px" : "12px 16px",
            borderTopLeftRadius: 10,
            borderTopRightRadius: 10,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong style={{ fontSize: isMobile ? 13 : 14 }}>Sem etapa</strong>
            <span
              style={{
                background: "var(--border)",
                color: "var(--muted)",
                borderRadius: 20,
                padding: "2px 10px",
                fontSize: isMobile ? 11 : 12,
              }}
            >
              {data.length}
            </span>
          </div>
        </div>

        <div style={{ 
          flex: 1, 
          overflowY: "auto", 
          padding: isMobile ? 8 : 12, 
          display: "grid", 
          gap: isMobile ? 8 : 10 
        }}>
          {data.map((t) => (
            <div
              key={t.id}
              draggable
              onDragStart={(e) => onDragStart(e, t)}
              style={{
                border: "1px solid var(--border)",
                borderRadius: 10,
                background: "var(--panel)",
                padding: isMobile ? 10 : 12,
                display: "flex",
                flexDirection: "column",
                gap: 8,
                minHeight: CARD_HEIGHT,
                boxSizing: "border-box",
                cursor: "grab",
              }}
            >
              <strong
                style={{
                  fontSize: isMobile ? 13 : 14,
                  color: "var(--text)",
                }}
                title={name(t)}
              >
                {name(t)}
              </strong>
              {t._phone && (
                <div className="small" style={{ color: "var(--muted)", fontSize: 11 }}>
                  {t._phone}
                </div>
              )}
              <div style={{ flex: 1 }} />
              <a
                href={`/#/chat?thread=${t.id}`}
                className="btn soft"
                style={{
                  fontSize: isMobile ? 11 : 12,
                  padding: "6px 10px",
                  textAlign: "center",
                  textDecoration: "none",
                  display: "block",
                }}
              >
                💬 Abrir chat
              </a>
            </div>
          ))}
          
          {data.length === 0 && (
            <div 
              className="small" 
              style={{ 
                color: "var(--muted)", 
                textAlign: "center", 
                padding: 20,
              }}
            >
              Nenhum contato sem etapa
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{ 
      height: "calc(100vh - 56px)", 
      maxHeight: "calc(100vh - 56px)",
      display: "grid", 
      gridTemplateRows: "auto auto 1fr",
      overflow: "hidden",
    }}>
      {/* Header com seletor de funil */}
      <div
        style={{
          display: "flex",
          gap: isMobile ? 8 : 12,
          alignItems: "center",
          padding: isMobile ? "10px 12px" : "12px 16px",
          borderBottom: "1px solid var(--border)",
          background: "var(--panel)",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: isMobile ? "1 1 100%" : "auto" }}>
          <strong style={{ fontSize: isMobile ? 14 : 16 }}>Funil:</strong>
          <select
            className="select"
            value={selectedFunnelId}
            onChange={(e) => setSelectedFunnelId(Number(e.target.value))}
            style={{
              fontSize: isMobile ? 13 : 14,
              padding: "6px 12px",
              minWidth: isMobile ? "100%" : 250,
            }}
          >
            {INITIAL_FUNNELS.map((funnel) => (
              <option key={funnel.id} value={funnel.id}>
                {funnel.name} {funnel.is_active ? "✅" : "⏸️"}
              </option>
            ))}
          </select>
        </div>

        <div style={{ 
          fontSize: isMobile ? 11 : 12,
          color: "var(--muted)",
          flex: isMobile ? "1 1 100%" : "auto",
        }}>
          {selectedFunnel.description}
        </div>

        <div className="small" style={{ 
          marginLeft: isMobile ? 0 : "auto", 
          color: "var(--muted)",
          fontSize: isMobile ? 11 : 12,
        }}>
          {filtered.length} contato(s)
        </div>
      </div>

      {/* Barra de busca */}
      <div
        style={{
          display: "flex",
          gap: isMobile ? 6 : 8,
          alignItems: "center",
          padding: isMobile ? "8px 12px" : "10px 16px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg)",
        }}
      >
        <input
          className="input"
          placeholder={isMobile ? "Buscar..." : "Buscar contato (nome, telefone, mensagem)..."}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ 
            maxWidth: isMobile ? "100%" : 400,
            fontSize: isMobile ? 14 : 15,
            flex: isMobile ? 1 : "auto",
          }}
        />
      </div>

      {/* Grid de colunas (etapas) */}
      <div style={{ 
        padding: isMobile ? 8 : 12,
        overflow: isMobile ? "auto" : "auto",
      }}>
        <div style={{ 
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : `repeat(${selectedFunnel.stages.length + 1}, 1fr)`,
          gap: isMobile ? 12 : 16,
          minWidth: isMobile ? "100%" : `${(selectedFunnel.stages.length + 1) * 320}px`,
        }}>
          {selectedFunnel.stages.map((stage) => (
            <StageColumn key={stage.id} stage={stage} />
          ))}
          <NoneColumn />
        </div>
      </div>

      {loading && (
        <div 
          className="small" 
          style={{ 
            padding: 12, 
            color: "var(--muted)",
            textAlign: "center",
            position: "absolute",
            bottom: 20,
            left: "50%",
            transform: "translateX(-50%)",
            background: "var(--bg)",
            borderRadius: 8,
            border: "1px solid var(--border)",
          }}
        >
          Carregando contatos…
        </div>
      )}
    </div>
  );
}
