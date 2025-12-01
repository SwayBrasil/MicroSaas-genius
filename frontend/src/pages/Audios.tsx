// frontend/src/pages/Audios.tsx
import React, { useState, useEffect } from "react";
import { INITIAL_AUDIOS } from "../data/audios";
import type { Audio } from "../types/funnel";

export default function Audios() {
  const [audios, setAudios] = useState<Audio[]>(INITIAL_AUDIOS);
  const [search, setSearch] = useState("");
  const [filterFunnel, setFilterFunnel] = useState<string>("all");
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [editingAudio, setEditingAudio] = useState<Audio | null>(null);
  const [editDisplayName, setEditDisplayName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editContext, setEditContext] = useState("");

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const filtered = audios.filter((a) => {
    const matchesSearch =
      !search ||
      a.display_name.toLowerCase().includes(search.toLowerCase()) ||
      a.code_name.toLowerCase().includes(search.toLowerCase()) ||
      a.filename_whatsapp.toLowerCase().includes(search.toLowerCase());
    const matchesFunnel = filterFunnel === "all" || a.funnel_type === filterFunnel;
    return matchesSearch && matchesFunnel;
  });

  const funnelTypes = Array.from(new Set(audios.map((a) => a.funnel_type)));

  function getFunnelDisplayName(type: string) {
    const map: Record<string, string> = {
      life_funil_longo: "Funil Longo (LIFE)",
      life_mini_funil_bf: "Mini Funil Black Friday",
      life_recuperacao_50: "Recuperação 50%",
      custom: "Personalizado",
    };
    return map[type] || type;
  }

  function handleEditAudio(audio: Audio) {
    setEditingAudio(audio);
    setEditDisplayName(audio.display_name);
    setEditDescription(audio.description || "");
    setEditContext(audio.context || "");
  }

  function handleSaveAudio() {
    if (!editingAudio) return;
    
    const updated = {
      ...editingAudio,
      display_name: editDisplayName,
      description: editDescription,
      context: editContext,
    };
    
    setAudios(audios.map(a => a.id === editingAudio.id ? updated : a));
    setEditingAudio(null);
    setEditDisplayName("");
    setEditDescription("");
    setEditContext("");
  }

  function handleCancelEdit() {
    setEditingAudio(null);
    setEditDisplayName("");
    setEditDescription("");
    setEditContext("");
  }

  return (
    <div style={{ 
      height: "calc(100vh - 56px)", 
      maxHeight: "calc(100vh - 56px)",
      display: "grid", 
      gridTemplateRows: "auto 1fr",
      overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{ 
        borderBottom: "1px solid var(--border)", 
        background: "var(--panel)", 
        padding: isMobile ? "8px 10px" : "10px 12px", 
        display: "flex", 
        gap: isMobile ? 6 : 8, 
        alignItems: "center",
        flexWrap: isMobile ? "wrap" : "nowrap",
      }}>
        <strong style={{ fontSize: isMobile ? 14 : 16 }}>Áudios</strong>
        <input
          className="input"
          placeholder={isMobile ? "Buscar..." : "Buscar áudio (nome, código, arquivo)..."}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ 
            maxWidth: isMobile ? "100%" : 360,
            fontSize: isMobile ? 14 : 16,
            flex: isMobile ? "1 1 100%" : "auto",
          }}
        />
        <select 
          className="select select--sm" 
          value={filterFunnel} 
          onChange={(e) => setFilterFunnel(e.target.value)}
          style={{ 
            fontSize: isMobile ? 13 : 14,
            flex: isMobile ? "1 1 calc(50% - 3px)" : "auto",
          }}
        >
          <option value="all">Todos os funis</option>
          {funnelTypes.map((type) => (
            <option key={type} value={type}>
              {getFunnelDisplayName(type)}
            </option>
          ))}
        </select>
        <div style={{ 
          marginLeft: isMobile ? 0 : "auto", 
          color: "var(--muted)",
          width: isMobile ? "100%" : "auto",
          marginTop: isMobile ? 4 : 0,
        }} className="small">
          {filtered.length} áudio(s)
        </div>
      </div>

      {/* Lista */}
      <div style={{ overflow: "auto", padding: isMobile ? 8 : 12 }}>
        {filtered.length === 0 ? (
          <div className="card" style={{ padding: 16, textAlign: "center", color: "var(--muted)" }}>
            <div className="small">Nenhum áudio encontrado.</div>
          </div>
        ) : (
          <div style={{ display: "grid", gap: isMobile ? 8 : 12 }}>
            {filtered.map((audio) => (
              <div key={audio.id} className="card" style={{ padding: isMobile ? 12 : 16 }}>
                <div style={{ display: "grid", gap: isMobile ? 8 : 12 }}>
                  {/* Header do card */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, flexWrap: "wrap" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ 
                        fontWeight: 600, 
                        fontSize: isMobile ? 15 : 16,
                        marginBottom: 4,
                        color: "var(--text)",
                      }}>
                        🎵 {audio.display_name}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--muted)", fontFamily: "monospace" }}>
                        {audio.code_name}
                      </div>
                    </div>
                    <span className="chip" style={{ 
                      fontSize: isMobile ? 10 : 11,
                      padding: isMobile ? "4px 8px" : "6px 10px",
                    }}>
                      {getFunnelDisplayName(audio.funnel_type)}
                    </span>
                  </div>

                  {/* Arquivo WhatsApp */}
                  <div style={{ 
                    padding: isMobile ? 8 : 10,
                    background: "var(--bg)",
                    borderRadius: 8,
                    border: "1px solid var(--border)",
                  }}>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                      Arquivo WhatsApp:
                    </div>
                    <code style={{ fontSize: 12, color: "var(--text)", wordBreak: "break-all" }}>
                      {audio.filename_whatsapp}
                    </code>
                  </div>

                  {/* Descrição */}
                  {audio.description && (
                    <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
                      {audio.description}
                    </div>
                  )}

                  {/* Contexto */}
                  {audio.context && (
                    <div style={{ 
                      padding: isMobile ? 8 : 10,
                      background: "var(--soft)",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "var(--muted)",
                      fontStyle: "italic",
                    }}>
                      💡 {audio.context}
                    </div>
                  )}

                  {/* Metadados */}
                  <div style={{ 
                    display: "flex", 
                    gap: isMobile ? 8 : 12,
                    flexWrap: "wrap",
                    fontSize: 11,
                    color: "var(--muted)",
                  }}>
                    {audio.stage_order && (
                      <span>Etapa: {audio.stage_order}</span>
                    )}
                    {audio.duration_seconds && (
                      <span>Duração: {audio.duration_seconds}s</span>
                    )}
                  </div>

                  {/* Ações */}
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {audio.file_url && (
                      <a
                        href={audio.file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn soft"
                        style={{ fontSize: isMobile ? 12 : 13, padding: isMobile ? "6px 10px" : "8px 12px" }}
                      >
                        ▶️ Reproduzir
                      </a>
                    )}
                    <button
                      className="btn soft"
                      style={{ fontSize: isMobile ? 12 : 13, padding: isMobile ? "6px 10px" : "8px 12px" }}
                      onClick={() => handleEditAudio(audio)}
                    >
                      ✏️ Editar
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal de Edição de Áudio */}
      {editingAudio && (
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
              <h3 style={{ margin: 0, fontSize: isMobile ? 18 : 20 }}>Editar Áudio</h3>
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
                  Nome de Exibição
                </label>
                <input
                  type="text"
                  className="input"
                  value={editDisplayName}
                  onChange={(e) => setEditDisplayName(e.target.value)}
                  style={{ width: "100%" }}
                  placeholder="Nome do áudio"
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
                  placeholder="Descrição do áudio"
                />
              </div>

              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
                  Contexto de Uso
                </label>
                <textarea
                  className="input"
                  value={editContext}
                  onChange={(e) => setEditContext(e.target.value)}
                  style={{ width: "100%", minHeight: 80, fontFamily: "inherit" }}
                  placeholder="Contexto de quando usar este áudio"
                />
              </div>

              <div style={{ 
                padding: 12, 
                background: "var(--bg)", 
                borderRadius: 8, 
                border: "1px solid var(--border)",
                fontSize: 12,
                color: "var(--muted)",
              }}>
                <div style={{ marginBottom: 4, fontWeight: 500 }}>Informações do arquivo:</div>
                <div style={{ fontFamily: "monospace", fontSize: 11, wordBreak: "break-all" }}>
                  {editingAudio.filename_whatsapp}
                </div>
                <div style={{ marginTop: 8, fontFamily: "monospace", fontSize: 11 }}>
                  Code name: {editingAudio.code_name}
                </div>
                {editingAudio.file_url && (
                  <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 11 }}>
                    URL: {editingAudio.file_url}
                  </div>
                )}
              </div>

              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 8 }}>
                <button className="btn soft" onClick={handleCancelEdit}>
                  Cancelar
                </button>
                <button className="btn" onClick={handleSaveAudio}>
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

