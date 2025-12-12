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
  LineChart,
  Line,
} from "recharts";
import { useAuth } from "../auth";
import { getProfile, getUsage, getStats, getAnalyticsSummary, getSalesByDay } from "../api";

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
  threads?: number;
  total_messages?: number;
  user_messages?: number;
  assistant_messages?: number;
  last_activity?: string | null;
  messages_by_day?: MessagesByDay[];
  avg_assistant_response_ms?: number | null;
  first_response_time_ms_avg?: number | null;
  resolution_time_ms_avg?: number | null;
  assistant_latency_p50?: number | null;
  assistant_latency_p95?: number | null;
  takeover_rate?: number | null;
  lead_levels?: { frio?: number; morno?: number; quente?: number } | null;
  active_days_30d?: number | null;
  messages_by_hour?: number[] | null;
  messages_heatmap?: number[][] | null;
  top_contacts?: TopContact[] | null;
  wa_templates_month?: number | null;
  wa_sessions_month?: number | null;
  tokens_month?: { prompt?: number; completion?: number } | null;
  onboarding_total_steps?: number | null;
  onboarding_current_step?: number | null;
  is_onboarded?: boolean | null;
  threads_growth?: Array<{ date: string; count: number }>;
  origin_distribution?: Array<{ origin: string; count: number }>;
  response_rate?: number;
};

type AnalyticsSummary = {
  total_threads: number;
  total_contacts: number;
  total_sales: number;
  total_revenue: number; // em centavos
  sales_with_conversation: number;
  sales_without_conversation: number;
  total_subscriptions: number;
  active_subscriptions: number;
};

type SalesByDay = {
  date: string;
  qtd_vendas: number;
  valor_total: number; // em centavos
};

/** =========================
 * Utils
 * ========================= */
function formatDate(dt?: string | number | Date | null) {
  if (!dt) return "—";
  const d = new Date(dt);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

function formatDateTime(dt?: string | number | Date | null) {
  if (!dt) return "—";
  const d = new Date(dt);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatCurrency(cents: number) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
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

function formatTime(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

/** =========================
 * Componentes Visuais
 * ========================= */
function ProgressBar({ value, max = 100, color = "var(--primary-color)" }: { value: number; max?: number; color?: string }) {
  const pct = max > 0 ? clamp((value / max) * 100, 0, 100) : 0;
  return (
    <div style={{ width: "100%", height: 8, background: "var(--panel)", borderRadius: 999, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: color, transition: "width 0.3s ease" }} />
    </div>
  );
}

function StatCard({ 
  title, 
  value, 
  valueLabel, 
  subtitle,
  trend,
  color = "var(--primary-color)",
}: { 
  title: string; 
  value?: number; 
  valueLabel?: string;
  subtitle?: string;
  trend?: { value: number; label: string };
  color?: string;
}) {
  return (
    <div className="card" style={{ padding: 20, position: "relative", overflow: "hidden" }}>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {title}
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, color, marginBottom: subtitle ? 4 : 0 }}>
        {typeof valueLabel === "string" ? valueLabel : value ?? 0}
      </div>
      {subtitle && (
        <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
          {subtitle}
        </div>
      )}
      {trend && (
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          gap: 4, 
          marginTop: 8,
          fontSize: 12,
          color: trend.value >= 0 ? "var(--success)" : "var(--danger)",
        }}>
          <span>{trend.value >= 0 ? "↑" : "↓"}</span>
          <span>{trend.label}</span>
        </div>
      )}
    </div>
  );
}

function MiniBar({ a, b, labelA, labelB, colorA = "#6366f1", colorB = "#10b981" }: { 
  a: number; 
  b: number; 
  labelA: string; 
  labelB: string;
  colorA?: string;
  colorB?: string;
}) {
  const tot = Math.max(0, a + b);
  const pa = tot ? (a / tot) * 100 : 0;
  const pb = tot ? (b / tot) * 100 : 0;
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 12, height: 12, borderRadius: 3, background: colorA }} />
          <span className="small" style={{ fontWeight: 500 }}>{labelA}: <strong>{a}</strong></span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div style={{ width: 12, height: 12, borderRadius: 3, background: colorB }} />
          <span className="small" style={{ fontWeight: 500 }}>{labelB}: <strong>{b}</strong></span>
        </div>
        {tot > 0 && (
          <span className="small" style={{ marginLeft: "auto", opacity: 0.7 }}>Total: {tot}</span>
        )}
      </div>
      {tot > 0 && (
        <div style={{ height: 10, borderRadius: 999, overflow: "hidden", display: "flex", background: "var(--panel)" }}>
          <div style={{ width: `${pa}%`, background: colorA, transition: "width 0.3s ease" }} />
          <div style={{ width: `${pb}%`, background: colorB, transition: "width 0.3s ease" }} />
        </div>
      )}
    </div>
  );
}

function LeadDistribution({ frio = 0, morno = 0, quente = 0 }: { frio?: number; morno?: number; quente?: number }) {
  const tot = Math.max(0, frio + morno + quente);
  const pct = (x: number) => (tot ? Math.round((x / tot) * 100) : 0);
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <div className="chip" style={{ background: "#0f172a", color: "#93c5fd", border: "1px solid #1d4ed8", fontSize: 12, padding: "6px 12px" }}>
          Frio: <strong style={{ marginLeft: 4 }}>{frio}</strong> ({pct(frio)}%)
        </div>
        <div className="chip" style={{ background: "#1f2937", color: "#fde68a", border: "1px solid #f59e0b", fontSize: 12, padding: "6px 12px" }}>
          Morno: <strong style={{ marginLeft: 4 }}>{morno}</strong> ({pct(morno)}%)
        </div>
        <div className="chip" style={{ background: "#2d0f12", color: "#fecaca", border: "1px solid #dc2626", fontSize: 12, padding: "6px 12px" }}>
          Quente: <strong style={{ marginLeft: 4 }}>{quente}</strong> ({pct(quente)}%)
        </div>
      </div>
      {tot > 0 && (
        <div style={{ height: 10, borderRadius: 999, overflow: "hidden", display: "flex", background: "var(--panel)" }}>
          <div style={{ width: `${pct(frio)}%`, background: "#1d4ed8" }} />
          <div style={{ width: `${pct(morno)}%`, background: "#f59e0b" }} />
          <div style={{ width: `${pct(quente)}%`, background: "#dc2626" }} />
        </div>
      )}
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
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [salesByDay, setSalesByDay] = useState<SalesByDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [humanSecondsPerMsg, setHumanSecondsPerMsg] = useState<number>(45);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

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
        const [pRes, uRes, sRes, aRes, sbdRes] = await Promise.allSettled([
          getProfile?.(),
          getUsage?.(),
          getStats?.(),
          getAnalyticsSummary ? getAnalyticsSummary() : Promise.resolve(null),
          getSalesByDay ? getSalesByDay(30) : Promise.resolve([]),
        ]);
        if (pRes.status === "fulfilled" && pRes.value) setProfile(pRes.value);
        if (uRes.status === "fulfilled" && uRes.value) setUsage(uRes.value);
        if (sRes.status === "fulfilled" && sRes.value) setStatsState(sRes.value as StatsResponse);
        if (aRes.status === "fulfilled" && aRes.value) setAnalytics(aRes.value);
        if (sbdRes.status === "fulfilled" && sbdRes.value) setSalesByDay(Array.isArray(sbdRes.value) ? sbdRes.value : []);
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
  const msgsPerThread = (totalMsgs && stats?.threads) ? (totalMsgs / (stats.threads || 1)) : 0;
  const takeoverPct = typeof stats?.takeover_rate === "number" ? Math.round(stats.takeover_rate * 100) : null;

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
    const counts = stats?.lead_levels || { quente: 0, morno: 0, frio: 0 };
    return [
      { name: "Quente", value: counts.quente || 0, color: "#dc2626" },
      { name: "Morno", value: counts.morno || 0, color: "#f59e0b" },
      { name: "Frio", value: counts.frio || 0, color: "#1d4ed8" },
    ].filter((item) => item.value > 0);
  }, [stats?.lead_levels]);

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

  // Vendas por dia
  const salesChartData = useMemo(() => {
    if (!salesByDay || salesByDay.length === 0) return [];
    return salesByDay.map((d) => ({
      date: new Date(d.date).toLocaleDateString("pt-BR", { month: "short", day: "numeric" }),
      vendas: d.qtd_vendas,
      receita: d.valor_total / 100, // converte centavos para reais
    }));
  }, [salesByDay]);

  // Tempo ganho
  const assistantSecondsPerMsg = (stats?.avg_assistant_response_ms ?? 3000) / 1000;
  const assistantMsgs = totalAssistant;
  const timeHuman = assistantMsgs * humanSecondsPerMsg;
  const timeAssistant = assistantMsgs * assistantSecondsPerMsg;
  const timeSavedSeconds = Math.max(0, timeHuman - timeAssistant);

  // Taxa de conversão (se analytics disponível)
  const conversionRate = analytics && analytics.total_threads > 0
    ? ((analytics.sales_with_conversation / analytics.total_threads) * 100).toFixed(1)
    : null;

  // Skeleton
  if (loading) {
    return (
      <div style={{ 
        padding: 24, 
        display: "grid", 
        gap: 20,
        minHeight: "calc(100vh - 56px)",
      }}>
        <div className="card skeleton" style={{ height: 120 }} />
        <div className="card skeleton" style={{ height: 200 }} />
        <div className="card skeleton" style={{ height: 320 }} />
      </div>
    );
  }

  return (
    <div style={{ 
      minHeight: "calc(100vh - 56px)",
      background: "var(--bg)",
    }}>
      {/* Header moderno */}
      <div style={{
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
        padding: isMobile ? "20px 16px" : "24px 32px",
      }}>
        <div style={{
          maxWidth: 1400,
          margin: "0 auto",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 16,
          flexWrap: "wrap",
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <button 
              className="btn ghost" 
              onClick={() => navigate(-1)} 
              style={{ 
                marginBottom: 12,
                fontSize: 13,
                padding: "6px 12px",
              }}
            >
              ← Voltar
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <div style={{
                width: 64,
                height: 64,
                borderRadius: "var(--radius-lg)",
                background: "var(--primary-soft)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 28,
                fontWeight: 700,
                color: "var(--primary-color)",
                flexShrink: 0,
              }}>
                {initials(data.name, data.email)}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h1 style={{ 
                  margin: 0, 
                  fontSize: isMobile ? 24 : 28,
                  fontWeight: 700,
                  marginBottom: 6,
                }}>
                  {data.name || "Usuário"}
                </h1>
                <div style={{ 
                  display: "flex", 
                  flexWrap: "wrap", 
                  gap: 12, 
                  alignItems: "center",
                  fontSize: 14,
                  color: "var(--text-muted)",
                }}>
                  <span>{data.email}</span>
                  <span className="badge badge-primary">{planLabel}</span>
                  {stats?.last_activity && (
                    <span>Última atividade: {formatDate(stats.last_activity)}</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Conteúdo principal */}
      <div style={{
        maxWidth: 1400,
        margin: "0 auto",
        padding: isMobile ? "20px 16px" : "32px",
      }}>
        {err && (
          <div className="card" style={{ 
            border: "1px solid var(--danger)", 
            background: "var(--danger-soft)", 
            color: "var(--danger)", 
            padding: 16,
            marginBottom: 24,
          }}>
            {err}
          </div>
        )}

        {/* Métricas principais */}
        <div style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 16,
          marginBottom: 24,
        }}>
          <StatCard 
            title="Conversas" 
            value={stats?.threads ?? usage?.threads_total ?? 0}
            color="var(--primary-color)"
          />
          <StatCard 
            title="Mensagens Total" 
            value={totalMsgs}
            color="var(--secondary-color)"
          />
          <StatCard 
            title="Mensagens Enviadas" 
            value={totalUser}
            subtitle={`${totalAssistant} respostas do assistente`}
            color="#6366f1"
          />
          {analytics && (
            <>
              <StatCard 
                title="Vendas Totais" 
                value={analytics.total_sales}
                subtitle={`${analytics.sales_with_conversation} com conversa`}
                color="var(--success)"
              />
              <StatCard 
                title="Receita Total" 
                valueLabel={formatCurrency(analytics.total_revenue)}
                subtitle={`${analytics.active_subscriptions} assinaturas ativas`}
                color="var(--success)"
              />
            </>
          )}
          {typeof stats?.active_days_30d === "number" && (
            <StatCard 
              title="Dias Ativos (30d)" 
              value={stats.active_days_30d}
              subtitle={`${Math.round((stats.active_days_30d / 30) * 100)}% do período`}
              color="var(--primary-color)"
            />
          )}
        </div>

        {/* Seção de Vendas e Receita */}
        {analytics && (
          <div className="card" style={{ padding: 24, marginBottom: 24 }}>
            <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
              Vendas e Receita
            </h3>
            <div style={{
              display: "grid",
              gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 16,
              marginBottom: 24,
            }}>
              <div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Total de Vendas
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--success)", marginBottom: 4 }}>
                  {analytics.total_sales}
                </div>
                <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  {analytics.sales_with_conversation} com conversa • {analytics.sales_without_conversation} sem conversa
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Receita Total
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--success)", marginBottom: 4 }}>
                  {formatCurrency(analytics.total_revenue)}
                </div>
                <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  Ticket médio: {analytics.total_sales > 0 ? formatCurrency(analytics.total_revenue / analytics.total_sales) : "—"}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Assinaturas
                </div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "var(--primary-color)", marginBottom: 4 }}>
                  {analytics.active_subscriptions}/{analytics.total_subscriptions}
                </div>
                <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  {analytics.total_subscriptions > 0 ? Math.round((analytics.active_subscriptions / analytics.total_subscriptions) * 100) : 0}% ativas
                </div>
              </div>
              {conversionRate && (
                <div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                    Taxa de Conversão
                  </div>
                  <div style={{ fontSize: 28, fontWeight: 700, color: "var(--secondary-color)", marginBottom: 4 }}>
                    {conversionRate}%
                  </div>
                  <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
                    {analytics.sales_with_conversation} vendas de {analytics.total_threads} conversas
                  </div>
                </div>
              )}
            </div>

            {/* Gráfico de vendas por dia */}
            {salesChartData.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text)" }}>
                  Vendas por Dia (últimos 30 dias)
                </div>
                <div style={{ width: "100%", height: isMobile ? 300 : 280 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={salesChartData} margin={{ top: 10, right: 10, left: 0, bottom: isMobile ? 50 : 30 }}>
                      <defs>
                        <linearGradient id="colorVendas" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorReceita" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis 
                        dataKey="date" 
                        stroke="var(--text-muted)"
                        style={{ fontSize: isMobile ? 10 : 12 }}
                        angle={isMobile ? -90 : -45}
                        textAnchor="end"
                        height={isMobile ? 80 : 60}
                        interval={isMobile ? 2 : 0}
                      />
                      <YAxis yAxisId="left" stroke="var(--text-muted)" style={{ fontSize: 12 }} />
                      <YAxis yAxisId="right" orientation="right" stroke="var(--text-muted)" style={{ fontSize: 12 }} />
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--surface)", 
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          color: "var(--text)"
                        }}
                      />
                      <Legend />
                      <Area 
                        yAxisId="left"
                        type="monotone" 
                        dataKey="vendas" 
                        name="Vendas" 
                        stroke="#10b981" 
                        fillOpacity={1} 
                        fill="url(#colorVendas)"
                        strokeWidth={2}
                      />
                      <Area 
                        yAxisId="right"
                        type="monotone" 
                        dataKey="receita" 
                        name="Receita (R$)" 
                        stroke="#6366f1" 
                        fillOpacity={1} 
                        fill="url(#colorReceita)"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Gráficos principais */}
        <div style={{ display: "grid", gap: 24, marginBottom: 24 }}>
          {/* Mensagens por dia */}
          {chartData.length > 0 && (
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
                Mensagens por Dia
              </h3>
              <div style={{ width: "100%", height: isMobile ? 300 : 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: isMobile ? 50 : 30 }}>
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
                      stroke="var(--text-muted)"
                      style={{ fontSize: isMobile ? 10 : 12 }}
                      angle={isMobile ? -90 : -45}
                      textAnchor="end"
                      height={isMobile ? 80 : 60}
                      interval={isMobile ? 2 : 0}
                    />
                    <YAxis stroke="var(--text-muted)" style={{ fontSize: 12 }} />
                    <Tooltip 
                      contentStyle={{ 
                        background: "var(--surface)", 
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

          {/* Grid de gráficos menores */}
          <div style={{ 
            display: "grid", 
            gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", 
            gap: 24 
          }}>
            {/* Distribuição de mensagens */}
            {pieData.some((d) => d.value > 0) && (
              <div className="card" style={{ padding: 24 }}>
                <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
                  Distribuição de Mensagens
                </h3>
                <div style={{ width: "100%", height: isMobile ? 260 : 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
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
                          background: "var(--surface)", 
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

            {/* Temperatura dos Leads */}
            {leadDistribution.length > 0 && (
              <div className="card" style={{ padding: 24 }}>
                <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
                  Temperatura dos Leads
                </h3>
                <div style={{ width: "100%", height: isMobile ? 260 : 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={leadDistribution} layout="vertical" margin={{ top: 10, right: 10, left: isMobile ? 90 : 80, bottom: 10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis type="number" stroke="var(--text-muted)" style={{ fontSize: 12 }} />
                      <YAxis 
                        dataKey="name" 
                        type="category" 
                        stroke="var(--text-muted)"
                        style={{ fontSize: 12 }}
                        width={isMobile ? 100 : 80}
                      />
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--surface)", 
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
          </div>

          {/* Mensagens por hora e Crescimento */}
          <div style={{ 
            display: "grid", 
            gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr", 
            gap: 24 
          }}>
            {/* Mensagens por hora */}
            {hourlyData.some((d) => d.messages > 0) && (
              <div className="card" style={{ padding: 24 }}>
                <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
                  Mensagens por Hora do Dia
                </h3>
                <div style={{ width: "100%", height: isMobile ? 300 : 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={hourlyData} margin={{ top: 10, right: 10, left: 0, bottom: isMobile ? 60 : 30 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis 
                        dataKey="hour" 
                        stroke="var(--text-muted)"
                        style={{ fontSize: isMobile ? 10 : 11 }}
                        angle={isMobile ? -90 : -45}
                        textAnchor="end"
                        height={isMobile ? 80 : 60}
                        interval={isMobile ? 2 : 0}
                      />
                      <YAxis stroke="var(--text-muted)" style={{ fontSize: 12 }} />
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--surface)", 
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

            {/* Crescimento de conversas */}
            {growthData.length > 0 && (
              <div className="card" style={{ padding: 24 }}>
                <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
                  Crescimento de Conversas (30 dias)
                </h3>
                <div style={{ width: "100%", height: isMobile ? 300 : 240 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={growthData} margin={{ top: 10, right: 10, left: 0, bottom: isMobile ? 60 : 30 }}>
                      <defs>
                        <linearGradient id="colorGrowthProfile" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis 
                        dataKey="date" 
                        stroke="var(--text-muted)"
                        style={{ fontSize: isMobile ? 10 : 11 }}
                        angle={isMobile ? -90 : -45}
                        textAnchor="end"
                        height={isMobile ? 80 : 60}
                        interval={isMobile ? 2 : 0}
                      />
                      <YAxis stroke="var(--text-muted)" style={{ fontSize: 12 }} />
                      <Tooltip 
                        contentStyle={{ 
                          background: "var(--surface)", 
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
          </div>

          {/* Origem dos contatos */}
          {originData.length > 0 && (
            <div className="card" style={{ padding: 24 }}>
              <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
                Origem dos Contatos
              </h3>
              <div style={{ width: "100%", height: isMobile ? 300 : 240 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={originData} layout="vertical" margin={{ top: 10, right: 10, left: isMobile ? 110 : 100, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis type="number" stroke="var(--text-muted)" style={{ fontSize: 12 }} />
                    <YAxis 
                      dataKey="origin" 
                      type="category" 
                      stroke="var(--text-muted)"
                      style={{ fontSize: 12 }}
                      width={isMobile ? 120 : 100}
                    />
                    <Tooltip 
                      contentStyle={{ 
                        background: "var(--surface)", 
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

        {/* Métricas de Performance */}
        <div className="card" style={{ padding: 24, marginBottom: 24 }}>
          <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
            Performance e Qualidade
          </h3>
          <div style={{
            display: "grid",
            gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 16,
          }}>
            {typeof stats?.avg_assistant_response_ms === "number" && (
              <div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Tempo Médio de Resposta
                </div>
                <div style={{ fontSize: 24, fontWeight: 700, color: "var(--primary-color)" }}>
                  {(stats.avg_assistant_response_ms / 1000).toFixed(1)}s
                </div>
              </div>
            )}
            {typeof stats?.response_rate === "number" && (
              <div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Taxa de Resposta
                </div>
                <div style={{ fontSize: 24, fontWeight: 700, color: "var(--success)" }}>
                  {stats.response_rate}%
                </div>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>
                  Conversas com resposta do assistente
                </div>
              </div>
            )}
            {takeoverPct != null && (
              <div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Takeover Humano
                </div>
                <div style={{ fontSize: 24, fontWeight: 700, color: "var(--warning)" }}>
                  {takeoverPct}%
                </div>
                <ProgressBar value={takeoverPct} max={100} color="var(--warning)" />
              </div>
            )}
            {Number.isFinite(msgsPerThread) && (
              <div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  Média Mensagens/Conversa
                </div>
                <div style={{ fontSize: 24, fontWeight: 700, color: "var(--text)" }}>
                  {msgsPerThread.toFixed(1)}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Tempo ganho */}
        {totalAssistant > 0 && (
          <div className="card" style={{ padding: 24, marginBottom: 24 }}>
            <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
              Eficiência e Tempo Ganho
            </h3>
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 14, color: "var(--text-muted)", marginBottom: 12 }}>
                Baseado em <strong>{totalAssistant}</strong> respostas do assistente:
              </div>
              <div style={{
                display: "grid",
                gridTemplateColumns: isMobile ? "1fr" : "repeat(3, 1fr)",
                gap: 16,
                marginBottom: 20,
              }}>
                <StatCard 
                  title="Se fosse humano" 
                  valueLabel={formatTime(totalAssistant * humanSecondsPerMsg)}
                  color="var(--danger)"
                />
                <StatCard 
                  title="Com a assistente" 
                  valueLabel={formatTime(totalAssistant * assistantSecondsPerMsg)}
                  color="var(--primary-color)"
                />
                <StatCard 
                  title="Tempo ganho" 
                  valueLabel={formatTime(timeSavedSeconds)}
                  color="var(--success)"
                />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <label htmlFor="human-seconds" style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  Tempo humano por mensagem:
                </label>
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
                  className="input"
                  style={{ width: 100 }}
                />
                <span style={{ fontSize: 12, color: "var(--text-muted)", opacity: 0.7 }}>
                  (padrão: 45s)
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Distribuição de leads */}
        {stats?.lead_levels && (
          <div className="card" style={{ padding: 24, marginBottom: 24 }}>
            <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
              Distribuição de Leads por Temperatura
            </h3>
            <LeadDistribution 
              frio={stats.lead_levels.frio || 0}
              morno={stats.lead_levels.morno || 0}
              quente={stats.lead_levels.quente || 0}
            />
          </div>
        )}

        {/* Top contatos */}
        {stats?.top_contacts && stats.top_contacts.length > 0 && (
          <div className="card" style={{ padding: 24, marginBottom: 24 }}>
            <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
              Top Contatos
            </h3>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", fontWeight: 600, padding: "12px", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                      Contato
                    </th>
                    <th style={{ textAlign: "right", fontWeight: 600, padding: "12px", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                      Total Mensagens
                    </th>
                    <th style={{ textAlign: "left", fontWeight: 600, padding: "12px", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                      Último Contato
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {stats.top_contacts.map((c) => (
                    <tr key={c.id}>
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-light)", fontSize: 14 }}>
                        {c.name || `Contato #${c.id}`}
                      </td>
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-light)", textAlign: "right", fontSize: 14, fontWeight: 600 }}>
                        {c.total_msgs ?? 0}
                      </td>
                      <td style={{ padding: "12px", borderBottom: "1px solid var(--border-light)", fontSize: 13, color: "var(--text-muted)" }}>
                        {formatDateTime(c.last_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Informações da conta */}
        <div className="card" style={{ padding: 24 }}>
          <h3 style={{ margin: "0 0 20px 0", fontSize: 18, fontWeight: 600 }}>
            Informações da Conta
          </h3>
          <div style={{
            display: "grid",
            gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 16,
          }}>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                ID
              </div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{String(data.id)}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Plano
              </div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{planLabel}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Criado em
              </div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{formatDate(data.created_at)}</div>
            </div>
            <div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                Última Atividade
              </div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>
                {formatDateTime(stats?.last_activity ?? data.last_activity_at)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
