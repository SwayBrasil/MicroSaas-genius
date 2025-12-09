// frontend/src/pages/Integrations.tsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

type Integration = {
  name: string;
  enabled: boolean;
  configured: boolean;
  status: "active" | "inactive" | "error";
  last_event_at: string | null;
  total_events: number;
  config: {
    webhook_url?: string;
    base_url?: string;
    description: string;
    [key: string]: any;
  };
};

type IntegrationsResponse = {
  integrations: Integration[];
  summary: {
    total: number;
    active: number;
    configured: number;
  };
};

type RecentEvent = {
  id: number;
  source: string;
  event: string;
  order_id: string | null;
  buyer_email: string;
  value: number | null;
  created_at: string;
  contact_id: number | null;
};

export default function Integrations() {
  const navigate = useNavigate();
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [summary, setSummary] = useState({ total: 0, active: 0, configured: 0 });
  const [recentEvents, setRecentEvents] = useState<RecentEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadIntegrations();
    loadRecentEvents();
  }, []);

  async function loadIntegrations() {
    try {
      setLoading(true);
      setError(null);
      const { data } = await api.get<IntegrationsResponse>("/integrations/status");
      setIntegrations(data.integrations);
      setSummary(data.summary);
    } catch (err: any) {
      console.error("Erro ao carregar integrações:", err);
      setError(err?.response?.data?.detail || "Erro ao carregar integrações");
    } finally {
      setLoading(false);
    }
  }

  async function loadRecentEvents() {
    try {
      setLoadingEvents(true);
      const { data } = await api.get<RecentEvent[]>("/integrations/events/recent?limit=10");
      setRecentEvents(data);
    } catch (err) {
      console.error("Erro ao carregar eventos:", err);
    } finally {
      setLoadingEvents(false);
    }
  }

  function getStatusColor(status: string) {
    switch (status) {
      case "active":
        return { bg: "rgba(34, 197, 94, 0.15)", color: "#22c55e", icon: "✅" };
      case "inactive":
        return { bg: "rgba(156, 163, 175, 0.15)", color: "#9ca3af", icon: "⚪" };
      case "error":
        return { bg: "rgba(239, 68, 68, 0.15)", color: "#ef4444", icon: "❌" };
      default:
        return { bg: "var(--panel)", color: "var(--muted)", icon: "❓" };
    }
  }

  function formatDate(dateStr: string | null) {
    if (!dateStr) return "Nunca";
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return "Agora";
      if (diffMins < 60) return `${diffMins} min atrás`;
      if (diffHours < 24) return `${diffHours}h atrás`;
      if (diffDays < 7) return `${diffDays}d atrás`;
      return date.toLocaleDateString("pt-BR");
    } catch {
      return dateStr;
    }
  }

  function copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      alert("Copiado para a área de transferência!");
    });
  }

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <div>Carregando integrações...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <div style={{ color: "var(--danger)", marginBottom: 16 }}>Erro: {error}</div>
        <button className="btn" onClick={loadIntegrations}>
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 1400, margin: "0 auto" }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ margin: "0 0 8px 0" }}>Integrações</h1>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          Gerencie e monitore suas integrações com plataformas externas
        </p>
      </div>

      {/* Resumo */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 16,
          marginBottom: 32,
        }}
      >
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontSize: 14, color: "var(--muted)", marginBottom: 8 }}>Total</div>
          <div style={{ fontSize: 32, fontWeight: 700 }}>{summary.total}</div>
        </div>
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontSize: 14, color: "var(--muted)", marginBottom: 8 }}>Ativas</div>
          <div style={{ fontSize: 32, fontWeight: 700, color: "#22c55e" }}>{summary.active}</div>
        </div>
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontSize: 14, color: "var(--muted)", marginBottom: 8 }}>Configuradas</div>
          <div style={{ fontSize: 32, fontWeight: 700 }}>{summary.configured}</div>
        </div>
      </div>

      {/* Lista de Integrações */}
      <div style={{ display: "grid", gap: 20, marginBottom: 32 }}>
        {integrations.map((integration) => {
          const statusStyle = getStatusColor(integration.status);
          return (
            <div key={integration.name} className="card" style={{ padding: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                    <h3 style={{ margin: 0 }}>{integration.name}</h3>
                    <span
                      style={{
                        padding: "4px 12px",
                        borderRadius: 12,
                        fontSize: 12,
                        fontWeight: 600,
                        background: statusStyle.bg,
                        color: statusStyle.color,
                      }}
                    >
                      {statusStyle.icon} {integration.status === "active" ? "Ativo" : integration.status === "inactive" ? "Inativo" : "Erro"}
                    </span>
                  </div>
                  <p style={{ color: "var(--muted)", margin: 0, fontSize: 14 }}>
                    {integration.config.description}
                  </p>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16, marginTop: 16 }}>
                <div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Configurado</div>
                  <div style={{ fontWeight: 600 }}>
                    {integration.configured ? "✅ Sim" : "❌ Não"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Total de eventos</div>
                  <div style={{ fontWeight: 600 }}>{integration.total_events}</div>
                </div>
                <div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Último evento</div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {formatDate(integration.last_event_at)}
                  </div>
                </div>
                {/* Estatísticas específicas do Eduzz */}
                {integration.name === "Eduzz" && integration.config.total_sales !== undefined && (
                  <>
                    <div>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Vendas aprovadas</div>
                      <div style={{ fontWeight: 600, color: "#22c55e" }}>{integration.config.total_sales}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Receita total</div>
                      <div style={{ fontWeight: 600, color: "#22c55e" }}>
                        {new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format((integration.config.total_revenue || 0) / 100)}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Produtos sincronizados</div>
                      <div style={{ fontWeight: 600 }}>{integration.config.products_synced || 0}</div>
                    </div>
                    {integration.config.recovered_carts !== undefined && (
                      <div>
                        <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Carrinhos recuperados</div>
                        <div style={{ fontWeight: 600, color: "#3b82f6" }}>{integration.config.recovered_carts}</div>
                      </div>
                    )}
                  </>
                )}
                {/* Estatísticas específicas da The Members */}
                {integration.name === "The Members" && integration.config.active_subscriptions !== undefined && (
                  <>
                    <div>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Assinaturas ativas</div>
                      <div style={{ fontWeight: 600, color: "#22c55e" }}>{integration.config.active_subscriptions}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Produtos sincronizados</div>
                      <div style={{ fontWeight: 600 }}>{integration.config.products_synced || 0}</div>
                    </div>
                  </>
                )}
              </div>

              {/* Webhook URL ou Config */}
              {integration.config.webhook_url && (
                <div style={{ marginTop: 16, padding: 12, background: "var(--panel)", borderRadius: 8 }}>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>Webhook URL</div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      fontFamily: "monospace",
                      fontSize: 13,
                      padding: 8,
                      background: "var(--bg)",
                      borderRadius: 6,
                      border: "1px solid var(--border)",
                    }}
                  >
                    <span style={{ flex: 1, wordBreak: "break-all" }}>{integration.config.webhook_url}</span>
                    <button
                      onClick={() => copyToClipboard(integration.config.webhook_url!)}
                      style={{
                        padding: "4px 8px",
                        fontSize: 12,
                        background: "var(--primary-color)",
                        color: "white",
                        border: "none",
                        borderRadius: 4,
                        cursor: "pointer",
                      }}
                    >
                      Copiar
                    </button>
                  </div>
                </div>
              )}

              {integration.config.base_url && (
                <div style={{ marginTop: 12, padding: 12, background: "var(--panel)", borderRadius: 8 }}>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Base URL</div>
                  <div style={{ fontFamily: "monospace", fontSize: 13 }}>{integration.config.base_url}</div>
                </div>
              )}
              
              {/* Link para produtos sincronizados (Eduzz) */}
              {integration.name === "Eduzz" && integration.config.products_synced > 0 && (
                <div style={{ marginTop: 12, padding: 12, background: "var(--panel)", borderRadius: 8 }}>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
                    {integration.config.products_synced} produtos sincronizados
                  </div>
                  <button
                    onClick={() => navigate("/products?source=eduzz")}
                    style={{
                      fontSize: 13,
                      color: "var(--primary-color)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      fontWeight: 600,
                      padding: 0,
                      textAlign: "left",
                    }}
                  >
                    Ver produtos da Eduzz →
                  </button>
                </div>
              )}
              
              {/* Link para produtos sincronizados (The Members) */}
              {integration.name === "The Members" && integration.config.products_synced > 0 && (
                <div style={{ marginTop: 12, padding: 12, background: "var(--panel)", borderRadius: 8 }}>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
                    {integration.config.products_synced} produtos sincronizados
                  </div>
                  <button
                    onClick={() => navigate("/products?source=themembers")}
                    style={{
                      fontSize: 13,
                      color: "var(--primary-color)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      fontWeight: 600,
                      padding: 0,
                      textAlign: "left",
                    }}
                  >
                    Ver produtos da The Members →
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Eventos Recentes */}
      <div className="card" style={{ padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ margin: 0 }}>Eventos Recentes</h3>
          <button className="btn" onClick={loadRecentEvents} disabled={loadingEvents}>
            {loadingEvents ? "Carregando..." : "Atualizar"}
          </button>
        </div>

        {recentEvents.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
            Nenhum evento recente
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {recentEvents.map((event) => (
              <div
                key={event.id}
                style={{
                  padding: 12,
                  background: "var(--panel)",
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 600,
                        background: "var(--primary-soft)",
                        color: "var(--primary-color)",
                      }}
                    >
                      {event.source}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{event.event}</span>
                  </div>
                  <span style={{ fontSize: 12, color: "var(--muted)" }}>
                    {formatDate(event.created_at)}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: "var(--muted)" }}>
                  <div>Email: {event.buyer_email}</div>
                  {event.order_id && <div>Pedido: {event.order_id}</div>}
                  {event.value && (
                    <div>
                      Valor: {new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(event.value / 100)}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

