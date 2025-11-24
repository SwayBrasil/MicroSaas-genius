// frontend/src/pages/Profile.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
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
import { useAuth } from "../auth";
import { getProfile, getUsage, getStats } from "../api";

/** =========================
 * Tipos
 * ========================= */
type ProfileData = {
  id: string | number;
  email: string;
  name?: string;
  plan?: string;
  created_at?: string | null;
  last_activity_at?: string | null;
};
type UsageData = {
  threads_total: number;
  messages_total: number;
  user_sent: number;
  assistant_sent: number;
};
type MessagesByDay = { date: string; user: number; assistant: number };

type TopContact = {
  id: string;
  name?: string | null;
  last_at?: string | null;
  total_msgs?: number;
};

type StatsResponse = {
  // básicos (já existiam)
  threads?: number;
  total_messages?: number;
  user_messages?: number;
  assistant_messages?: number;
  last_activity?: string | null;
  messages_by_day?: MessagesByDay[];
  avg_assistant_response_ms?: number | null;

  // novos (opcionais; render condicional)
  first_response_time_ms_avg?: number | null; // FRT
  resolution_time_ms_avg?: number | null;     // TMR
  assistant_latency_p50?: number | null;
  assistant_latency_p95?: number | null;
  takeover_rate?: number | null;              // 0..1 (fração)
  lead_levels?: { frio?: number; morno?: number; quente?: number } | null;
  active_days_30d?: number | null;            // 0..30
  messages_by_hour?: number[] | null;         // 24 posições
  messages_heatmap?: number[][] | null;       // 7x24 (0=Dom, 6=Sáb) opcional
  top_contacts?: TopContact[] | null;
  wa_templates_month?: number | null;
  wa_sessions_month?: number | null;
  tokens_month?: { prompt?: number; completion?: number } | null;

  // onboarding
  onboarding_total_steps?: number | null;
  onboarding_current_step?: number | null;
  is_onboarded?: boolean | null;
};

/** =========================
 * Utils
 * ========================= */
function formatDate(dt?: string | number | Date | null) {
  if (!dt) return "—";
  const d = new Date(dt);
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
}
function initials(name?: string, email?: string) {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/).slice(0, 2);
    return parts.map((p) => p[0]?.toUpperCase()).join("");
  }
  const user = email?.split("@")[0] || "U";
  return (user[0] || "U").toUpperCase();
}
const clamp = (x: number, min: number, max: number) => Math.max(min, Math.min(max, x));

/** =========================
 * Componentes Visuais
 * ========================= */
function ProgressBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = max > 0 ? clamp((value / max) * 100, 0, 100) : 0;
  return (
    <div style={{ width: "100%", height: 10, background: "var(--soft)", borderRadius: 999, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: "var(--primary)" }} />
    </div>
  );
}

function MiniBar({ a, b, labelA, labelB }: { a: number; b: number; labelA: string; labelB: string }) {
  const tot = Math.max(0, a + b);
  const pa = tot ? (a / tot) * 100 : 0;
  const pb = tot ? (b / tot) * 100 : 0;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span className="small">{labelA}: <strong>{a}</strong></span>
        <span className="small">{labelB}: <strong>{b}</strong></span>
        <span className="small" style={{ marginLeft: "auto", opacity: 0.8 }}>Total: {tot}</span>
      </div>
      <div style={{ height: 12, borderRadius: 999, overflow: "hidden", display: "flex" }}>
        <div style={{ width: `${pa}%`, background: "#6366f1" }} />
        <div style={{ width: `${pb}%`, background: "#10b981" }} />
      </div>
    </div>
  );
}

function LeadDistribution({ frio = 0, morno = 0, quente = 0 }: { frio?: number; morno?: number; quente?: number }) {
  const tot = Math.max(0, frio + morno + quente);
  const pct = (x: number) => (tot ? Math.round((x / tot) * 100) : 0);
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <span className="chip" style={{ background: "#0f172a", color: "#93c5fd", border: "1px solid #1d4ed8" }}>
          Frio: <strong style={{ marginLeft: 6 }}>{frio}</strong> ({pct(frio)}%)
        </span>
        <span className="chip" style={{ background: "#1f2937", color: "#fde68a", border: "1px solid #f59e0b" }}>
          Morno: <strong style={{ marginLeft: 6 }}>{morno}</strong> ({pct(morno)}%)
        </span>
        <span className="chip" style={{ background: "#2d0f12", color: "#fecaca", border: "1px solid #dc2626" }}>
          Quente: <strong style={{ marginLeft: 6 }}>{quente}</strong> ({pct(quente)}%)
        </span>
      </div>
      <div style={{ height: 12, borderRadius: 999, overflow: "hidden", display: "flex" }}>
        <div style={{ width: `${pct(frio)}%`, background: "#1d4ed8" }} />
        <div style={{ width: `${pct(morno)}%`, background: "#f59e0b" }} />
        <div style={{ width: `${pct(quente)}%`, background: "#dc2626" }} />
      </div>
    </div>
  );
}

function MiniHeatmap24x7({
  heatmap, // 7x24 [dia][hora]
  width = 360,
  height = 140,
  dayLabels = ["D", "S", "T", "Q", "Q", "S", "S"],
}: {
  heatmap: number[][];
  width?: number;
  height?: number;
  dayLabels?: string[];
}) {
  const rows = heatmap.length;
  const cols = heatmap[0]?.length || 0;
  const cellW = width / Math.max(1, cols);
  const cellH = height / Math.max(1, rows);
  const flat = heatmap.flat();
  const max = Math.max(1, ...flat);
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div style={{ display: "grid", gridTemplateColumns: `auto ${width}px`, alignItems: "center", gap: 8 }}>
        <div />
        <div className="small" style={{ display: "flex", justifyContent: "space-between", opacity: 0.8 }}>
          {Array.from({ length: cols }, (_, i) => <span key={i} style={{ width: cellW, textAlign: "center" }}>{i}</span>)}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: `auto ${width}px`, gap: 8 }}>
        <div style={{ display: "grid", gap: 4 }}>
          {Array.from({ length: rows }, (_, r) => (
            <div key={r} className="small" style={{ opacity: 0.8 }}>{dayLabels[r] ?? r}</div>
          ))}
        </div>
        <svg width={width} height={height}>
          {heatmap.map((row, r) =>
            row.map((v, c) => {
              const intensity = v / max; // 0..1
              const bg = `rgba(99,102,241,${0.08 + 0.85 * intensity})`;
              return (
                <rect
                  key={`${r}-${c}`}
                  x={c * cellW}
                  y={r * cellH}
                  width={cellW - 1}
                  height={cellH - 1}
                  fill={bg}
                  stroke="transparent"
                />
              );
            })
          )}
        </svg>
      </div>
    </div>
  );
}


/** =========================
 * Página Profile
 * ========================= */
export default function Profile() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [stats, setStatsState] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const fallback: ProfileData = useMemo(
    () => ({
      id: (user as any)?.id ?? "-",
      email: (user as any)?.email ?? "dev@local.com",
      name: (user as any)?.name ?? "Usuário",
      plan: (user as any)?.plan ?? "Trial",
      created_at: (user as any)?.created_at ?? null,
      last_activity_at: null,
    }),
    [user]
  );

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setErr(null);
        const [pRes, uRes, sRes] = await Promise.allSettled([getProfile?.(), getUsage?.(), getStats?.()]);
        if (pRes.status === "fulfilled" && pRes.value) setProfile(pRes.value);
        if (uRes.status === "fulfilled" && uRes.value) setUsage(uRes.value);
        if (sRes.status === "fulfilled" && sRes.value) setStatsState(sRes.value as StatsResponse);
      } catch (e: any) {
        setErr(e?.message || "Falha ao carregar sua conta.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const data = profile || fallback;
  const planLabel = data.plan || "Trial";

  const totalUser = stats?.user_messages ?? usage?.user_sent ?? 0;
  const totalAssistant = stats?.assistant_messages ?? usage?.assistant_sent ?? 0;
  const totalMsgs = stats?.total_messages ?? usage?.messages_total ?? (totalUser + totalAssistant);

  // Dados para gráficos
  const pieData = [
    { name: "Você", value: totalUser, color: "#6366f1" },
    { name: "Assistente", value: totalAssistant, color: "#10b981" },
  ];

  // Mensagens por dia
  const chartData = useMemo(() => {
    if (!stats?.messages_by_day || stats.messages_by_day.length === 0) return [];
    return stats.messages_by_day
      .slice()
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((d) => ({
        date: new Date(d.date).toLocaleDateString("pt-BR", { month: "short", day: "numeric" }),
        user: d.user || 0,
        assistant: d.assistant || 0,
        total: (d.user || 0) + (d.assistant || 0),
      }));
  }, [stats?.messages_by_day]);

  // Mensagens por hora
  const hourlyData = useMemo(() => {
    if (!stats?.messages_by_hour) return [];
    return stats.messages_by_hour.map((count, hour) => ({
      hour: `${hour.toString().padStart(2, "0")}:00`,
      messages: count,
    }));
  }, [stats?.messages_by_hour]);

  // Distribuição de leads
  const leadDistribution = useMemo(() => {
    const counts = { quente: 0, morno: 0, frio: 0, desconhecido: 0 };
    if (stats?.lead_levels) {
      counts.quente = stats.lead_levels.quente || 0;
      counts.morno = stats.lead_levels.morno || 0;
      counts.frio = stats.lead_levels.frio || 0;
      counts.desconhecido = stats.lead_levels.desconhecido || 0;
    }
    const totalKnown = counts.quente + counts.morno + counts.frio;
    const totalThreads = stats?.threads || 0;
    if (counts.desconhecido === 0 && totalThreads > totalKnown) {
      counts.desconhecido = totalThreads - totalKnown;
    }
    return [
      { name: "Quente", value: counts.quente, color: "#dc2626" },
      { name: "Morno", value: counts.morno, color: "#f59e0b" },
      { name: "Frio", value: counts.frio, color: "#1d4ed8" },
      { name: "Sem classificação", value: counts.desconhecido, color: "#6b7280" },
    ].filter((item) => item.value > 0);
  }, [stats?.lead_levels, stats?.threads]);

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
      .slice(0, 6);
  }, [stats?.origin_distribution]);

  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  
  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  /** Tempo ganho */
  const [humanSecondsPerMsg, setHumanSecondsPerMsg] = useState<number>(45);
  const assistantSecondsPerMsg = (stats?.avg_assistant_response_ms ?? 3000) / 1000;
  const assistantMsgs = totalAssistant;
  const timeHuman = assistantMsgs * humanSecondsPerMsg;
  const timeAssistant = assistantMsgs * assistantSecondsPerMsg;
  const timeSavedSeconds = Math.max(0, timeHuman - timeAssistant);
  const hhmm = (sec: number) => {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    const parts = [h ? `${h}h` : null, m ? `${m}m` : null, s || (!h && !m) ? `${s}s` : null].filter(Boolean);
    return parts.join(" ");
  };

  // Derivados
  const msgsPerThread = (totalMsgs && stats?.threads) ? (totalMsgs / (stats.threads || 1)) : 0;
  const takeoverPct = typeof stats?.takeover_rate === "number" ? Math.round(stats.takeover_rate * 100) : null;

  // Skeleton
  if (loading) {
    return (
      <div style={{ padding: 14, display: "grid", gap: 12 }}>
        <div className="profile-card" style={{ height: 120 }} />
        <div className="profile-card" style={{ height: 120 }} />
        <div className="profile-card" style={{ height: 320 }} />
      </div>
    );
  }

  return (
    <div
      style={{
        height: "calc(100vh - 56px)", // header global 56px
        minHeight: 0,
        overflow: "hidden",
        display: "grid",
        gridTemplateRows: "auto 1fr",
        background: "var(--bg)",
      }}
    >
      {/* Topo fixo */}
      <div style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button className="btn soft" onClick={() => navigate(-1)} title="Voltar" style={{ padding: "6px 10px" }}>
            ← Voltar
          </button>
          <h2 className="profile-title" style={{ margin: 0 }}>Minha conta</h2>
        </div>
      </div>

      {/* Conteúdo rolável */}
      <div
        style={{
          overflowY: "auto",
          minHeight: 0,
          padding: "0 14px 14px",
          display: "grid",
          gap: 14,
          alignContent: "start",
        }}
      >
        {/* Header */}
        <div className="profile-card" style={{ display: "grid", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div
              style={{
                width: 56, height: 56, borderRadius: 999,
                background: "var(--soft)", border: "1px solid var(--border)",
                display: "grid", placeItems: "center", fontWeight: 700, fontSize: 18,
              }}
              aria-label="Avatar"
            >
              {initials(data.name, data.email)}
            </div>

            <div style={{ display: "grid", gap: 2 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <strong style={{ fontSize: 18 }}>{data.name || "Usuário"}</strong>
                <span className="badge">{planLabel}</span>
              </div>
              <div className="small">{data.email}</div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
            <KV k="ID" v={String(data.id)} />
            <KV k="Plano" v={planLabel} />
            <KV k="Criado em" v={formatDate(data.created_at)} />
            <KV k="Última atividade" v={formatDate(stats?.last_activity ?? data.last_activity_at)} />
          </div>
        </div>

        {/* KPIs gerais */}
        <div className="profile-card" style={{ display: "grid", gap: 12 }}>
          <div className="profile-title">Seus números</div>
          <div className="stats-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12 }}>
            <StatCard title="Conversas (total)" value={stats?.threads ?? usage?.threads_total ?? 0} />
            <StatCard title="Mensagens (total)" value={totalMsgs} />
            <StatCard title="Você enviou" value={totalUser} />
            <StatCard title="Assistente respondeu" value={totalAssistant} />
            <StatCard title="Média msgs/conv." value={Number.isFinite(msgsPerThread) ? Number(msgsPerThread.toFixed(1)) : 0} />
            {typeof stats?.active_days_30d === "number" && (
              <div className="stat-cardx" style={{ textAlign: "center" }}>
                <div className="stat-kpi">{stats.active_days_30d}/30</div>
                <div className="stat-label" style={{ marginTop: 6 }}>Dias ativos (30d)</div>
                <ProgressBar value={stats.active_days_30d} max={30} />
              </div>
            )}
          </div>
          {err && (
            <div role="alert" style={{ border: "1px solid #7f1d1d", background: "#1b0f10", color: "#fecaca", padding: "10px 12px", borderRadius: 10, fontSize: 14 }}>
              {err}
            </div>
          )}
        </div>

        {/* Visualizações principais */}
        <div className="profile-card" style={{ display: "grid", gap: 16 }}>
          <div className="profile-title" style={{ 
            fontSize: isMobile ? 16 : 18, 
            fontWeight: 600,
            color: "var(--text)"
          }}>
            Visualizações
          </div>
          <div style={{ display: "grid", gap: 16, gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(320px, 1fr))", alignItems: "start" }}>
            {/* Gráfico de Pizza - Distribuição de mensagens */}
            {pieData.some((d) => d.value > 0) && (
            <div style={{ display: "grid", gap: 12 }}>
                <div className="small" style={{ 
                  fontWeight: 600,
                  fontSize: isMobile ? 14 : 16,
                  color: "var(--text)"
                }}>
                  Distribuição de mensagens
                </div>
                <div style={{ 
                  width: "100%", 
                  height: isMobile ? 260 : 240, 
                  display: "flex", 
                  alignItems: "center", 
                  justifyContent: "center"
                }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) => isMobile ? `${(percent * 100).toFixed(0)}%` : `${name}: ${(percent * 100).toFixed(0)}%`}
                        outerRadius={isMobile ? 90 : 80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--panel)", 
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          color: "var(--text)"
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
            </div>
              </div>
            )}
            {/* Gráfico de Área - Mensagens por dia */}
            {chartData.length > 0 && (
            <div style={{ display: "grid", gap: 12 }}>
                <div className="small" style={{ 
                  fontWeight: 600,
                  fontSize: isMobile ? 14 : 16,
                  color: "var(--text)"
                }}>
                  Mensagens por dia
                </div>
                <div style={{ 
                  width: "100%", 
                  height: isMobile ? 280 : 240, 
                  overflow: "hidden",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ 
                      top: 10, 
                      right: isMobile ? 5 : 5, 
                      left: isMobile ? 5 : 5, 
                      bottom: isMobile ? 50 : 5 
                    }}>
                      <defs>
                        <linearGradient id="colorUserProfile" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorAssistantProfile" x1="0" y1="0" x2="0" y2="1">
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
                        height={isMobile ? 60 : 30}
                      />
                      <YAxis stroke="var(--muted)" style={{ fontSize: isMobile ? 11 : 12 }} />
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
                        fill="url(#colorUserProfile)"
                        strokeWidth={2}
                      />
                      <Area 
                        type="monotone" 
                        dataKey="assistant" 
                        name="Assistente" 
                        stroke="#10b981" 
                        fillOpacity={1} 
                        fill="url(#colorAssistantProfile)"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
              </div>
              </div>
            )}
            {chartData.length === 0 && (
                <div className="small" style={{ opacity: 0.7 }}>Sem histórico suficiente para exibir o gráfico.</div>
              )}
            </div>
          </div>

        {/* Novos gráficos */}
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr" }}>
          {/* Gráfico de barras - Distribuição de leads */}
          {leadDistribution.length > 0 && (
            <div className="profile-card" style={{ display: "grid", gap: 12 }}>
              <div className="profile-title" style={{ 
                fontSize: isMobile ? 16 : 18, 
                fontWeight: 600,
                color: "var(--text)"
              }}>
                Temperatura dos Leads
        </div>
              <div style={{ 
                width: "100%", 
                height: isMobile ? 260 : 240,
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={leadDistribution} layout="vertical" margin={{ 
                    top: 10, 
                    right: isMobile ? 5 : 5, 
                    left: isMobile ? 90 : 5, 
                    bottom: 10 
                  }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis type="number" stroke="var(--muted)" style={{ fontSize: isMobile ? 12 : 12 }} />
                    <YAxis 
                      dataKey="name" 
                      type="category" 
                      stroke="var(--muted)"
                      style={{ fontSize: isMobile ? 12 : 12 }}
                      width={isMobile ? 100 : 80}
                    />
                    <Tooltip 
                      contentStyle={{ 
                        background: "var(--panel)", 
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                        color: "var(--text)"
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

          {/* Gráfico de mensagens por hora */}
          {hourlyData.some((d) => d.messages > 0) && (
            <div className="profile-card" style={{ display: "grid", gap: 12 }}>
              <div className="profile-title" style={{ 
                fontSize: isMobile ? 16 : 18, 
                fontWeight: 600,
                color: "var(--text)"
              }}>
                Mensagens por Hora
              </div>
              <div style={{ 
                width: "100%", 
                height: isMobile ? 300 : 240,
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
                        color: "var(--text)"
                      }}
                    />
                    <Bar dataKey="messages" fill="#6366f1" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>

        {/* Crescimento e Origem */}
        {(growthData.length > 0 || originData.length > 0) && (
          <div style={{ display: "grid", gap: 16, gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr" }}>
            {/* Crescimento de conversas */}
            {growthData.length > 0 && (
              <div className="profile-card" style={{ display: "grid", gap: 12 }}>
                <div className="profile-title" style={{ 
                  fontSize: isMobile ? 16 : 18, 
                  fontWeight: 600,
                  color: "var(--text)"
                }}>
                  Crescimento (30 dias)
                </div>
                <div style={{ 
                  width: "100%", 
                  height: isMobile ? 280 : 240,
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
                        <linearGradient id="colorGrowthProfile" x1="0" y1="0" x2="0" y2="1">
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
                          color: "var(--text)"
                        }}
                      />
                      <Area 
                        type="monotone" 
                        dataKey="conversas" 
                        stroke="#8b5cf6" 
                        fillOpacity={1} 
                        fill="url(#colorGrowthProfile)"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Distribuição por origem */}
            {originData.length > 0 && (
              <div className="profile-card" style={{ display: "grid", gap: 12 }}>
                <div className="profile-title" style={{ 
                  fontSize: isMobile ? 16 : 18, 
                  fontWeight: 600,
                  color: "var(--text)"
                }}>
                  Origem dos Contatos
                </div>
                <div style={{ 
                  width: "100%", 
                  height: isMobile ? 260 : 240,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={originData} layout="vertical" margin={{ 
                      top: 10, 
                      right: isMobile ? 5 : 5, 
                      left: isMobile ? 110 : 5, 
                      bottom: 10 
                    }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis type="number" stroke="var(--muted)" style={{ fontSize: isMobile ? 12 : 12 }} />
                      <YAxis 
                        dataKey="origin" 
                        type="category" 
                        stroke="var(--muted)"
                        style={{ fontSize: isMobile ? 12 : 12 }}
                        width={isMobile ? 120 : 100}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--panel)", 
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          color: "var(--text)"
                        }}
                      />
                      <Bar dataKey="count" fill="#f59e0b" radius={[0, 8, 8, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Atendimento & Qualidade */}
        {(stats?.first_response_time_ms_avg != null ||
          stats?.resolution_time_ms_avg != null ||
          stats?.assistant_latency_p50 != null ||
          stats?.assistant_latency_p95 != null ||
          stats?.takeover_rate != null) && (
          <div className="profile-card" style={{ display: "grid", gap: 12 }}>
            <div className="profile-title">Atendimento & Qualidade</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
              {typeof stats?.first_response_time_ms_avg === "number" && (
                <StatCard title="FRT médio" valueLabel={`${Math.round(stats.first_response_time_ms_avg / 1000)}s`} />
              )}
              {typeof stats?.resolution_time_ms_avg === "number" && (
                <StatCard title="TMR médio" valueLabel={hhmm(stats.resolution_time_ms_avg / 1000)} />
              )}
              {typeof stats?.assistant_latency_p50 === "number" && (
                <StatCard title="Latência p50" valueLabel={`${Math.round(stats.assistant_latency_p50)} ms`} />
              )}
              {typeof stats?.assistant_latency_p95 === "number" && (
                <StatCard title="Latência p95" valueLabel={`${Math.round(stats.assistant_latency_p95)} ms`} />
              )}
              {takeoverPct != null && (
                <div className="stat-cardx" style={{ textAlign: "center" }}>
                  <div className="stat-kpi">{takeoverPct}%</div>
                  <div className="stat-label" style={{ marginTop: 6 }}>Takeover humano</div>
                  <ProgressBar value={takeoverPct} max={100} />
                </div>
              )}
            </div>
          </div>
        )}



        {/* Top contatos */}
        {stats?.top_contacts?.length ? (
          <div className="profile-card" style={{ display: "grid", gap: 12 }}>
            <div className="profile-title">Top contatos</div>
            <div style={{ overflowX: "auto" }}>
              <table className="small" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <Th>Contato</Th>
                    <Th>Total msgs</Th>
                    <Th>Último contato</Th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top_contacts!.map((c) => (
                    <tr key={c.id}>
                      <Td>{c.name || c.id}</Td>
                      <Td align="right">{c.total_msgs ?? 0}</Td>
                      <Td>{formatDate(c.last_at)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {/* WhatsApp & Tokens */}
        {(stats?.wa_templates_month != null || stats?.wa_sessions_month != null || stats?.tokens_month) && (
          <div className="profile-card" style={{ display: "grid", gap: 16 }}>
            <div className="profile-title">Uso de canais & custo</div>

            {(typeof stats?.wa_templates_month === "number" || typeof stats?.wa_sessions_month === "number") && (
              <div style={{ display: "grid", gap: 10 }}>
                <div className="small" style={{ fontWeight: 600 }}>WhatsApp (mês atual)</div>
                <MiniBar
                  a={stats?.wa_templates_month ?? 0}
                  b={stats?.wa_sessions_month ?? 0}
                  labelA="Templates"
                  labelB="Sessões (24h)"
                />
              </div>
            )}

            {stats?.tokens_month && (
              <div style={{ display: "grid", gap: 10 }}>
                <div className="small" style={{ fontWeight: 600 }}>Tokens (mês atual)</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 12 }}>
                  <StatCard title="Prompt tokens" value={stats.tokens_month.prompt ?? 0} />
                  <StatCard title="Completion tokens" value={stats.tokens_month.completion ?? 0} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tabela por dia + Tempo ganho */}
        <div style={{ display: "grid", gap: 14 }}>
          <div className="profile-card" style={{ display: "grid", gap: 12 }}>
            <div className="profile-title">Relação de mensagens por dia</div>
            <div style={{ overflowX: "auto" }}>
              <table className="small" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <Th>Data</Th>
                    <Th>Você</Th>
                    <Th>Assistente</Th>
                    <Th>Total</Th>
                  </tr>
                </thead>
                <tbody>
                  {chartData.map((d) => {
                    const tot = d.user + d.assistant;
                    return (
                      <tr key={d.date}>
                        <Td>{d.date}</Td>
                        <Td align="right">{d.user}</Td>
                        <Td align="right">{d.assistant}</Td>
                        <Td align="right"><strong>{tot}</strong></Td>
                      </tr>
                    );
                  })}
                  {!chartData.length && (
                    <tr><Td colSpan={4} align="center">Sem dados ainda.</Td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div className="profile-card" style={{ display: "grid", gap: 16 }}>
            <div className="profile-title">Tempo ganho (assistente vs. humano)</div>
            <div className="small" style={{ lineHeight: 1.6 }}>
              Baseado em <strong>{totalAssistant}</strong> respostas da assistente:
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 14 }}>
              <StatCard title="Se fosse humano" valueLabel={hhmm(totalAssistant * humanSecondsPerMsg)} />
              <StatCard title="Com a assistente" valueLabel={hhmm(totalAssistant * assistantSecondsPerMsg)} />
              <StatCard title="Tempo ganho" valueLabel={hhmm(timeSavedSeconds)} />
            </div>
            <div className="small" style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <label htmlFor="human-seconds">Tempo humano por mensagem:</label>
              <input
                id="human-seconds"
                type="number"
                min={1}
                max={600}
                step={1}
                value={humanSecondsPerMsg}
                onChange={(e) => {
                  const v = Math.max(1, Number(e.target.value) || 1);
                  setHumanSecondsPerMsg(v);
                }}
                style={{ width: 100, padding: "6px 8px", borderRadius: 8, border: "1px solid var(--border)", background: "transparent", color: "var(--text)" }}
              />
              <span style={{ opacity: 0.8 }}>(padrão: 45s)</span>
            </div>
          </div>
        </div>

        {/* Onboarding */}
        {(stats?.onboarding_total_steps || stats?.is_onboarded) && (
          <div className="profile-card" style={{ display: "grid", gap: 12 }}>
            <div className="profile-title">Onboarding</div>
            {stats?.is_onboarded ? (
              <div className="small">✅ Onboarding concluído.</div>
            ) : (
              <>
                <div className="small">
                  Progresso:{" "}
                  <strong>
                    {stats?.onboarding_current_step ?? 0}/{stats?.onboarding_total_steps ?? 0}
                  </strong>
                </div>
                <ProgressBar
                  value={stats?.onboarding_current_step ?? 0}
                  max={stats?.onboarding_total_steps ?? 0}
                />
                <div>
                  <button className="btn">Continuar onboarding</button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** =========================
 * Helpers visuais
 * ========================= */
function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="kv"><span className="kv-k">{k}</span><span className="kv-v">{v}</span></div>
  );
}

function StatCard({ title, value, valueLabel }: { title: string; value?: number; valueLabel?: string }) {
  return (
    <div className="stat-cardx" style={{ textAlign: "center" }}>
      <div className="stat-kpi">{typeof valueLabel === "string" ? valueLabel : value ?? 0}</div>
      <div className="stat-label" style={{ marginTop: 6 }}>{title}</div>
    </div>
  );
}
function Th({ children }: { children: React.ReactNode }) {
  return (
    <th style={{ textAlign: "left", fontWeight: 600, padding: "8px 10px", borderBottom: "1px solid var(--border)", whiteSpace: "nowrap" }}>
      {children}
    </th>
  );
}
function Td({ children, align, colSpan }: { children: React.ReactNode; align?: "left" | "right" | "center"; colSpan?: number }) {
  return (
    <td style={{ textAlign: align || "left", padding: "8px 10px", borderBottom: "1px solid var(--soft)", whiteSpace: "nowrap" }} colSpan={colSpan}>
      {children}
    </td>
  );
}
