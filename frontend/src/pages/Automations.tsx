// frontend/src/pages/Automations.tsx
import React, { useState, useEffect } from "react";
import { INITIAL_FUNNELS } from "../data/funnels";
import { INITIAL_AUDIOS, TEXT_TEMPLATES } from "../data/audios";
import type { Funnel, FunnelStage } from "../types/funnel";

export default function Automations() {
  const [funnels, setFunnels] = useState<Funnel[]>(INITIAL_FUNNELS);
  const [selectedFunnel, setSelectedFunnel] = useState<Funnel | null>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [editingFunnel, setEditingFunnel] = useState<Funnel | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editIsActive, setEditIsActive] = useState(false);
  const [editingStage, setEditingStage] = useState<FunnelStage | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [syncStatus, setSyncStatus] = useState<"synced" | "unsynced" | "syncing">("synced");

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

  function getAudioDetails(audioId?: number | string | null) {
    if (!audioId) return null;
    return INITIAL_AUDIOS.find((a) => a.id === audioId);
  }

  function getTextTemplateName(templateId?: string | null) {
    if (!templateId) return null;
    // Pode ter múltiplos templates separados por |
    const templates = templateId.split("|");
    return templates.map(t => {
      const template = (TEXT_TEMPLATES as any)[t.trim()];
      return template?.display_name || t.trim();
    }).join(" ou ");
  }

  function formatConditionValue(condition: any) {
    if (condition.type === "time_elapsed") {
      const seconds = parseInt(condition.value);
      if (seconds < 60) return `${seconds} segundos`;
      if (seconds < 3600) return `${Math.floor(seconds / 60)} minutos`;
      return `${Math.floor(seconds / 3600)} hora(s)`;
    }
    if (condition.type === "user_message_contains" || condition.type === "user_message_intent") {
      // Separa valores múltiplos por |
      return condition.value.split("|").map((v: string) => `"${v.trim()}"`).join(" ou ");
    }
    return condition.value;
  }

  function formatActionValue(action: any) {
    if (action.type === "send_link") {
      const links = action.value.split("|");
      return links.map((link: string) => link.trim()).join(" ou ");
    }
    if (action.type === "send_text") {
      const template = (TEXT_TEMPLATES as any)[action.value];
      return template?.display_name || action.value;
    }
    return action.value;
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
    setHasChanges(false);
    setSyncStatus("synced");
  }

  function handleEditStage(stage: FunnelStage) {
    setEditingStage(stage);
  }

  function handleAddStage() {
    if (!editingFunnel) return;
    const newStage: FunnelStage = {
      id: Date.now(),
      funnel_id: editingFunnel.id,
      name: "Nova Etapa",
      order: editingFunnel.stages.length + 1,
      phase: "frio",
      conditions: [],
      actions: [],
    };
    const updatedFunnel = {
      ...editingFunnel,
      stages: [...editingFunnel.stages, newStage],
    };
    setEditingFunnel(updatedFunnel);
    setHasChanges(true);
    setSyncStatus("unsynced");
  }

  function handleDeleteStage(stageId: number | string) {
    if (!editingFunnel) return;
    if (!confirm("Tem certeza que deseja remover esta etapa?")) return;
    const updatedFunnel = {
      ...editingFunnel,
      stages: editingFunnel.stages.filter(s => s.id !== stageId).map((s, idx) => ({ ...s, order: idx + 1 })),
    };
    setEditingFunnel(updatedFunnel);
    setHasChanges(true);
    setSyncStatus("unsynced");
  }

  function handleMoveStage(stageId: number | string, direction: "up" | "down") {
    if (!editingFunnel) return;
    const stages = [...editingFunnel.stages];
    const index = stages.findIndex(s => s.id === stageId);
    if (index === -1) return;
    
    if (direction === "up" && index === 0) return;
    if (direction === "down" && index === stages.length - 1) return;
    
    const newIndex = direction === "up" ? index - 1 : index + 1;
    [stages[index], stages[newIndex]] = [stages[newIndex], stages[index]];
    
    const updatedFunnel = {
      ...editingFunnel,
      stages: stages.map((s, idx) => ({ ...s, order: idx + 1 })),
    };
    setEditingFunnel(updatedFunnel);
    setHasChanges(true);
    setSyncStatus("unsynced");
  }

  function handleUpdateStage(stageId: number | string, updates: Partial<FunnelStage>) {
    if (!editingFunnel) return;
    const updatedStages = editingFunnel.stages.map(s => s.id === stageId ? { ...s, ...updates } : s);
    const updatedFunnel = {
      ...editingFunnel,
      stages: updatedStages,
    };
    setEditingFunnel(updatedFunnel);
    // Atualiza editingStage se estiver editando essa etapa
    if (editingStage && editingStage.id === stageId) {
      const updatedStage = updatedStages.find(s => s.id === stageId);
      if (updatedStage) {
        setEditingStage(updatedStage);
      }
    }
    setHasChanges(true);
    setSyncStatus("unsynced");
  }

  async function handleSaveFunnel() {
    if (!editingFunnel) return;
    
    setSyncStatus("syncing");
    
    // Simula salvamento (por enquanto só no frontend)
    // TODO: Implementar endpoint no backend para salvar alterações
    await new Promise(resolve => setTimeout(resolve, 500));
    
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
    setHasChanges(false);
    setSyncStatus("synced");
    
    // Aviso: alterações são apenas no frontend por enquanto
    alert("⚠️ Atenção: As alterações foram salvas apenas no frontend. Para que a IA use essas configurações, é necessário atualizar o arquivo `funnel_config.json` no backend.");
  }

  function handleExportFunnel() {
    if (!selectedFunnel) return;
    
    const exportData = {
      funnel: selectedFunnel,
      exported_at: new Date().toISOString(),
      note: "Exporte este JSON e atualize o arquivo funnel_config.json no backend para sincronizar com a IA",
    };
    
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `funnel_${selectedFunnel.id}_${selectedFunnel.name.replace(/\s+/g, "_")}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function handleCancelEdit() {
    if (hasChanges && !confirm("Tem certeza que deseja cancelar? As alterações não salvas serão perdidas.")) {
      return;
    }
    setEditingFunnel(null);
    setEditName("");
    setEditDescription("");
    setEditIsActive(false);
    setEditingStage(null);
    setHasChanges(false);
    setSyncStatus("synced");
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
          <button 
            className="btn" 
            style={{ width: "100%", fontSize: isMobile ? 12 : 13 }}
            onClick={() => {
              const newFunnelId = Date.now();
              const newFunnel: Funnel = {
                id: newFunnelId,
                name: "Novo Funil",
                type: "custom",
                description: "Descrição do novo funil",
                is_active: false,
                stages: [
                  {
                    id: newFunnelId * 10 + 1,
                    funnel_id: newFunnelId,
                    name: "Etapa Inicial",
                    order: 1,
                    phase: "frio",
                    conditions: [
                      {
                        type: "user_message_contains",
                        value: "",
                        operator: "contains",
                      },
                    ],
                    actions: [],
                  },
                ],
              };
              setFunnels([...funnels, newFunnel]);
              setSelectedFunnel(newFunnel);
              // Abre o modal de edição automaticamente
              handleEditFunnel(newFunnel);
            }}
          >
            + Novo Funil
          </button>
        </div>

        <div style={{ display: "grid", gap: 10 }}>
          {funnels.map((funnel) => {
            const audioCount = funnel.stages.filter(s => s.audio_id).length;
            const textCount = funnel.stages.filter(s => s.text_template).length;
            
            return (
              <button
                key={funnel.id}
                onClick={() => setSelectedFunnel(funnel)}
                className={selectedFunnel?.id === funnel.id ? "btn" : "btn soft"}
                style={{
                  textAlign: "left",
                  padding: isMobile ? 12 : 14,
                  fontSize: isMobile ? 13 : 14,
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  alignItems: "flex-start",
                  borderRadius: 10,
                }}
              >
                <div style={{ 
                  fontWeight: 600, 
                  fontSize: isMobile ? 14 : 15,
                  marginBottom: 2,
                }}>
                  {funnel.name}
                </div>
                {funnel.description && (
                  <div style={{ 
                    fontSize: 11, 
                    color: "var(--muted)",
                    lineHeight: 1.4,
                    marginBottom: 4,
                  }}>
                    {funnel.description.length > 80 
                      ? funnel.description.substring(0, 80) + "..." 
                      : funnel.description}
                  </div>
                )}
                <div style={{ 
                  display: "flex", 
                  flexWrap: "wrap", 
                  gap: 8,
                  fontSize: 11, 
                  color: "var(--muted)",
                  width: "100%",
                }}>
                  <span>📊 {funnel.stages.length} etapa(s)</span>
                  {audioCount > 0 && <span>🎵 {audioCount} áudio(s)</span>}
                  {textCount > 0 && <span>💬 {textCount} texto(s)</span>}
                  <span style={{ 
                    marginLeft: "auto",
                    fontWeight: 600,
                    color: funnel.is_active ? "#10b981" : "#6b7280",
                  }}>
                    {funnel.is_active ? "✅ Ativo" : "⏸️ Pausado"}
                  </span>
                </div>
              </button>
            );
          })}
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
                    <p style={{ margin: 0, fontSize: 14, color: "var(--muted)", lineHeight: 1.6, marginBottom: 16 }}>
                      {selectedFunnel.description}
                    </p>
                  )}
                  
                  {/* Estatísticas do Funil */}
                  <div style={{ 
                    display: "grid", 
                    gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
                    gap: 12,
                    marginTop: 16,
                  }}>
                    <div style={{ 
                      padding: 12,
                      background: "var(--panel)",
                      borderRadius: 8,
                      border: "1px solid var(--border)",
                    }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                        📊 Etapas
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)" }}>
                        {selectedFunnel.stages.length}
                      </div>
                    </div>
                    <div style={{ 
                      padding: 12,
                      background: "var(--panel)",
                      borderRadius: 8,
                      border: "1px solid var(--border)",
                    }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                        🎵 Áudios
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)" }}>
                        {selectedFunnel.stages.filter(s => s.audio_id).length}
                      </div>
                    </div>
                    <div style={{ 
                      padding: 12,
                      background: "var(--panel)",
                      borderRadius: 8,
                      border: "1px solid var(--border)",
                    }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                        💬 Mensagens
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)" }}>
                        {selectedFunnel.stages.filter(s => s.text_template).length}
                      </div>
                    </div>
                    <div style={{ 
                      padding: 12,
                      background: "var(--panel)",
                      borderRadius: 8,
                      border: "1px solid var(--border)",
                    }}>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                        ⚡ Triggers
                      </div>
                      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)" }}>
                        {selectedFunnel.stages.reduce((acc, s) => acc + (s.conditions?.length || 0), 0)}
                      </div>
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
                  <div style={{ 
                    padding: 8,
                    background: "#fef3c7",
                    border: "1px solid #f59e0b",
                    borderRadius: 8,
                    fontSize: 11,
                    color: "#92400e",
                    maxWidth: 300,
                  }}>
                    <div style={{ fontWeight: 600, marginBottom: 2 }}>
                      ⚠️ Status de Sincronização
                    </div>
                    <div style={{ lineHeight: 1.4 }}>
                      Alterações são apenas no frontend. Para a IA usar, atualize <code style={{ background: "#fde68a", padding: "1px 3px", borderRadius: 3 }}>funnel_config.json</code> no backend.
                    </div>
                  </div>
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
                    onClick={handleExportFunnel}
                    title="Exportar configuração em JSON"
                  >
                    📥 Exportar JSON
                  </button>
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

                      {/* Resumo da Etapa */}
                      <div style={{ 
                        padding: 12,
                        background: "linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(99, 102, 241, 0.05) 100%)",
                        borderRadius: 10,
                        marginBottom: 16,
                        border: "1px solid rgba(99, 102, 241, 0.2)",
                      }}>
                        <div style={{ 
                          fontSize: 12, 
                          fontWeight: 600, 
                          color: "var(--text)",
                          marginBottom: 6,
                        }}>
                          📋 O que acontece nesta etapa:
                        </div>
                        <div style={{ 
                          fontSize: 13, 
                          color: "var(--text)",
                          lineHeight: 1.6,
                        }}>
                          {(() => {
                            const parts: string[] = [];
                            if (stage.audio_id) {
                              const audio = getAudioDetails(stage.audio_id);
                              parts.push(`🎵 Envia áudio "${audio?.display_name || getAudioName(stage.audio_id)}"`);
                            }
                            if (stage.text_template) {
                              parts.push(`💬 Envia mensagem de texto`);
                            }
                            if (stage.actions && stage.actions.length > 0) {
                              const actionTypes = stage.actions.map(a => {
                                if (a.type === "send_link") return "🔗 link de compra";
                                if (a.type === "send_text") return "💬 texto";
                                if (a.type === "send_image") return "🖼️ imagem";
                                return a.type;
                              });
                              parts.push(`🎬 Executa: ${actionTypes.join(", ")}`);
                            }
                            if (stage.conditions && stage.conditions.length > 0) {
                              const conditionTypes = stage.conditions.map(c => {
                                if (c.type === "user_message_contains") return "mensagem do usuário";
                                if (c.type === "time_elapsed") return "tempo decorrido";
                                if (c.type === "external_webhook") return "evento externo";
                                return c.type;
                              });
                              parts.push(`⚡ Quando: ${conditionTypes.join(" ou ")}`);
                            }
                            return parts.length > 0 ? parts.join(" • ") : "Sem ações configuradas";
                          })()}
                        </div>
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
                          {/* Áudio - Detalhado */}
                          {stage.audio_id && (() => {
                            const audioDetails = getAudioDetails(stage.audio_id);
                            return (
                              <div style={{ 
                                padding: 16,
                                background: "linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(37, 99, 235, 0.03) 100%)",
                                borderRadius: 12,
                                border: "1px solid rgba(37, 99, 235, 0.2)",
                              }}>
                                <div style={{ 
                                  fontSize: 11, 
                                  color: "var(--muted)", 
                                  marginBottom: 8,
                                  fontWeight: 600,
                                  textTransform: "uppercase",
                                  letterSpacing: "0.5px",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 6,
                                }}>
                                  🎵 Áudio Enviado
                                </div>
                                <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)", marginBottom: 8 }}>
                                  {getAudioName(stage.audio_id)}
                                </div>
                                {audioDetails?.description && (
                                  <div style={{ 
                                    fontSize: 13, 
                                    color: "var(--text)", 
                                    marginBottom: 8,
                                    lineHeight: 1.5,
                                  }}>
                                    {audioDetails.description}
                                  </div>
                                )}
                                {audioDetails?.context && (
                                  <div style={{ 
                                    padding: 10,
                                    background: "rgba(37, 99, 235, 0.05)",
                                    borderRadius: 8,
                                    fontSize: 12,
                                    color: "var(--muted)",
                                    borderLeft: "3px solid rgba(37, 99, 235, 0.3)",
                                    marginTop: 8,
                                  }}>
                                    <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--text)" }}>
                                      📍 Quando dispara:
                                    </div>
                                    {audioDetails.context}
                                  </div>
                                )}
                              </div>
                            );
                          })()}

                          {/* Template de texto - Detalhado */}
                          {stage.text_template && (() => {
                            const templateNames = getTextTemplateName(stage.text_template);
                            const templates = stage.text_template.split("|").map(t => (TEXT_TEMPLATES as any)[t.trim()]).filter(Boolean);
                            return (
                              <div style={{ 
                                padding: 16,
                                background: "linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.03) 100%)",
                                borderRadius: 12,
                                border: "1px solid rgba(16, 185, 129, 0.2)",
                              }}>
                                <div style={{ 
                                  fontSize: 11, 
                                  color: "var(--muted)", 
                                  marginBottom: 8,
                                  fontWeight: 600,
                                  textTransform: "uppercase",
                                  letterSpacing: "0.5px",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 6,
                                }}>
                                  💬 Mensagem de Texto
                                </div>
                                <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text)", marginBottom: 8 }}>
                                  {templateNames || stage.text_template}
                                </div>
                                {templates.length > 0 && templates[0]?.text && (
                                  <div style={{ 
                                    fontSize: 13, 
                                    color: "var(--text)", 
                                    marginBottom: 8,
                                    lineHeight: 1.5,
                                    fontStyle: "italic",
                                  }}>
                                    "{templates[0].text}"
                                  </div>
                                )}
                                {templates.length > 0 && templates[0]?.images && templates[0].images.length > 0 && (
                                  <div style={{ 
                                    padding: 10,
                                    background: "rgba(16, 185, 129, 0.05)",
                                    borderRadius: 8,
                                    fontSize: 12,
                                    color: "var(--muted)",
                                    marginTop: 8,
                                  }}>
                                    <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--text)" }}>
                                      🖼️ Imagens enviadas: {templates[0].images.length}
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })()}

                        {/* Condições - Melhoradas */}
                        {stage.conditions && stage.conditions.length > 0 && (
                          <div style={{ gridColumn: "1 / -1", marginTop: 4 }}>
                            <div style={{ 
                              fontSize: 12, 
                              color: "var(--text)", 
                              marginBottom: 12, 
                              fontWeight: 600,
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                            }}>
                              <span>⚡</span>
                              <span>Mensagens Esperadas / Triggers</span>
                            </div>
                            <div style={{ display: "grid", gap: 10 }}>
                              {stage.conditions.map((condition, idx) => {
                                const conditionTypeLabels: Record<string, string> = {
                                  "user_message_contains": "Usuário escreve",
                                  "user_message_intent": "Usuário demonstra intenção",
                                  "time_elapsed": "Tempo decorrido",
                                  "external_webhook": "Evento externo",
                                  "user_choice": "Usuário escolhe",
                                };
                                
                                const operatorLabels: Record<string, string> = {
                                  "contains": "contém",
                                  "equals": "igual a",
                                  "greater_than": "maior que",
                                };

                                return (
                                  <div key={idx} style={{ 
                                    padding: 14,
                                    background: "var(--bg)",
                                    borderRadius: 10,
                                    border: "2px solid var(--border)",
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 8,
                                  }}>
                                    <div style={{ 
                                      display: "flex", 
                                      alignItems: "center", 
                                      gap: 8,
                                      flexWrap: "wrap",
                                    }}>
                                      <span style={{ 
                                        fontSize: 11,
                                        fontWeight: 600,
                                        color: "var(--muted)",
                                        textTransform: "uppercase",
                                        letterSpacing: "0.5px",
                                      }}>
                                        {conditionTypeLabels[condition.type] || condition.type}
                                      </span>
                                      {condition.operator && (
                                        <span style={{ 
                                          fontSize: 11,
                                          color: "var(--muted)",
                                        }}>
                                          {operatorLabels[condition.operator] || condition.operator}
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ 
                                      padding: 10,
                                      background: "var(--panel)",
                                      borderRadius: 8,
                                      fontSize: 13,
                                      color: "var(--text)",
                                      fontWeight: 500,
                                      lineHeight: 1.5,
                                      borderLeft: "3px solid var(--primary-color)",
                                    }}>
                                      {formatConditionValue(condition)}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Ações - Melhoradas */}
                        {stage.actions && stage.actions.length > 0 && (
                          <div style={{ gridColumn: "1 / -1", marginTop: 4 }}>
                            <div style={{ 
                              fontSize: 12, 
                              color: "var(--text)", 
                              marginBottom: 12, 
                              fontWeight: 600,
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                            }}>
                              <span>🎬</span>
                              <span>Ações Executadas</span>
                            </div>
                            <div style={{ display: "grid", gap: 10 }}>
                              {stage.actions.map((action, idx) => {
                                const actionTypeLabels: Record<string, string> = {
                                  "send_text": "📝 Enviar Texto",
                                  "send_link": "🔗 Enviar Link",
                                  "send_image": "🖼️ Enviar Imagem",
                                  "update_stage": "🔄 Atualizar Etapa",
                                };

                                return (
                                  <div key={idx} style={{ 
                                    padding: 14,
                                    background: "var(--bg)",
                                    borderRadius: 10,
                                    border: "2px solid var(--border)",
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 8,
                                  }}>
                                    <div style={{ 
                                      display: "flex", 
                                      alignItems: "center", 
                                      justifyContent: "space-between",
                                      flexWrap: "wrap",
                                      gap: 8,
                                    }}>
                                      <span style={{ 
                                        fontSize: 13,
                                        fontWeight: 600,
                                        color: "var(--text)",
                                      }}>
                                        {actionTypeLabels[action.type] || action.type}
                                      </span>
                                      {action.delay_seconds && action.delay_seconds > 0 && (
                                        <span style={{ 
                                          fontSize: 11, 
                                          color: "var(--muted)",
                                          whiteSpace: "nowrap",
                                          padding: "4px 10px",
                                          background: "var(--panel)",
                                          borderRadius: 6,
                                          fontWeight: 500,
                                        }}>
                                          ⏱️ Aguarda {action.delay_seconds}s
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ 
                                      padding: 10,
                                      background: "var(--panel)",
                                      borderRadius: 8,
                                      fontSize: 13,
                                      color: "var(--text)",
                                      lineHeight: 1.5,
                                      borderLeft: "3px solid #10b981",
                                      wordBreak: "break-word",
                                    }}>
                                      {formatActionValue(action)}
                                    </div>
                                  </div>
                                );
                              })}
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

      {/* Modal de Edição de Condições e Ações */}
      {editingStage && editingFunnel && (
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
          zIndex: 1001,
          padding: isMobile ? 16 : 24,
        }} onClick={() => setEditingStage(null)}>
          <div 
            className="card" 
            style={{ 
              maxWidth: 700, 
              width: "100%",
              maxHeight: "90vh",
              overflow: "auto",
              padding: isMobile ? 16 : 24,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: isMobile ? 18 : 20 }}>
                Editar Etapa: {editingStage.name}
              </h3>
              <button 
                className="btn soft" 
                onClick={() => setEditingStage(null)}
                style={{ padding: "6px 10px" }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gap: 20 }}>
              {/* Informação sobre condições */}
              <div style={{ 
                padding: 10,
                background: "rgba(37, 99, 235, 0.1)",
                borderRadius: 8,
                fontSize: 11,
                color: "var(--text)",
                lineHeight: 1.5,
              }}>
                <strong>💡 Sobre Condições:</strong> Quando TODAS as condições forem verdadeiras, a etapa será acionada. 
                Use múltiplas condições para criar triggers mais específicos.
              </div>

              {/* Condições */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <label style={{ fontSize: 13, fontWeight: 500 }}>
                    ⚡ Condições / Triggers ({(editingStage.conditions || []).length})
                  </label>
                  <button 
                    className="btn soft" 
                    onClick={() => {
                      const newCondition: StageCondition = {
                        type: "user_message_contains",
                        value: "",
                        operator: "contains",
                      };
                      handleUpdateStage(editingStage.id, {
                        conditions: [...(editingStage.conditions || []), newCondition],
                      });
                    }}
                    style={{ fontSize: 12, padding: "6px 12px" }}
                  >
                    + Adicionar Condição
                  </button>
                </div>
                
                <div style={{ display: "grid", gap: 10 }}>
                  {(editingStage.conditions || []).map((condition, idx) => (
                    <div key={idx} style={{ 
                      padding: 14,
                      background: "var(--panel)",
                      borderRadius: 10,
                      border: "1px solid var(--border)",
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr 1fr auto",
                      gap: 10,
                      alignItems: "center",
                    }}>
                      <select
                        className="select"
                        value={condition.type}
                        onChange={(e) => {
                          const updated = [...(editingStage.conditions || [])];
                          updated[idx] = { ...updated[idx], type: e.target.value as any };
                          handleUpdateStage(editingStage.id, { conditions: updated });
                        }}
                        style={{ fontSize: 12, padding: "6px 10px" }}
                      >
                        <option value="user_message_contains">Usuário escreve</option>
                        <option value="user_message_intent">Usuário demonstra intenção</option>
                        <option value="time_elapsed">Tempo decorrido</option>
                        <option value="external_webhook">Evento externo</option>
                        <option value="user_choice">Usuário escolhe</option>
                      </select>
                      
                      <select
                        className="select"
                        value={condition.operator || "contains"}
                        onChange={(e) => {
                          const updated = [...(editingStage.conditions || [])];
                          updated[idx] = { ...updated[idx], operator: e.target.value as any };
                          handleUpdateStage(editingStage.id, { conditions: updated });
                        }}
                        style={{ fontSize: 12, padding: "6px 10px" }}
                      >
                        <option value="contains">contém</option>
                        <option value="equals">igual a</option>
                        <option value="greater_than">maior que</option>
                        <option value="less_than">menor que</option>
                      </select>
                      
                      <input
                        type="text"
                        className="input"
                        value={condition.value}
                        onChange={(e) => {
                          const updated = [...(editingStage.conditions || [])];
                          updated[idx] = { ...updated[idx], value: e.target.value };
                          handleUpdateStage(editingStage.id, { conditions: updated });
                        }}
                        style={{ fontSize: 12, padding: "6px 10px" }}
                        placeholder="Valor (ex: 'quero saber' ou '3600')"
                      />
                      
                      <button
                        className="btn soft"
                        onClick={() => {
                          const updated = editingStage.conditions?.filter((_, i) => i !== idx) || [];
                          handleUpdateStage(editingStage.id, { conditions: updated });
                        }}
                        style={{ padding: "6px 10px", color: "#dc2626" }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  {(!editingStage.conditions || editingStage.conditions.length === 0) && (
                    <div style={{ 
                      padding: 20,
                      textAlign: "center",
                      color: "var(--muted)",
                      fontSize: 13,
                    }}>
                      Nenhuma condição configurada
                    </div>
                  )}
                </div>
              </div>

              {/* Informação sobre ações */}
              <div style={{ 
                padding: 10,
                background: "rgba(16, 185, 129, 0.1)",
                borderRadius: 8,
                fontSize: 11,
                color: "var(--text)",
                lineHeight: 1.5,
              }}>
                <strong>💡 Sobre Ações:</strong> As ações são executadas na ordem em que aparecem. 
                Use "delay_seconds" para criar pausas entre ações (útil para evitar spam no WhatsApp).
              </div>

              {/* Ações */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <label style={{ fontSize: 13, fontWeight: 500 }}>
                    🎬 Ações Executadas ({(editingStage.actions || []).length})
                  </label>
                  <button 
                    className="btn soft" 
                    onClick={() => {
                      const newAction: StageAction = {
                        type: "send_text",
                        value: "",
                        delay_seconds: 0,
                      };
                      handleUpdateStage(editingStage.id, {
                        actions: [...(editingStage.actions || []), newAction],
                      });
                    }}
                    style={{ fontSize: 12, padding: "6px 12px" }}
                  >
                    + Adicionar Ação
                  </button>
                </div>
                
                <div style={{ display: "grid", gap: 10 }}>
                  {(editingStage.actions || []).map((action, idx) => (
                    <div key={idx} style={{ 
                      padding: 14,
                      background: "var(--panel)",
                      borderRadius: 10,
                      border: "1px solid var(--border)",
                      display: "grid",
                      gridTemplateColumns: "1fr 2fr 100px auto",
                      gap: 10,
                      alignItems: "center",
                    }}>
                      <select
                        className="select"
                        value={action.type}
                        onChange={(e) => {
                          const updated = [...(editingStage.actions || [])];
                          updated[idx] = { ...updated[idx], type: e.target.value as any };
                          handleUpdateStage(editingStage.id, { actions: updated });
                        }}
                        style={{ fontSize: 12, padding: "6px 10px" }}
                      >
                        <option value="send_text">Enviar Texto</option>
                        <option value="send_link">Enviar Link</option>
                        <option value="send_image">Enviar Imagem</option>
                        <option value="send_audio">Enviar Áudio</option>
                        <option value="wait">Aguardar</option>
                      </select>
                      
                      <input
                        type="text"
                        className="input"
                        value={action.value}
                        onChange={(e) => {
                          const updated = [...(editingStage.actions || [])];
                          updated[idx] = { ...updated[idx], value: e.target.value };
                          handleUpdateStage(editingStage.id, { actions: updated });
                        }}
                        style={{ fontSize: 12, padding: "6px 10px" }}
                        placeholder="Valor (ex: URL ou template ID)"
                      />
                      
                      <input
                        type="number"
                        className="input"
                        value={action.delay_seconds || 0}
                        onChange={(e) => {
                          const updated = [...(editingStage.actions || [])];
                          updated[idx] = { ...updated[idx], delay_seconds: Number(e.target.value) || 0 };
                          handleUpdateStage(editingStage.id, { actions: updated });
                        }}
                        style={{ fontSize: 12, padding: "6px 10px" }}
                        placeholder="Delay (s)"
                        min={0}
                      />
                      
                      <button
                        className="btn soft"
                        onClick={() => {
                          const updated = editingStage.actions?.filter((_, i) => i !== idx) || [];
                          handleUpdateStage(editingStage.id, { actions: updated });
                        }}
                        style={{ padding: "6px 10px", color: "#dc2626" }}
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  {(!editingStage.actions || editingStage.actions.length === 0) && (
                    <div style={{ 
                      padding: 20,
                      textAlign: "center",
                      color: "var(--muted)",
                      fontSize: 13,
                    }}>
                      Nenhuma ação configurada
                    </div>
                  )}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", paddingTop: 16, borderTop: "1px solid var(--border)" }}>
                <button className="btn" onClick={() => setEditingStage(null)}>
                  Fechar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h3 style={{ margin: "0 0 8px 0", fontSize: isMobile ? 18 : 20 }}>Editar Funil</h3>
                {syncStatus === "unsynced" && (
                  <div style={{ 
                    fontSize: 12, 
                    color: "#f59e0b",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}>
                    ⚠️ Alterações não salvas
                  </div>
                )}
                {syncStatus === "syncing" && (
                  <div style={{ 
                    fontSize: 12, 
                    color: "#3b82f6",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}>
                    🔄 Salvando...
                  </div>
                )}
                {syncStatus === "synced" && !hasChanges && (
                  <div style={{ 
                    fontSize: 12, 
                    color: "#10b981",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}>
                    ✅ Sincronizado (apenas frontend)
                  </div>
                )}
              </div>
              <button 
                className="btn soft" 
                onClick={handleCancelEdit}
                style={{ padding: "6px 10px" }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: "grid", gap: 20 }}>
              {/* Informação sobre sincronização */}
              <div style={{ 
                padding: 14,
                background: "linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)",
                border: "2px solid #f59e0b",
                borderRadius: 10,
                fontSize: 12,
                color: "#92400e",
              }}>
                <div style={{ fontWeight: 700, marginBottom: 8, fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
                  <span>⚠️</span>
                  <span>Sincronização com a IA</span>
                </div>
                <div style={{ lineHeight: 1.6, marginBottom: 8 }}>
                  <strong>Status atual:</strong> As alterações são salvas apenas no frontend (visualização).
                </div>
                <div style={{ lineHeight: 1.6, marginBottom: 8 }}>
                  <strong>Para a IA usar essas configurações:</strong>
                  <ol style={{ margin: "8px 0 0 20px", padding: 0, lineHeight: 1.8 }}>
                    <li>Atualize o arquivo <code style={{ background: "#fbbf24", padding: "2px 6px", borderRadius: 4, fontWeight: 600 }}>api/app/config/funnel_config.json</code> no backend</li>
                    <li>Reinicie o serviço da API para carregar as novas configurações</li>
                    <li>As alterações serão aplicadas em novas conversas</li>
                  </ol>
                </div>
                <div style={{ 
                  padding: 10,
                  background: "rgba(255, 255, 255, 0.5)",
                  borderRadius: 6,
                  fontSize: 11,
                  marginTop: 8,
                }}>
                  <strong>💡 Dica:</strong> Você pode verificar se a IA está usando as configurações observando os logs do backend quando uma conversa é processada. 
                  Procure por mensagens como "Gatilho detectado" ou "Automação executada".
                </div>
              </div>

              {/* Informações básicas */}
              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                  Nome do Funil
                </label>
                <input
                  type="text"
                  className="input"
                  value={editName}
                  onChange={(e) => {
                    setEditName(e.target.value);
                    setHasChanges(true);
                    setSyncStatus("unsynced");
                  }}
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
                  onChange={(e) => {
                    setEditDescription(e.target.value);
                    setHasChanges(true);
                    setSyncStatus("unsynced");
                  }}
                  style={{ width: "100%", minHeight: 80, fontFamily: "inherit" }}
                  placeholder="Descrição do funil"
                />
              </div>

              <div>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={editIsActive}
                    onChange={(e) => {
                      setEditIsActive(e.target.checked);
                      setHasChanges(true);
                      setSyncStatus("unsynced");
                    }}
                    style={{ cursor: "pointer" }}
                  />
                  <span>Funil ativo</span>
                </label>
              </div>

              {/* Lista de Etapas */}
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <label style={{ fontSize: 13, fontWeight: 500 }}>
                    Etapas do Funil ({editingFunnel.stages.length})
                  </label>
                  <button 
                    className="btn soft" 
                    onClick={handleAddStage}
                    style={{ fontSize: 12, padding: "6px 12px" }}
                  >
                    + Adicionar Etapa
                  </button>
                </div>
                
                <div style={{ display: "grid", gap: 12, maxHeight: "400px", overflowY: "auto", padding: "8px 0" }}>
                  {editingFunnel.stages
                    .sort((a, b) => a.order - b.order)
                    .map((stage) => (
                      <div key={stage.id} style={{ 
                        padding: 14,
                        background: "var(--panel)",
                        borderRadius: 10,
                        border: "1px solid var(--border)",
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                      }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                <button
                                  className="btn soft"
                                  onClick={() => handleMoveStage(stage.id, "up")}
                                  disabled={stage.order === 1}
                                  style={{ 
                                    padding: "4px 8px",
                                    fontSize: 11,
                                    opacity: stage.order === 1 ? 0.5 : 1,
                                  }}
                                  title="Mover para cima"
                                >
                                  ↑
                                </button>
                                <button
                                  className="btn soft"
                                  onClick={() => handleMoveStage(stage.id, "down")}
                                  disabled={stage.order === editingFunnel.stages.length}
                                  style={{ 
                                    padding: "4px 8px",
                                    fontSize: 11,
                                    opacity: stage.order === editingFunnel.stages.length ? 0.5 : 1,
                                  }}
                                  title="Mover para baixo"
                                >
                                  ↓
                                </button>
                              </div>
                              <span style={{ 
                                fontSize: 11,
                                fontWeight: 600,
                                color: "var(--muted)",
                                background: "var(--bg)",
                                padding: "4px 8px",
                                borderRadius: 6,
                              }}>
                                Etapa #{stage.order}
                              </span>
                              <input
                                type="text"
                                className="input"
                                value={stage.name}
                                onChange={(e) => handleUpdateStage(stage.id, { name: e.target.value })}
                                style={{ flex: 1, minWidth: 200, fontSize: 13, padding: "6px 10px" }}
                                placeholder="Nome da etapa"
                              />
                            </div>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                              <div>
                                <label style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4, display: "block" }}>
                                  Fase
                                </label>
                                <select
                                  className="select"
                                  value={stage.phase}
                                  onChange={(e) => handleUpdateStage(stage.id, { phase: e.target.value as any })}
                                  style={{ width: "100%", fontSize: 12, padding: "6px 10px" }}
                                >
                                  <option value="frio">❄️ Frio</option>
                                  <option value="aquecimento">🌤️ Aquecimento</option>
                                  <option value="aquecido">🔥 Aquecido</option>
                                  <option value="quente">🔥🔥 Quente</option>
                                  <option value="assinante">✅ Assinante</option>
                                </select>
                              </div>
                              <div>
                                <label style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4, display: "block" }}>
                                  Áudio
                                </label>
                                <select
                                  className="select"
                                  value={stage.audio_id || ""}
                                  onChange={(e) => handleUpdateStage(stage.id, { audio_id: e.target.value ? Number(e.target.value) : null })}
                                  style={{ width: "100%", fontSize: 12, padding: "6px 10px" }}
                                >
                                  <option value="">Nenhum</option>
                                  {INITIAL_AUDIOS.map(audio => (
                                    <option key={audio.id} value={audio.id}>
                                      {audio.display_name}
                                    </option>
                                  ))}
                                </select>
                              </div>
                            </div>
                            <div style={{ marginTop: 8 }}>
                              <label style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4, display: "block" }}>
                                Template de Texto (opcional)
                              </label>
                              <input
                                type="text"
                                className="input"
                                value={stage.text_template || ""}
                                onChange={(e) => handleUpdateStage(stage.id, { text_template: e.target.value || undefined })}
                                style={{ width: "100%", fontSize: 12, padding: "6px 10px" }}
                                placeholder="ID do template (ex: life_funil_longo_planos) ou deixe vazio"
                              />
                              <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 4 }}>
                                Use | para múltiplos templates (ex: template1|template2)
                              </div>
                            </div>
                          </div>
                          <button
                            className="btn soft"
                            onClick={() => handleDeleteStage(stage.id)}
                            style={{ 
                              padding: "6px 10px",
                              fontSize: 12,
                              color: "#dc2626",
                              flexShrink: 0,
                            }}
                            title="Remover etapa"
                          >
                            ✕
                          </button>
                        </div>
                        
                        {/* Botão para editar condições e ações */}
                        <button
                          className="btn soft"
                          onClick={() => setEditingStage(stage)}
                          style={{ fontSize: 12, padding: "8px 12px", width: "100%" }}
                        >
                          ⚙️ Editar Condições e Ações
                        </button>
                      </div>
                    ))}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, justifyContent: "space-between", marginTop: 8, paddingTop: 16, borderTop: "1px solid var(--border)", flexWrap: "wrap" }}>
                <button 
                  className="btn soft" 
                  onClick={() => {
                    if (!editingFunnel) return;
                    const exportData = {
                      funnel: {
                        ...editingFunnel,
                        name: editName,
                        description: editDescription,
                        is_active: editIsActive,
                      },
                      exported_at: new Date().toISOString(),
                    };
                    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `funnel_${editingFunnel.id}_${editName.replace(/\s+/g, "_")}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                  }}
                  style={{ fontSize: 12, padding: "8px 14px" }}
                >
                  📥 Exportar JSON
                </button>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn soft" onClick={handleCancelEdit}>
                    Cancelar
                  </button>
                  <button 
                    className="btn" 
                    onClick={handleSaveFunnel}
                    disabled={syncStatus === "syncing"}
                    style={{ opacity: syncStatus === "syncing" ? 0.6 : 1 }}
                  >
                    {syncStatus === "syncing" ? "Salvando..." : "Salvar Alterações"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

