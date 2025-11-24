// frontend/src/pages/Dashboard.tsx
import React, { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  listThreads,
  createThread,
  deleteThread,
  getStats,
  type Thread,
  type StatsResponse,
} from "../api";

export default function Dashboard() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loadingThreads, setLoadingThreads] = useState(true);
  const [loadingStats, setLoadingStats] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [isTablet, setIsTablet] = useState(window.innerWidth < 1024);
  const navigate = useNavigate();

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
      setIsTablet(window.innerWidth < 1024);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  async function refreshThreads() {
    try {
      setError(null);
      setLoadingThreads(true);
      const data = await listThreads();
      setThreads(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e?.message || "Falha ao carregar conversas");
    } finally {
      setLoadingThreads(false);
    }
  }

  async function refreshStats() {
    try {
      setLoadingStats(true);
      const s = await getStats();
      setStats(s);
    } catch {
      setStats(null);
    } finally {
      setLoadingStats(false);
    }
  }

  useEffect(() => {
    refreshThreads();
    refreshStats();
  }, []);

  async function handleCreate() {
    try {
      setCreating(true);
      const t = await createThread("Nova conversa");
      // navegar para o chat; o Chat já seleciona a primeira thread.
      // Se quiser passar o id explicitamente, mantemos o query param:
      navigate(`/chat?thread=${t?.id ?? ""}`);
    } catch (e: any) {
      setError(e?.message || "Não foi possível criar a conversa");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(threadId: number | string) {
    if (!confirm("Excluir esta conversa? Essa ação não pode ser desfeita.")) return;
    try {
      await deleteThread(Number(threadId));
      await refreshThreads();
      await refreshStats();
    } catch (e: any) {
      setError(e?.message || "Não foi possível excluir");
    }
  }

  // Preparar dados para gráficos
  const chartData = useMemo(() => {
    if (!stats?.messages_by_day || stats.messages_by_day.length === 0) return [];
    return stats.messages_by_day.map((d) => ({
      date: new Date(d.date).toLocaleDateString("pt-BR", { month: "short", day: "numeric" }),
      user: d.user,
      assistant: d.assistant,
      total: d.user + d.assistant,
    }));
  }, [stats?.messages_by_day]);

  // Distribuição de leads (usa dados da API + calcula desconhecidos)
  const leadDistribution = useMemo(() => {
    const counts = { quente: 0, morno: 0, frio: 0, desconhecido: 0 };
    
    // Primeiro tenta usar dados da API
    if (stats?.lead_levels) {
      counts.quente = stats.lead_levels.quente || 0;
      counts.morno = stats.lead_levels.morno || 0;
      counts.frio = stats.lead_levels.frio || 0;
      counts.desconhecido = stats.lead_levels.desconhecido || 0;
    } else {
      // Fallback: calcula dos threads
      threads.forEach((t) => {
        const level = (t as any).lead_level;
        if (level === "quente" || level === "morno" || level === "frio") {
          counts[level]++;
        } else {
          counts.desconhecido++;
        }
      });
    }
    
    // Se ainda não tiver desconhecidos calculados, calcula pela diferença
    const totalKnown = counts.quente + counts.morno + counts.frio;
    const totalThreads = stats?.threads || threads.length;
    if (counts.desconhecido === 0 && totalThreads > totalKnown) {
      counts.desconhecido = totalThreads - totalKnown;
    }
    
    return [
      { name: "Quente", value: counts.quente, color: "#dc2626" },
      { name: "Morno", value: counts.morno, color: "#f59e0b" },
      { name: "Frio", value: counts.frio, color: "#1d4ed8" },
      { name: "Sem classificação", value: counts.desconhecido, color: "#6b7280" },
    ].filter((item) => item.value > 0);
  }, [stats?.lead_levels, stats?.threads, threads]);

  // Mensagens por hora do dia
  const hourlyData = useMemo(() => {
    if (!stats?.messages_by_hour) return [];
    return stats.messages_by_hour.map((count, hour) => ({
      hour: `${hour.toString().padStart(2, "0")}:00`,
      messages: count,
    }));
  }, [stats?.messages_by_hour]);

  // Crescimento de conversas
  const growthData = useMemo(() => {
    if (!stats?.threads_growth || stats.threads_growth.length === 0) return [];
    return stats.threads_growth.map((d) => ({
      date: new Date(d.date).toLocaleDateString("pt-BR", { month: "short", day: "numeric" }),
      conversas: d.count,
    }));
  }, [stats?.threads_growth]);

  // Distribuição por origem
  const originData = useMemo(() => {
    if (!stats?.origin_distribution || stats.origin_distribution.length === 0) return [];
    return stats.origin_distribution
      .sort((a, b) => b.count - a.count)
      .slice(0, 6); // Top 6 origens
  }, [stats?.origin_distribution]);

  // Dados para gráfico de pizza de mensagens
  const messageDistribution = useMemo(() => {
    const user = stats?.user_messages ?? 0;
    const assistant = stats?.assistant_messages ?? 0;
    return [
      { name: "Você", value: user, color: "#6366f1" },
      { name: "Assistente", value: assistant, color: "#10b981" },
    ];
  }, [stats]);

  return (
    <section style={{ 
      display: "grid", 
      gap: isMobile ? 12 : 16,
      padding: 0,
      maxWidth: "100%",
      overflow: "hidden",
      boxSizing: "border-box"
    }}>
      <h1 className="profile-title" style={{ fontSize: isMobile ? 18 : 22, margin: 0 }}>
        Dashboard
      </h1>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: isTablet ? "1fr" : "340px 1fr",
          gap: isMobile ? 12 : 16,
          alignItems: "start",
          maxWidth: "100%",
          overflow: "hidden",
        }}
      >
        {/* COLUNA ESQUERDA — conversas */}
        <aside className="profile-card" style={{ display: "grid", gap: isMobile ? 8 : 12 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <div className="profile-title" style={{ margin: 0, fontSize: isMobile ? 14 : 16 }}>
              Conversas
            </div>
            <button 
              className="btn" 
              onClick={handleCreate} 
              disabled={creating}
              style={{ 
                padding: isMobile ? "6px 10px" : "8px 12px",
                fontSize: isMobile ? 12 : 14
              }}
            >
              {creating ? "Criando…" : isMobile ? "+" : "+ Nova"}
            </button>
          </div>

          {loadingThreads ? (
            <div className="small" style={{ color: "var(--muted)" }}>Carregando…</div>
          ) : error ? (
            <div
              role="alert"
              style={{
                border: "1px solid #7f1d1d",
                background: "#1b0f10",
                color: "#fecaca",
                padding: "10px 12px",
                borderRadius: 10,
                fontSize: 14,
              }}
            >
              {error}
            </div>
          ) : threads.length === 0 ? (
            <div className="small" style={{ color: "var(--muted)" }}>
              Você ainda não tem conversas.
            </div>
          ) : (
            <div
              style={{
                display: "grid",
                gap: isMobile ? 6 : 8,
                maxHeight: isMobile ? 300 : 520,
                overflowY: "auto",
              }}
            >
              {threads.map((t) => (
                <button
                  key={t.id}
                  onClick={() => navigate(`/chat?thread=${t.id}`)}
                  className="item"
                  style={{
                    textAlign: "left",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    padding: isMobile ? 8 : 10,
                    borderRadius: 10,
                    border: "1px solid var(--border)",
                    background: "var(--bg)",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ overflow: "hidden" }}>
                    <div
                      style={{
                        fontWeight: 700,
                        color: "var(--text)",
                        whiteSpace: "nowrap",
                        textOverflow: "ellipsis",
                        overflow: "hidden",
                        maxWidth: isMobile ? 180 : 220,
                        fontSize: isMobile ? 13 : 14,
                      }}
                      title={t.title || `Thread #${t.id}`}
                    >
                      {t.title || `Thread #${t.id}`}
                    </div>
                    <div className="small" style={{ color: "var(--muted)", fontSize: isMobile ? 11 : 12 }}>
                      ID #{t.id}
                    </div>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(t.id!);
                    }}
                    title="Excluir"
                    className="btn soft"
                    style={{ 
                      padding: isMobile ? "4px 8px" : "4px 10px",
                      fontSize: isMobile ? 11 : 12
                    }}
                  >
                    {isMobile ? "×" : "Excluir"}
                  </button>
                </button>
              ))}
            </div>
          )}
        </aside>

        {/* COLUNA DIREITA — stats + gráficos */}
        <div style={{ 
          display: "grid", 
          gap: isMobile ? 12 : 16,
          minWidth: 0, // Previne overflow
          maxWidth: "100%",
          overflow: "hidden"
        }}>
          {/* Cards de métricas melhorados */}
          <div className="profile-card" style={{ maxWidth: "100%", overflow: "hidden" }}>
            <div
              className="profile-title"
              style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}
            >
              <span>Visão Geral</span>
              <button
                className="btn soft"
                onClick={() => {
                  refreshStats();
                  refreshThreads();
                }}
                style={{ padding: "6px 10px" }}
              >
                Atualizar
              </button>
            </div>

            {loadingStats ? (
              <div className="small" style={{ color: "var(--muted)", textAlign: "center", padding: 20 }}>
                Carregando métricas…
              </div>
            ) : (
              <>
                <div style={{ 
                  display: "grid", 
                  gridTemplateColumns: isMobile ? "repeat(2, 1fr)" : "repeat(auto-fit, minmax(140px, 1fr))", 
                  gap: isMobile ? 8 : 12 
                }}>
                  <StatCard 
                    title="Conversas" 
                    value={stats?.threads ?? 0} 
                    color="#6366f1"
                    isMobile={isMobile}
                  />
                  <StatCard 
                    title="Suas mensagens" 
                    value={stats?.user_messages ?? 0} 
                    color="#8b5cf6"
                    isMobile={isMobile}
                  />
                  <StatCard 
                    title="IA respondeu" 
                    value={stats?.assistant_messages ?? 0} 
                    color="#10b981"
                    isMobile={isMobile}
                  />
                  <StatCard 
                    title="Total" 
                    value={stats?.total_messages ?? 0} 
                    color="#f59e0b"
                    isMobile={isMobile}
                  />
                </div>

                <div style={{ 
                  display: "grid", 
                  gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", 
                  gap: isMobile ? 8 : 12, 
                  marginTop: 12 
                }}>
                  {stats?.avg_assistant_response_ms && (
                    <div style={{ 
                      padding: isMobile ? 8 : 10, 
                      background: "var(--panel)", 
                      borderRadius: 8,
                      border: "1px solid var(--border)"
                    }}>
                      <div className="small" style={{ color: "var(--muted)", marginBottom: 4, fontSize: isMobile ? 11 : 12 }}>
                        Tempo médio de resposta
                      </div>
                      <div style={{ fontSize: isMobile ? 16 : 18, fontWeight: 600, color: "var(--text)" }}>
                        {(stats.avg_assistant_response_ms / 1000).toFixed(1)}s
                      </div>
                    </div>
                  )}
                  {stats?.response_rate !== undefined && (
                    <div style={{ 
                      padding: isMobile ? 8 : 10, 
                      background: "var(--panel)", 
                      borderRadius: 8,
                      border: "1px solid var(--border)"
                    }}>
                      <div className="small" style={{ color: "var(--muted)", marginBottom: 4, fontSize: isMobile ? 11 : 12 }}>
                        Taxa de resposta
                      </div>
                      <div style={{ fontSize: isMobile ? 16 : 18, fontWeight: 600, color: "#10b981" }}>
                        {stats.response_rate}%
                      </div>
                    </div>
                  )}
                </div>

                <div className="small" style={{ color: "var(--muted)", marginTop: 12, textAlign: "center" }}>
                  Última atividade:{" "}
                  {stats?.last_activity
                    ? new Date(stats.last_activity as any).toLocaleString("pt-BR")
                    : "—"}
                </div>
              </>
            )}
          </div>

          {/* Gráfico de mensagens ao longo do tempo */}
          {chartData.length > 0 && (
            <div className="profile-card" style={{ display: "grid", gap: 12, maxWidth: "100%", overflow: "hidden" }}>
              <div className="profile-title" style={{ 
                fontSize: isMobile ? 16 : 18, 
                margin: 0,
                fontWeight: 600,
                color: "var(--text)"
              }}>
                Mensagens ao Longo do Tempo
              </div>
              <div style={{ 
                width: "100%", 
                height: isMobile ? 280 : 280,
                minHeight: isMobile ? 280 : 280,
                maxWidth: "100%",
                overflow: "hidden"
              }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ 
                    top: 10, 
                    right: isMobile ? 5 : 5, 
                    left: isMobile ? 5 : 5, 
                    bottom: isMobile ? 50 : 5 
                  }}>
                    <defs>
                      <linearGradient id="colorUser" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                      </linearGradient>
                      <linearGradient id="colorAssistant" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis 
                      dataKey="date" 
                      stroke="var(--muted)"
                      style={{ fontSize: isMobile ? 11 : 12 }}
                      angle={isMobile ? -45 : 0}
                      textAnchor={isMobile ? "end" : "middle"}
                      height={isMobile ? 50 : 30}
                    />
                    <YAxis 
                      stroke="var(--muted)"
                      style={{ fontSize: isMobile ? 11 : 12 }}
                    />
                    <Tooltip 
                      contentStyle={{ 
                        background: "var(--panel)", 
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                        color: "var(--text)"
                      }}
                    />
                    <Legend />
                    <Area 
                      type="monotone" 
                      dataKey="user" 
                      name="Você" 
                      stroke="#6366f1" 
                      fillOpacity={1} 
                      fill="url(#colorUser)"
                      strokeWidth={2}
                    />
                    <Area 
                      type="monotone" 
                      dataKey="assistant" 
                      name="Assistente" 
                      stroke="#10b981" 
                      fillOpacity={1} 
                      fill="url(#colorAssistant)"
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Gráficos lado a lado - Primeira linha */}
          <div style={{ 
            display: "grid", 
            gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", 
            gap: 16 
          }}>
            {/* Gráfico de pizza - Distribuição de mensagens */}
            {messageDistribution.some((d) => d.value > 0) && (
              <div className="profile-card" style={{ display: "grid", gap: 12, maxWidth: "100%", overflow: "hidden" }}>
                <div className="profile-title" style={{ 
                  fontSize: isMobile ? 16 : 18, 
                  margin: 0,
                  fontWeight: 600,
                  color: "var(--text)"
                }}>
                  Distribuição de Mensagens
                </div>
                <div style={{ 
                  width: "100%", 
                  height: isMobile ? 260 : 240,
                  minHeight: isMobile ? 260 : 240,
                  maxWidth: "100%",
                  display: "flex", 
                  alignItems: "center", 
                  justifyContent: "center",
                  overflow: "hidden"
                }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={messageDistribution}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) => isMobile ? `${(percent * 100).toFixed(0)}%` : `${name}: ${(percent * 100).toFixed(0)}%`}
                        outerRadius={isMobile ? 90 : 80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {messageDistribution.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--panel)", 
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          color: "var(--text)",
                          fontSize: isMobile ? 12 : 14
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Gráfico de barras - Distribuição de leads */}
            {leadDistribution.length > 0 && (
              <div className="profile-card" style={{ display: "grid", gap: 12, maxWidth: "100%", overflow: "hidden" }}>
                <div className="profile-title" style={{ 
                  fontSize: isMobile ? 16 : 18, 
                  margin: 0,
                  fontWeight: 600,
                  color: "var(--text)"
                }}>
                  Temperatura dos Leads
                </div>
                <div style={{ 
                  width: "100%", 
                  height: isMobile ? 260 : 240,
                  minHeight: isMobile ? 260 : 240,
                  maxWidth: "100%",
                  overflow: "hidden",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={leadDistribution} layout="vertical" margin={{ 
                      top: 10, 
                      right: isMobile ? 5 : 5, 
                      left: isMobile ? 80 : 5, 
                      bottom: 10 
                    }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis type="number" stroke="var(--muted)" style={{ fontSize: isMobile ? 12 : 12 }} />
                      <YAxis 
                        dataKey="name" 
                        type="category" 
                        stroke="var(--muted)"
                        style={{ fontSize: isMobile ? 12 : 12 }}
                        width={isMobile ? 90 : 60}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--panel)", 
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          color: "var(--text)",
                          fontSize: isMobile ? 12 : 14
                        }}
                      />
                      <Bar dataKey="value" radius={[0, 8, 8, 0]}>
                        {leadDistribution.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>

          {/* Gráfico de mensagens por hora */}
          {hourlyData.some((d) => d.messages > 0) && (
            <div className="profile-card" style={{ display: "grid", gap: 12, maxWidth: "100%", overflow: "hidden" }}>
              <div className="profile-title" style={{ 
                fontSize: isMobile ? 16 : 18, 
                margin: 0,
                fontWeight: 600,
                color: "var(--text)"
              }}>
                Mensagens por Hora do Dia
              </div>
              <div style={{ 
                width: "100%", 
                height: isMobile ? 300 : 280,
                minHeight: isMobile ? 300 : 280,
                maxWidth: "100%",
                overflow: "hidden",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={hourlyData} margin={{ 
                    top: 10, 
                    right: isMobile ? 5 : 5, 
                    left: isMobile ? 5 : 5, 
                    bottom: isMobile ? 60 : 30 
                  }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis 
                        dataKey="hour" 
                        stroke="var(--muted)"
                        style={{ fontSize: isMobile ? 10 : 11 }}
                        angle={isMobile ? -90 : -45}
                        textAnchor="end"
                        height={isMobile ? 80 : 60}
                        interval={isMobile ? 2 : 0}
                      />
                      <YAxis stroke="var(--muted)" style={{ fontSize: isMobile ? 11 : 12 }} />
                    <Tooltip 
                      contentStyle={{ 
                        background: "var(--panel)", 
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                        color: "var(--text)",
                        fontSize: isMobile ? 12 : 14
                      }}
                    />
                    <Bar dataKey="messages" fill="#6366f1" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Gráficos lado a lado - Segunda linha */}
          <div style={{ 
            display: "grid", 
            gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", 
            gap: 16 
          }}>
            {/* Crescimento de conversas */}
            {growthData.length > 0 && (
              <div className="profile-card" style={{ display: "grid", gap: 12, maxWidth: "100%", overflow: "hidden" }}>
                <div className="profile-title" style={{ 
                  fontSize: isMobile ? 16 : 18, 
                  margin: 0,
                  fontWeight: 600,
                  color: "var(--text)"
                }}>
                  Crescimento (30 dias)
                </div>
                <div style={{ 
                  width: "100%", 
                  height: isMobile ? 280 : 240,
                  minHeight: isMobile ? 280 : 240,
                  maxWidth: "100%",
                  overflow: "hidden",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={growthData} margin={{ 
                      top: 10, 
                      right: isMobile ? 5 : 5, 
                      left: isMobile ? 5 : 5, 
                      bottom: isMobile ? 60 : 30 
                    }}>
                      <defs>
                        <linearGradient id="colorGrowth" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis 
                        dataKey="date" 
                        stroke="var(--muted)"
                        style={{ fontSize: isMobile ? 10 : 11 }}
                        angle={isMobile ? -90 : -45}
                        textAnchor="end"
                        height={isMobile ? 80 : 60}
                        interval={isMobile ? 2 : 0}
                      />
                      <YAxis stroke="var(--muted)" style={{ fontSize: isMobile ? 11 : 12 }} />
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--panel)", 
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          color: "var(--text)",
                          fontSize: isMobile ? 12 : 14
                        }}
                      />
                      <Area 
                        type="monotone" 
                        dataKey="conversas" 
                        stroke="#8b5cf6" 
                        fillOpacity={1} 
                        fill="url(#colorGrowth)"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Distribuição por origem */}
            {originData.length > 0 && (
              <div className="profile-card" style={{ display: "grid", gap: 12, maxWidth: "100%", overflow: "hidden" }}>
                <div className="profile-title" style={{ 
                  fontSize: isMobile ? 16 : 18, 
                  margin: 0,
                  fontWeight: 600,
                  color: "var(--text)"
                }}>
                  Origem dos Contatos
                </div>
                <div style={{ 
                  width: "100%", 
                  height: isMobile ? 260 : 240,
                  minHeight: isMobile ? 260 : 240,
                  maxWidth: "100%",
                  overflow: "hidden",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={originData} layout="vertical" margin={{ 
                      top: 10, 
                      right: isMobile ? 5 : 5, 
                      left: isMobile ? 100 : 5, 
                      bottom: 10 
                    }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis type="number" stroke="var(--muted)" style={{ fontSize: isMobile ? 12 : 12 }} />
                      <YAxis 
                        dataKey="origin" 
                        type="category" 
                        stroke="var(--muted)"
                        style={{ fontSize: isMobile ? 12 : 12 }}
                        width={isMobile ? 110 : 100}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--panel)", 
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          color: "var(--text)",
                          fontSize: isMobile ? 12 : 14
                        }}
                      />
                      <Bar dataKey="count" fill="#f59e0b" radius={[0, 8, 8, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>

          {/* Card de orientação */}
          <div className="profile-card" style={{ display: "grid", gap: isMobile ? 8 : 12 }}>
            <div className="profile-title" style={{ fontSize: isMobile ? 14 : 16, margin: 0 }}>
              Como começar
            </div>
            <p className="small" style={{ color: "var(--muted)", margin: 0, fontSize: isMobile ? 12 : 14 }}>
              {isMobile ? (
                <>Selecione uma conversa ou crie uma <strong>nova</strong> para começar.</>
              ) : (
                <>Selecione uma conversa à esquerda para abrir no chat, ou crie uma <strong>nova</strong> para começar do zero. Você também pode ir em <strong>Minha conta</strong> para ver token e métricas detalhadas.</>
              )}
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: isMobile ? "wrap" : "nowrap" }}>
              <button 
                className="btn" 
                onClick={handleCreate} 
                disabled={creating}
                style={{ 
                  flex: isMobile ? "1 1 100%" : "auto",
                  fontSize: isMobile ? 12 : 14,
                  padding: isMobile ? "8px 12px" : "10px 16px"
                }}
              >
                {creating ? "Criando…" : "Nova conversa"}
              </button>
              <button
                className="btn soft"
                onClick={() => navigate("/profile")}
                style={{ 
                  marginLeft: isMobile ? 0 : 8,
                  flex: isMobile ? "1 1 100%" : "auto",
                  fontSize: isMobile ? 12 : 14,
                  padding: isMobile ? "8px 12px" : "10px 16px"
                }}
              >
                Minha conta
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function StatCard({ 
  title, 
  value, 
  color = "#6366f1",
  isMobile = false
}: { 
  title: string; 
  value: number;
  color?: string;
  isMobile?: boolean;
}) {
  return (
    <div 
      style={{ 
        textAlign: "center",
        padding: isMobile ? 12 : 16,
        borderRadius: 12,
        border: `1px solid var(--border)`,
        background: "var(--bg)",
        transition: "transform 0.2s, box-shadow 0.2s",
      }}
      onMouseEnter={(e) => {
        if (!isMobile) {
          e.currentTarget.style.transform = "translateY(-2px)";
          e.currentTarget.style.boxShadow = `0 4px 12px ${color}20`;
        }
      }}
      onMouseLeave={(e) => {
        if (!isMobile) {
          e.currentTarget.style.transform = "translateY(0)";
          e.currentTarget.style.boxShadow = "none";
        }
      }}
    >
      <div 
        style={{ 
          fontSize: isMobile ? 22 : 28, 
          fontWeight: 700, 
          color: color,
          marginBottom: 4,
        }}
      >
        {value.toLocaleString("pt-BR")}
      </div>
      <div 
        className="small" 
        style={{ 
          color: "var(--muted)",
          fontSize: isMobile ? 11 : 12,
        }}
      >
        {title}
      </div>
    </div>
  );
}
