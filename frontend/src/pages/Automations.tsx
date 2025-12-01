// frontend/src/pages/Automations.tsx
import React, { useState, useEffect } from "react";
import { INITIAL_FUNNELS } from "../data/funnels";
import { INITIAL_AUDIOS } from "../data/audios";
import type { Funnel, FunnelStage } from "../types/funnel";

export default function Automations() {
  const [funnels, setFunnels] = useState<Funnel[]>(INITIAL_FUNNELS);
  const [selectedFunnel, setSelectedFunnel] = useState<Funnel | null>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [editingFunnel, setEditingFunnel] = useState<Funnel | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editIsActive, setEditIsActive] = useState(false);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  function getAudioName(audioId?: number | string | null) {
    if (!audioId) return null;
    const audio = INITIAL_AUDIOS.find((a) => a.id === audioId);
    return audio?.display_name || `Áudio #${audioId}`;
  }

  function getPhaseDisplayName(phase: string) {
    const map: Record<string, string> = {
      frio: "❄️ Frio",
      aquecimento: "🌤️ Aquecimento",
      aquecido: "🔥 Aquecido",
      quente: "🔥🔥 Quente",
      assinante: "✅ Assinante",
      assinante_fatura_pendente: "⚠️ Assinante (Fatura Pendente)",
    };
    return map[phase] || phase;
  }

  function handleEditFunnel(funnel: Funnel) {
    setEditingFunnel(funnel);
    setEditName(funnel.name);
    setEditDescription(funnel.description || "");
    setEditIsActive(funnel.is_active);
  }

  function handleSaveFunnel() {
    if (!editingFunnel) return;
    
    const updated = {
      ...editingFunnel,
      name: editName,
      description: editDescription,
      is_active: editIsActive,
    };
    
    setFunnels(funnels.map(f => f.id === editingFunnel.id ? updated : f));
    if (selectedFunnel?.id === editingFunnel.id) {
      setSelectedFunnel(updated);
    }
    setEditingFunnel(null);
    setEditName("");
    setEditDescription("");
    setEditIsActive(false);
  }

  function handleCancelEdit() {
    setEditingFunnel(null);
    setEditName("");
    setEditDescription("");
    setEditIsActive(false);
  }

  return (
    <div style={{ 
      height: "calc(100vh - 56px)", 
      maxHeight: "calc(100vh - 56px)",
      display: "grid", 
      gridTemplateColumns: isMobile ? "1fr" : "300px 1fr",
      overflow: "hidden",
    }}>
      {/* Sidebar - Lista de Funis */}
      <div style={{ 
        borderRight: isMobile ? "none" : "1px solid var(--border)",
        background: "var(--panel)",
        overflowY: "auto",
        padding: isMobile ? 8 : 12,
      }}>
        <div style={{ marginBottom: 12 }}>
          <h3 style={{ margin: "0 0 8px 0", fontSize: isMobile ? 14 : 16 }}>Funis</h3>
          <button className="btn" style={{ width: "100%", fontSize: isMobile ? 12 : 13 }}>
            + Novo Funil
          </button>
        </div>

        <div style={{ display: "grid", gap: 8 }}>
          {funnels.map((funnel) => (
            <button
              key={funnel.id}
              onClick={() => setSelectedFunnel(funnel)}
              className={selectedFunnel?.id === funnel.id ? "btn" : "btn soft"}
              style={{
                textAlign: "left",
                padding: isMobile ? 10 : 12,
                fontSize: isMobile ? 13 : 14,
                display: "flex",
                flexDirection: "column",
                gap: 4,
                alignItems: "flex-start",
              }}
            >
              <div style={{ fontWeight: 600 }}>{funnel.name}</div>
              <div style={{ fontSize: 11, color: "var(--muted)" }}>
                {funnel.stages.length} etapa(s) • {funnel.is_active ? "✅ Ativo" : "⏸️ Pausado"}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Conteúdo - Detalhes do Funil */}
      <div style={{ overflowY: "auto", padding: isMobile ? 8 : 16 }}>
        {!selectedFunnel ? (
          <div style={{ 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "center", 
            height: "100%",
            color: "var(--muted)",
            textAlign: "center",
          }}>
            <div>
              <div style={{ fontSize: 64, marginBottom: 16, opacity: 0.5 }}>⚙️</div>
              <p style={{ margin: 0, fontSize: 15 }}>
                Selecione um funil para ver os detalhes
              </p>
            </div>
          </div>
        ) : (
          <div style={{ 
            display: "flex", 
            flexDirection: "column", 
            alignItems: "center",
            maxWidth: 900,
            margin: "0 auto",
            width: "100%",
          }}>
            {/* Header do Funil */}
            <div className="card" style={{ 
              padding: isMobile ? 16 : 24,
              width: "100%",
              marginBottom: 24,
              background: "var(--bg)",
              boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h2 style={{ margin: "0 0 10px 0", fontSize: isMobile ? 20 : 24, fontWeight: 700 }}>
                    {selectedFunnel.name}
                  </h2>
                  {selectedFunnel.description && (
                    <p style={{ margin: 0, fontSize: 14, color: "var(--muted)", lineHeight: 1.6 }}>
                      {selectedFunnel.description}
                    </p>
                  )}
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <span className="chip" style={{ 
                    background: selectedFunnel.is_active ? "#10b98120" : "#6b728020",
                    color: selectedFunnel.is_active ? "#10b981" : "#6b7280",
                    fontSize: 12,
                    fontWeight: 500,
                  }}>
                    {selectedFunnel.is_active ? "✅ Ativo" : "⏸️ Pausado"}
                  </span>
                  <button 
                    className="btn soft" 
                    style={{ fontSize: 13, padding: "8px 14px" }}
                    onClick={() => handleEditFunnel(selectedFunnel)}
                  >
                    ✏️ Editar
                  </button>
                </div>
              </div>
            </div>

            {/* Etapas do Funil - Centralizadas com conectores */}
            <div style={{ width: "100%", position: "relative" }}>
              <h3 style={{ 
                margin: "0 0 24px 0", 
                fontSize: isMobile ? 18 : 20,
                fontWeight: 600,
                textAlign: "center",
                color: "var(--text)",
              }}>
                Fluxo de Etapas ({selectedFunnel.stages.length})
              </h3>
              
              <div style={{ 
                display: "grid", 
                gap: 0,
                position: "relative",
              }}>
                {selectedFunnel.stages.map((stage, index) => (
                  <div key={stage.id} style={{ position: "relative", width: "100%" }}>
                    {/* Conector entre etapas */}
                    {index < selectedFunnel.stages.length - 1 && (
                      <div style={{
                        position: "absolute",
                        left: "50%",
                        transform: "translateX(-50%)",
                        bottom: -12,
                        width: 2,
                        height: 20,
                        background: "linear-gradient(180deg, var(--border) 0%, transparent 100%)",
                        zIndex: 0,
                      }} />
                    )}
                    
                    {/* Card da Etapa */}
                    <div className="card" style={{ 
                      padding: isMobile ? 18 : 24,
                      width: "100%",
                      marginBottom: index < selectedFunnel.stages.length - 1 ? 32 : 0,
                      background: "var(--bg)",
                      boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
                      border: "1px solid var(--border)",
                      borderRadius: 16,
                      position: "relative",
                      zIndex: 1,
                      transition: "all 0.2s ease",
                    }}>
                      {/* Header da etapa - centralizado */}
                      <div style={{ 
                        display: "flex", 
                        flexDirection: "column",
                        alignItems: "center",
                        marginBottom: 20,
                        textAlign: "center",
                      }}>
                        <div style={{ 
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: 48,
                          height: 48,
                          borderRadius: "50%",
                          background: "linear-gradient(135deg, var(--primary-color) 0%, #1d4ed8 100%)",
                          color: "#fff",
                          fontSize: 20,
                          fontWeight: 700,
                          marginBottom: 12,
                          boxShadow: "0 4px 12px rgba(37, 99, 235, 0.3)",
                        }}>
                          {stage.order}
                        </div>
                        
                        <h4 style={{ 
                          fontWeight: 600, 
                          fontSize: isMobile ? 16 : 18,
                          margin: "0 0 8px 0",
                          color: "var(--text)",
                        }}>
                          {stage.name}
                        </h4>
                        
                        <span className="chip soft" style={{ 
                          fontSize: 11,
                          fontWeight: 500,
                          padding: "6px 12px",
                        }}>
                          {getPhaseDisplayName(stage.phase)}
                        </span>
                      </div>

                      {/* Conteúdo da etapa - em grid centralizado */}
                      {(stage.audio_id || stage.text_template || (stage.conditions && stage.conditions.length > 0) || (stage.actions && stage.actions.length > 0)) && (
                        <div style={{ 
                          display: "grid", 
                          gap: 14,
                          gridTemplateColumns: stage.audio_id && stage.text_template 
                            ? "repeat(auto-fit, minmax(280px, 1fr))" 
                            : "1fr",
                        }}>
                          {/* Áudio */}
                          {stage.audio_id && (
                            <div style={{ 
                              padding: 14,
                              background: "linear-gradient(135deg, rgba(37, 99, 235, 0.05) 0%, rgba(37, 99, 235, 0.02) 100%)",
                              borderRadius: 12,
                              border: "1px solid rgba(37, 99, 235, 0.15)",
                            }}>
                              <div style={{ 
                                fontSize: 11, 
                                color: "var(--muted)", 
                                marginBottom: 6,
                                fontWeight: 600,
                                textTransform: "uppercase",
                                letterSpacing: "0.5px",
                              }}>
                                🎵 Áudio
                              </div>
                              <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)" }}>
                                {getAudioName(stage.audio_id)}
                              </div>
                            </div>
                          )}

                          {/* Template de texto */}
                          {stage.text_template && (
                            <div style={{ 
                              padding: 14,
                              background: "linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(16, 185, 129, 0.02) 100%)",
                              borderRadius: 12,
                              border: "1px solid rgba(16, 185, 129, 0.15)",
                            }}>
                              <div style={{ 
                                fontSize: 11, 
                                color: "var(--muted)", 
                                marginBottom: 6,
                                fontWeight: 600,
                                textTransform: "uppercase",
                                letterSpacing: "0.5px",
                              }}>
                                💬 Template de Texto
                              </div>
                              <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)", wordBreak: "break-word" }}>
                                {stage.text_template}
                              </div>
                            </div>
                          )}

                        {/* Condições */}
                        {stage.conditions && stage.conditions.length > 0 && (
                          <div style={{ gridColumn: "1 / -1" }}>
                            <div style={{ 
                              fontSize: 11, 
                              color: "var(--muted)", 
                              marginBottom: 10, 
                              fontWeight: 600,
                              textTransform: "uppercase",
                              letterSpacing: "0.5px",
                            }}>
                              ⚡ Condições para avançar
                            </div>
                            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
                              {stage.conditions.map((condition, idx) => (
                                <div key={idx} style={{ 
                                  padding: 10,
                                  background: "var(--panel)",
                                  borderRadius: 8,
                                  fontSize: 12,
                                  border: "1px solid var(--border)",
                                }}>
                                  <code style={{ color: "var(--text)", fontSize: 11 }}>
                                    {condition.type} {condition.operator}
                                  </code>
                                  <div style={{ 
                                    marginTop: 4,
                                    fontSize: 11,
                                    color: "var(--muted)",
                                    wordBreak: "break-word",
                                  }}>
                                    "{condition.value}"
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Ações */}
                        {stage.actions && stage.actions.length > 0 && (
                          <div style={{ gridColumn: "1 / -1" }}>
                            <div style={{ 
                              fontSize: 11, 
                              color: "var(--muted)", 
                              marginBottom: 10, 
                              fontWeight: 600,
                              textTransform: "uppercase",
                              letterSpacing: "0.5px",
                            }}>
                              🎬 Ações
                            </div>
                            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))" }}>
                              {stage.actions.map((action, idx) => (
                                <div key={idx} style={{ 
                                  padding: 12,
                                  background: "var(--panel)",
                                  borderRadius: 8,
                                  fontSize: 12,
                                  border: "1px solid var(--border)",
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  gap: 12,
                                }}>
                                  <div>
                                    <code style={{ 
                                      color: "var(--text)", 
                                      fontSize: 11,
                                      fontWeight: 600,
                                    }}>
                                      {action.type}
                                    </code>
                                    <div style={{ 
                                      marginTop: 4,
                                      fontSize: 11,
                                      color: "var(--muted)",
                                      wordBreak: "break-word",
                                    }}>
                                      {action.value}
                                    </div>
                                  </div>
                                  {action.delay_seconds && (
                                    <span style={{ 
                                      fontSize: 11, 
                                      color: "var(--muted)",
                                      whiteSpace: "nowrap",
                                      padding: "4px 8px",
                                      background: "var(--bg)",
                                      borderRadius: 6,
                                      fontWeight: 500,
                                    }}>
                                      +{action.delay_seconds}s
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modal de Edição de Funil */}
      {editingFunnel && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0, 0, 0, 0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
          padding: isMobile ? 16 : 24,
        }} onClick={handleCancelEdit}>
          <div 
            className="card" 
            style={{ 
              maxWidth: 600, 
              width: "100%",
              maxHeight: "90vh",
              overflow: "auto",
              padding: isMobile ? 16 : 24,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: isMobile ? 18 : 20 }}>Editar Funil</h3>
              <button 
                className="btn soft" 
                onClick={handleCancelEdit}
                style={{ padding: "6px 10px" }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gap: 16 }}>
              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                  Nome do Funil
                </label>
                <input
                  type="text"
                  className="input"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  style={{ width: "100%" }}
                  placeholder="Nome do funil"
                />
              </div>

              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                  Descrição
                </label>
                <textarea
                  className="input"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  style={{ width: "100%", minHeight: 80, fontFamily: "inherit" }}
                  placeholder="Descrição do funil"
                />
              </div>

              <div>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={editIsActive}
                    onChange={(e) => setEditIsActive(e.target.checked)}
                    style={{ cursor: "pointer" }}
                  />
                  <span>Funil ativo</span>
                </label>
              </div>

              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 8 }}>
                <button className="btn soft" onClick={handleCancelEdit}>
                  Cancelar
                </button>
                <button className="btn" onClick={handleSaveFunnel}>
                  Salvar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

