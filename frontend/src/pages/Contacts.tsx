// frontend/src/pages/Contacts.tsx
import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listThreads, updateThread, getMessages, type Thread } from "../api";
import { getOverrideLevel, type LeadLevel } from "../hooks/useLeadScore";
import { computeLeadScoreFromMessages, levelFromScore } from "../utils/leadScore";
import type { UIMessage } from "../types/lead";
import { INITIAL_FUNNELS } from "../data/funnels";
import { INITIAL_AUDIOS } from "../data/audios";
import type { AutomationAction } from "../types/funnel";

/** ===== Visual helpers ===== */
type Row = Thread & {
  _lastText?: string;
  _lastAt?: string;
  _phone?: string;
  _level?: LeadLevel;
  _score?: number;
};
function chipColors(level: LeadLevel) {
  switch (level) {
    case "quente":
      return { bg: "#2d0f12", fg: "#fecaca", bd: "#dc2626" };
    case "morno":
      return { bg: "#1f2937", fg: "#fde68a", bd: "#f59e0b" };
    case "frio":
      return { bg: "#0f172a", fg: "#93c5fd", bd: "#1d4ed8" };
    default:
      return { bg: "var(--panel)", fg: "var(--muted)", bd: "var(--border)" };
  }
}
function LeadTag({ level, score }: { level: LeadLevel; score?: number }) {
  const { bg, fg, bd } = chipColors(level);
  const label = level === "quente" ? "Quente" : level === "morno" ? "Morno" : level === "frio" ? "Frio" : "—";
  return (
    <span className="chip" style={{ background: bg, color: fg, border: `1px solid ${bd}` }}>
      {label}
      {typeof score === "number" ? ` (${score})` : ""}
    </span>
  );
}
function getDisplayName(t: Thread) {
  const title = String(t.title || "").trim();
  if (title) return title;
  const wa = (t.metadata?.wa_id || t.metadata?.phone || "").toString();
  if (wa) return `Contato • ${wa.slice(-4)}`;
  return "Sem nome";
}
function getPhone(t: Thread) {
  const raw =
    (t as any)?.metadata?.wa_id ||
    (t as any)?.metadata?.phone ||
    (t as any)?.external_user_phone ||
    "";
  const s = String(raw).trim();
  if (!s) return "";
  const e164 = s.startsWith("whatsapp:") ? s.replace(/^whatsapp:/, "") : s;
  return e164.startsWith("+") ? e164 : `+${e164}`;
}
function fmtTimeShort(iso?: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString();
}

type AutomationStatus = "em_fluxo" | "pausado" | "concluido" | "nao_entrou";

export default function Contacts() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [origin, setOrigin] = useState<string>("");
  const [level, setLevel] = useState<"todos" | "frio" | "morno" | "quente">("todos");
  const [filterFunnel, setFilterFunnel] = useState<string>("all");
  const [filterStage, setFilterStage] = useState<string>("all");
  const [filterProduct, setFilterProduct] = useState<string>("all");
  const [filterAutomationStatus, setFilterAutomationStatus] = useState<string>("all");
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" }>({ key: "ultimo", dir: "desc" });
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  
  // Modais
  const [showFlowModal, setShowFlowModal] = useState<{ threadId: number | string } | null>(null);
  const [showForceStageModal, setShowForceStageModal] = useState<{ threadId: number | string } | null>(null);
  const [automationActions, setAutomationActions] = useState<Record<string, AutomationAction[]>>({});
  const [forceStageFunnel, setForceStageFunnel] = useState<string>("");
  const [forceStageStage, setForceStageStage] = useState<string>("");
  const [savingStage, setSavingStage] = useState(false);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Inicializa valores do modal Forçar Etapa quando abre
  useEffect(() => {
    if (showForceStageModal) {
      const thread = rows.find(t => String(t.id) === showForceStageModal.threadId);
      if (thread) {
        const funnelId = (thread as any).funnel_id || (thread as any).metadata?.funnel_id;
        const stageId = (thread as any).stage_id || (thread as any).metadata?.stage_id;
        setForceStageFunnel(String(funnelId || ""));
        setForceStageStage(String(stageId || ""));
      }
    } else {
      setForceStageFunnel("");
      setForceStageStage("");
    }
  }, [showForceStageModal?.threadId, rows]);

  /** Carrega threads + enriquece com telefone e temperatura (OTIMIZADO: usa last_message do backend) */
  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const ts = await listThreads();
        const base: Row[] = ts.map(t => {
          const beScore = (t as any).lead_score as number | undefined;
          const beLevel = (t as any).lead_level as LeadLevel | undefined;
          const override = getOverrideLevel(String(t.id));
          const levelEff: LeadLevel =
            override && override !== "desconhecido"
              ? override
              : beLevel ?? levelFromScore(beScore);
          const scoreEff = typeof beScore === "number" ? beScore : undefined;
          
          // Usa last_message do backend se disponível (não precisa carregar todas as mensagens)
          const lastText = t.last_message || undefined;
          const lastAt = t.last_message_at || undefined;
          
          return { 
            ...t, 
            _phone: getPhone(t), 
            _level: levelEff, 
            _score: scoreEff,
            _lastText: lastText,
            _lastAt: lastAt,
          };
        });
        setRows(base);

        // Carrega mensagens para threads que não têm score do backend (mesmo que tenham last_message)
        // Isso garante que o score seja calculado localmente quando necessário
        const needsMessages = base.filter(t => 
          typeof t._score !== "number"
        );
        
        if (needsMessages.length > 0) {
          const CONC = 4;
          for (let i = 0; i < needsMessages.length; i += CONC) {
            await Promise.all(
              needsMessages.slice(i, i + CONC).map(async t => {
                try {
                  const msgs = (await getMessages(Number(t.id))) as UIMessage[];
                  if (!msgs?.length) return;
                  const last = msgs[msgs.length - 1];
                  const localScore = computeLeadScoreFromMessages(msgs);
                  // Recalcula o level considerando override, beLevel e score local
                  const override = getOverrideLevel(String(t.id));
                  const beLevel = (t as any).lead_level as LeadLevel | undefined;
                  const localLevel: LeadLevel = 
                    override && override !== "desconhecido"
                      ? override
                      : beLevel ?? levelFromScore(localScore);
                  setRows(prev =>
                    prev.map(r =>
                      r.id === t.id
                        ? { 
                            ...r, 
                            _lastText: last.content, 
                            _lastAt: last.created_at, 
                            _score: localScore, 
                            _level: localLevel 
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
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  /** Atualização leve a cada 15s (sincroniza level/score vindos do backend e mantém override) */
  useEffect(() => {
    const id = window.setInterval(async () => {
      const ts = await listThreads();
      setRows(prev => {
        const map = new Map(prev.map(r => [String(r.id), r]));
        for (const t of ts) {
          const r = map.get(String(t.id));
          const beScore = (t as any).lead_score as number | undefined;
          const beLevel = (t as any).lead_level as LeadLevel | undefined;
          const override = getOverrideLevel(String(t.id));
          const levelEff: LeadLevel =
            override && override !== "desconhecido"
              ? override
              : beLevel ?? (r?._score !== undefined ? levelFromScore(r?._score) : r?._level ?? "desconhecido");
          const scoreEff = typeof beScore === "number" ? beScore : r?._score;
          // Preserva campos do metadata que vêm achatados do backend
          const updatedRow = { 
            ...(r || (t as Row)), 
            origin: t.origin, 
            _level: levelEff, 
            _score: scoreEff,
            // Garante que campos achatados estão presentes (vêm do backend ou do metadata)
            funnel_id: (t as any).funnel_id || (t as any).metadata?.funnel_id,
            stage_id: (t as any).stage_id || (t as any).metadata?.stage_id,
            product_id: (t as any).product_id || (t as any).metadata?.product_id,
            source: (t as any).source || (t as any).metadata?.source,
            tags: (t as any).tags || (t as any).metadata?.tags,
            metadata: (t as any).metadata || {},
          };
          if (r) map.set(String(t.id), updatedRow);
          else map.set(String(t.id), { ...updatedRow, _phone: getPhone(t) });
        }
        return Array.from(map.values());
      });
    }, 15000);
    return () => clearInterval(id);
  }, []);

  // Helpers para buscar nomes
  function getFunnelName(funnelId?: number | string | null) {
    if (!funnelId) return null;
    // Compara como string para garantir compatibilidade
    const funnel = INITIAL_FUNNELS.find(f => String(f.id) === String(funnelId));
    return funnel?.name || `Funil #${funnelId}`;
  }

  function getStageName(funnelId?: number | string | null, stageId?: number | string | null) {
    if (!funnelId || !stageId) return null;
    // Compara como string para garantir compatibilidade
    const funnel = INITIAL_FUNNELS.find(f => String(f.id) === String(funnelId));
    if (!funnel) return null;
    const stage = funnel.stages.find(s => String(s.id) === String(stageId));
    return stage?.name || `Etapa #${stageId}`;
  }

  function getFunnelStageDisplay(thread: Row) {
    // Busca funnel_id e stage_id do metadata ou direto do objeto
    const funnelId = (thread as any).funnel_id || (thread as any).metadata?.funnel_id;
    const stageId = (thread as any).stage_id || (thread as any).metadata?.stage_id;
    if (!funnelId || !stageId) return "—";
    const funnelName = getFunnelName(funnelId);
    const stageName = getStageName(funnelId, stageId);
    if (!funnelName || !stageName) return "—";
    return `${funnelName} • ${stageName}`;
  }

  function getProductName(productId?: number | string | null) {
    // Busca product_id do metadata ou direto do objeto
    const pid = productId || (productId === undefined ? undefined : null);
    if (!pid) return null;
    // TODO: buscar do backend quando tiver lista de produtos
    const productMap: Record<string, string> = {
      "1": "Life PLM",
      "2": "Mentoria X",
      "3": "Life Premium",
    };
    return productMap[String(pid)] || `Produto #${pid}`;
  }

  function getAutomationStatus(thread: Row): AutomationStatus {
    // Busca funnel_id do metadata ou direto do objeto
    const funnelId = (thread as any).funnel_id || (thread as any).metadata?.funnel_id;
    if (!funnelId) return "nao_entrou";
    
    const automationActive = (thread as any)?.automation_active || (thread as any).metadata?.automation_active;
    if (automationActive === false) return "pausado";
    if (automationActive === true) return "em_fluxo";
    
    // Se tem funil mas não tem status explícito, assume em fluxo
    return "em_fluxo";
  }

  function getAutomationStatusDisplay(status: AutomationStatus) {
    const map: Record<AutomationStatus, { label: string; color: string; bg: string }> = {
      em_fluxo: { label: "Em fluxo", color: "#10b981", bg: "#10b98120" },
      pausado: { label: "Pausado", color: "#f59e0b", bg: "#f59e0b20" },
      concluido: { label: "Concluído", color: "#6366f1", bg: "#6366f120" },
      nao_entrou: { label: "Não entrou", color: "#6b7280", bg: "#6b728020" },
    };
    return map[status] || map.nao_entrou;
  }

  const origins = useMemo(() => {
    const s = new Set<string>();
    rows.forEach(t => t.origin && s.add(String(t.origin)));
    return Array.from(s).sort();
  }, [rows]);

  const funnels = useMemo(() => {
    return INITIAL_FUNNELS;
  }, []);

  const stages = useMemo(() => {
    const allStages: Array<{ id: number | string; funnelId: number | string; name: string }> = [];
    INITIAL_FUNNELS.forEach(f => {
      f.stages.forEach(s => {
        allStages.push({ id: s.id, funnelId: f.id, name: s.name });
      });
    });
    return allStages;
  }, []);

  const products = useMemo(() => {
    const s = new Set<string>();
    rows.forEach(t => {
      const pid = (t as any).product_id;
      if (pid) s.add(String(pid));
    });
    return Array.from(s).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return rows.filter(t => {
      const matchesQ =
        !s ||
        getDisplayName(t).toLowerCase().includes(s) ||
        (t._phone || "").toLowerCase().includes(s) ||
        (t._lastText || "").toLowerCase().includes(s);
      const matchesOrigin = !origin || (t.origin || "") === origin;
      const lvl = t._level && t._level !== "desconhecido" ? t._level : (t.lead_level || "frio");
      const matchesLevel = level === "todos" || lvl === level;
      
      // Novos filtros
      const funnelId = (t as any).funnel_id || (t as any).metadata?.funnel_id;
      const stageId = (t as any).stage_id || (t as any).metadata?.stage_id;
      const matchesFunnel = filterFunnel === "all" || String(funnelId || "") === filterFunnel;
      const matchesStage = filterStage === "all" || String(stageId || "") === filterStage;
      const matchesProduct = filterProduct === "all" || String((t as any).product_id || "") === filterProduct;
      
      const automationStatus = getAutomationStatus(t);
      const matchesAutomationStatus = filterAutomationStatus === "all" || automationStatus === filterAutomationStatus;
      
      return matchesQ && matchesOrigin && matchesLevel && matchesFunnel && matchesStage && matchesProduct && matchesAutomationStatus;
    });
  }, [q, origin, level, filterFunnel, filterStage, filterProduct, filterAutomationStatus, rows]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    const dir = sort.dir === "asc" ? 1 : -1;
    arr.sort((a, b) => {
      const k = sort.key;
      if (k === "nome") return getDisplayName(a).localeCompare(getDisplayName(b)) * dir;
      if (k === "numero") return (a._phone || "").localeCompare(b._phone || "") * dir;
      if (k === "origem") return (a.origin || "").localeCompare(b.origin || "") * dir;
      if (k === "score") return ((a._score ?? -1) - (b._score ?? -1)) * dir;
      if (k === "tempo") {
        const da = a._lastAt ? new Date(a._lastAt).getTime() : 0;
        const db = b._lastAt ? new Date(b._lastAt).getTime() : 0;
        return (da - db) * dir;
      }
      if (k === "level") {
        const ord = { quente: 3, morno: 2, frio: 1 } as Record<string, number>;
        const la = a._level && a._level !== "desconhecido" ? a._level : (a.lead_level || "frio");
        const lb = b._level && b._level !== "desconhecido" ? b._level : (b.lead_level || "frio");
        return ((ord[la as string] || 0) - (ord[lb as string] || 0)) * dir;
      }
      if (k === "funil") {
        const fa = getFunnelName((a as any).funnel_id) || "";
        const fb = getFunnelName((b as any).funnel_id) || "";
        return fa.localeCompare(fb) * dir;
      }
      if (k === "produto") {
        const pa = getProductName((a as any).product_id) || "";
        const pb = getProductName((b as any).product_id) || "";
        return pa.localeCompare(pb) * dir;
      }
      return 0;
    });
    return arr;
  }, [filtered, sort]);

  async function handleChangeOrigin(t: Row, next: string) {
    const old = t.origin || "";
    setRows(prev => prev.map(x => (x.id === t.id ? { ...x, origin: next || null } : x)));
    try {
      await updateThread(t.id, { origin: next || undefined });
    } catch {
      setRows(prev => prev.map(x => (x.id === t.id ? { ...x, origin: old || null } : x)));
      alert("Falha ao atualizar a origem.");
    }
  }

  function toggleSort(key: string) {
    setSort(s => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
  }

  return (
    <div style={{ 
      height: "calc(100vh - 56px)", 
      maxHeight: "calc(100vh - 56px)",
      display: "grid", 
      gridTemplateRows: "auto 1fr",
      overflow: "hidden",
    }}>
      {/* Filtros */}
      <div
        style={{
          display: "flex",
          gap: isMobile ? 6 : 8,
          alignItems: "center",
          padding: isMobile ? "8px 10px" : "10px 12px",
          borderBottom: "1px solid var(--border)",
          background: "var(--panel)",
          flexWrap: "wrap",
        }}
      >
        <input
          className="input"
          placeholder={isMobile ? "Buscar..." : "Buscar (nome, número, mensagem)..."}
          value={q}
          onChange={e => setQ(e.target.value)}
          style={{ 
            maxWidth: isMobile ? "100%" : 280,
            fontSize: isMobile ? 14 : 16,
            flex: isMobile ? "1 1 100%" : "auto",
            minWidth: isMobile ? "100%" : 200,
          }}
        />
        <select 
          className="select select--sm" 
          value={origin} 
          onChange={e => setOrigin(e.target.value)}
          style={{ 
            fontSize: isMobile ? 12 : 13,
            flex: isMobile ? "1 1 calc(50% - 3px)" : "auto",
            minWidth: isMobile ? "calc(50% - 3px)" : 140,
          }}
        >
          <option value="">Todas as origens</option>
          {[...new Set(origins)].map(o => (
            <option key={o} value={o}>
              {o.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <select 
          className="select select--sm" 
          value={level} 
          onChange={e => setLevel(e.target.value as any)}
          style={{ 
            fontSize: isMobile ? 12 : 13,
            flex: isMobile ? "1 1 calc(50% - 3px)" : "auto",
            minWidth: isMobile ? "calc(50% - 3px)" : 130,
          }}
        >
          <option value="todos">Todas as temperaturas</option>
          <option value="frio">Frio</option>
          <option value="morno">Morno</option>
          <option value="quente">Quente</option>
        </select>
        <select 
          className="select select--sm" 
          value={filterFunnel} 
          onChange={e => {
            setFilterFunnel(e.target.value);
            setFilterStage("all"); // Reset etapa quando muda funil
          }}
          style={{ 
            fontSize: isMobile ? 12 : 13,
            flex: isMobile ? "1 1 calc(50% - 3px)" : "auto",
            minWidth: isMobile ? "calc(50% - 3px)" : 160,
          }}
        >
          <option value="all">Todos os funis</option>
          {funnels.map(f => (
            <option key={f.id} value={String(f.id)}>
              {f.name}
            </option>
          ))}
        </select>
        <select 
          className="select select--sm" 
          value={filterStage} 
          onChange={e => setFilterStage(e.target.value)}
          disabled={filterFunnel === "all"}
          style={{ 
            fontSize: isMobile ? 12 : 13,
            flex: isMobile ? "1 1 calc(50% - 3px)" : "auto",
            minWidth: isMobile ? "calc(50% - 3px)" : 150,
            opacity: filterFunnel === "all" ? 0.5 : 1,
          }}
        >
          <option value="all">Todas as etapas</option>
          {filterFunnel !== "all" && stages
            .filter(s => String(s.funnelId) === filterFunnel)
            .map(s => (
              <option key={s.id} value={String(s.id)}>
                {s.name}
              </option>
            ))}
        </select>
        <select 
          className="select select--sm" 
          value={filterProduct} 
          onChange={e => setFilterProduct(e.target.value)}
          style={{ 
            fontSize: isMobile ? 12 : 13,
            flex: isMobile ? "1 1 calc(50% - 3px)" : "auto",
            minWidth: isMobile ? "calc(50% - 3px)" : 140,
          }}
        >
          <option value="all">Todos os produtos</option>
          {products.map(p => {
            const name = getProductName(p);
            return (
              <option key={p} value={p}>
                {name || `Produto #${p}`}
              </option>
            );
          })}
        </select>
        <select 
          className="select select--sm" 
          value={filterAutomationStatus} 
          onChange={e => setFilterAutomationStatus(e.target.value)}
          style={{ 
            fontSize: isMobile ? 12 : 13,
            flex: isMobile ? "1 1 calc(50% - 3px)" : "auto",
            minWidth: isMobile ? "calc(50% - 3px)" : 140,
          }}
        >
          <option value="all">Todos os status</option>
          <option value="em_fluxo">Em fluxo</option>
          <option value="pausado">Pausado</option>
          <option value="concluido">Concluído</option>
          <option value="nao_entrou">Não entrou</option>
        </select>
        <div style={{ 
          marginLeft: isMobile ? 0 : "auto", 
          color: "var(--muted)",
          width: isMobile ? "100%" : "auto",
          marginTop: isMobile ? 4 : 0,
          fontSize: isMobile ? 11 : 12,
        }} className="small">
          {sorted.length} lead(s)
        </div>
      </div>

      {/* Tabela (desktop) ou Cards (mobile) */}
      {!isMobile ? (
        <div style={{ overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: 0 }}>
          <thead style={{ position: "sticky", top: 0, background: "var(--panel)", zIndex: 1 }}>
            <tr>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                <button className="btn soft" onClick={() => toggleSort("nome")}>
                  Nome {sort.key === "nome" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
                </button>
              </th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                <button className="btn soft" onClick={() => toggleSort("numero")}>
                  Número {sort.key === "numero" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
                </button>
              </th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                <button className="btn soft" onClick={() => toggleSort("origem")}>
                  Origem {sort.key === "origem" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
                </button>
              </th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>Última mensagem</th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                <button className="btn soft" onClick={() => toggleSort("tempo")}>
                  Último contato {sort.key === "tempo" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
                </button>
              </th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                <button className="btn soft" onClick={() => toggleSort("level")}>
                  Temperatura {sort.key === "level" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
                </button>
              </th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                <button className="btn soft" onClick={() => toggleSort("score")}>
                  Score {sort.key === "score" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
                </button>
              </th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>Source</th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>Tags</th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                <button className="btn soft" onClick={() => toggleSort("funil")}>
                  Funil/Etapa {sort.key === "funil" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
                </button>
              </th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                <button className="btn soft" onClick={() => toggleSort("produto")}>
                  Produto {sort.key === "produto" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
                </button>
              </th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>Status Automação</th>
              <th style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={13} style={{ padding: 12 }} className="small">
                  Carregando…
                </td>
              </tr>
            )}
            {!loading && sorted.length === 0 && (
              <tr>
                <td colSpan={13} style={{ padding: 12, color: "var(--muted)" }} className="small">
                  Nenhum contato encontrado.
                </td>
              </tr>
            )}
            {sorted.map(t => {
              const effLevel = t._level && t._level !== "desconhecido" ? t._level : (t.lead_level || "frio");
              const effScore = typeof t._score === "number" ? t._score : ((t as any).lead_score as number | undefined);
              return (
                <tr key={t.id}>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)", maxWidth: 280 }}>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--text)" }}>
                      {getDisplayName(t)}
                    </div>
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    <code style={{ color: "var(--text)" }}>{t._phone || "—"}</code>
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    <select
                      className="select select--sm"
                      value={t.origin || ""}
                      onChange={e => handleChangeOrigin(t, e.target.value)}
                    >
                      <option value="">Sem origem</option>
                      <option value="whatsapp_organico">WhatsApp (orgânico)</option>
                      <option value="eduzz_compra">Eduzz compra</option>
                      <option value="eduzz_abandono">Eduzz abandono</option>
                      <option value="the_members">The Members</option>
                      <option value="meta_ads">Campanha (Meta)</option>
                      <option value="qr_code">QR Code</option>
                      <option value="site">Site</option>
                      <option value="indicacao">Indicação</option>
                    </select>
                  </td>
                  <td
                    style={{
                      padding: "8px 12px",
                      borderBottom: "1px solid var(--border)",
                      maxWidth: 420,
                    }}
                  >
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t._lastText || "—"}
                    </div>
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    {fmtTimeShort(t._lastAt)}
                  </td>

                  {/* Temperatura somente leitura */}
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    <LeadTag level={effLevel} score={effScore} />
                  </td>

                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    {typeof effScore === "number" ? effScore : "—"}
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    <div style={{ 
                      fontSize: 12, 
                      color: "var(--text)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      maxWidth: 150,
                    }} title={(t as any).source || (t as any).metadata?.source || ""}>
                      {(t as any).source || (t as any).metadata?.source || "—"}
                    </div>
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, maxWidth: 200 }}>
                      {(() => {
                        const tags = (t as any).tags || (t as any).metadata?.tags || [];
                        const tagsArray = Array.isArray(tags) ? tags : [];
                        return tagsArray.length > 0 ? (
                          <>
                            {tagsArray.slice(0, 2).map((tag: string, idx: number) => (
                              <span key={idx} className="chip soft" style={{ fontSize: 10, padding: "2px 6px" }}>
                                {tag}
                              </span>
                            ))}
                            {tagsArray.length > 2 && (
                              <span className="chip soft" style={{ fontSize: 10, padding: "2px 6px" }}>
                                +{tagsArray.length - 2}
                              </span>
                            )}
                          </>
                        ) : (
                          <span style={{ fontSize: 12, color: "var(--muted)" }}>—</span>
                        );
                      })()}
                    </div>
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    {(() => {
                      const display = getFunnelStageDisplay(t);
                      // Log apenas para debug (pode remover depois)
                      if (String(t.id) === "1" || String(t.id) === "2") {
                        console.log(`[RENDER] Thread ${t.id} na tabela:`, {
                          id: t.id,
                          funnel_id: (t as any).funnel_id,
                          stage_id: (t as any).stage_id,
                          metadata_funnel: (t as any).metadata?.funnel_id,
                          metadata_stage: (t as any).metadata?.stage_id,
                          display,
                          displayLength: display?.length || 0
                        });
                      }
                      return (
                        <div 
                          key={`funnel-stage-${t.id}-${(t as any).funnel_id}-${(t as any).stage_id}`}
                          style={{ 
                            fontSize: 12, 
                            color: "var(--text)",
                            maxWidth: 200,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            minHeight: 16,
                          }} 
                          title={display}
                        >
                          {display || "—"}
                        </div>
                      );
                    })()}
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    <div style={{ fontSize: 12, color: "var(--text)" }}>
                      {getProductName((t as any).product_id || (t as any).metadata?.product_id) || "—"}
                    </div>
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    {(() => {
                      const status = getAutomationStatus(t);
                      const statusDisplay = getAutomationStatusDisplay(status);
                      return (
                        <span className="chip" style={{
                          background: statusDisplay.bg,
                          color: statusDisplay.color,
                          fontSize: 11,
                          padding: "4px 8px",
                        }}>
                          {statusDisplay.label}
                        </span>
                      );
                    })()}
                  </td>
                  <td style={{ padding: "8px 12px", borderBottom: "1px solid var(--border)" }}>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <button
                        className="btn soft"
                        onClick={() => setShowFlowModal({ threadId: t.id })}
                        style={{ fontSize: 11, padding: "4px 8px" }}
                        title="Ver fluxo de automação"
                      >
                        Ver fluxo
                      </button>
                      <button
                        className="btn soft"
                        onClick={() => setShowForceStageModal({ threadId: t.id })}
                        style={{ fontSize: 11, padding: "4px 8px" }}
                        title="Forçar etapa"
                      >
                        Forçar etapa
                      </button>
                      <Link to={`/contacts/${t.id}`} className="btn soft" style={{ fontSize: 11, padding: "4px 8px" }}>
                        CRM
                      </Link>
                      <a className="btn soft" href={`/#/chat?thread=${t.id}`} style={{ fontSize: 11, padding: "4px 8px" }}>
                        Chat
                      </a>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      ) : (
        /* Cards (mobile) */
        <div style={{ overflow: "auto", padding: 8 }}>
          {loading && (
            <div className="small" style={{ padding: 12, color: "var(--muted)" }}>
              Carregando…
            </div>
          )}
          {!loading && sorted.length === 0 && (
            <div className="card" style={{ padding: 16, textAlign: "center", color: "var(--muted)" }}>
              <div className="small">Nenhum contato encontrado.</div>
            </div>
          )}
          {sorted.map(t => {
            const effLevel = t._level && t._level !== "desconhecido" ? t._level : (t.lead_level || "frio");
            const effScore = typeof t._score === "number" ? t._score : ((t as any).lead_score as number | undefined);
            return (
              <div key={t.id} className="card" style={{ padding: 12, marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ 
                      fontWeight: 600, 
                      fontSize: 14,
                      marginBottom: 4,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}>
                      {getDisplayName(t)}
                    </div>
                    <code style={{ fontSize: 12, color: "var(--muted)" }}>{t._phone || "—"}</code>
                  </div>
                  <LeadTag level={effLevel} score={effScore} />
                </div>
                
                <div style={{ marginBottom: 8 }}>
                  <select
                    className="select select--sm"
                    value={t.origin || ""}
                    onChange={e => handleChangeOrigin(t, e.target.value)}
                    style={{ width: "100%", fontSize: 13 }}
                  >
                    <option value="">Sem origem</option>
                    <option value="whatsapp_organico">WhatsApp (orgânico)</option>
                    <option value="eduzz_compra">Eduzz compra</option>
                    <option value="eduzz_abandono">Eduzz abandono</option>
                    <option value="the_members">The Members</option>
                    <option value="meta_ads">Campanha (Meta)</option>
                    <option value="qr_code">QR Code</option>
                    <option value="site">Site</option>
                    <option value="indicacao">Indicação</option>
                  </select>
                </div>

                {t._lastText && (
                  <div style={{ 
                    fontSize: 12, 
                    color: "var(--muted)", 
                    marginBottom: 8,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}>
                    {t._lastText}
                  </div>
                )}

                {/* Novos campos: Source, Tags, Funil/Etapa, Produto */}
                {(t as any).source && (
                  <div style={{ 
                    fontSize: 11, 
                    color: "var(--muted)", 
                    marginBottom: 6,
                  }}>
                    Source: <strong style={{ color: "var(--text)" }}>{(t as any).source}</strong>
                  </div>
                )}

                {((t as any).tags && Array.isArray((t as any).tags) && (t as any).tags.length > 0) && (
                  <div style={{ 
                    display: "flex", 
                    flexWrap: "wrap", 
                    gap: 4, 
                    marginBottom: 6 
                  }}>
                    {(t as any).tags.map((tag: string, idx: number) => (
                      <span key={idx} className="chip soft" style={{ fontSize: 10, padding: "2px 6px" }}>
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Funil/Etapa, Produto, Status */}
                <div style={{ 
                  display: "flex", 
                  flexWrap: "wrap", 
                  gap: 6, 
                  marginBottom: 8,
                  fontSize: 11,
                }}>
                  {getFunnelStageDisplay(t) !== "—" && (
                    <span className="chip soft" style={{ fontSize: 10, padding: "4px 8px" }}>
                      📍 {getFunnelStageDisplay(t)}
                    </span>
                  )}
                  {getProductName((t as any).product_id) && (
                    <span className="chip soft" style={{ fontSize: 10, padding: "4px 8px" }}>
                      📦 {getProductName((t as any).product_id)}
                    </span>
                  )}
                  {(() => {
                    const status = getAutomationStatus(t);
                    const statusDisplay = getAutomationStatusDisplay(status);
                    return (
                      <span className="chip" style={{
                        background: statusDisplay.bg,
                        color: statusDisplay.color,
                        fontSize: 10,
                        padding: "4px 8px",
                      }}>
                        {statusDisplay.label}
                      </span>
                    );
                  })()}
                </div>

                <div style={{ 
                  display: "flex", 
                  justifyContent: "space-between", 
                  alignItems: "center",
                  marginBottom: 8,
                  fontSize: 11,
                  color: "var(--muted)",
                }}>
                  <span>Último: {fmtTimeShort(t._lastAt)}</span>
                  {typeof effScore === "number" && <span>Score: {effScore}</span>}
                </div>

                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <button
                    className="btn soft"
                    onClick={() => setShowFlowModal({ threadId: t.id })}
                    style={{ fontSize: 11, padding: "6px 10px", flex: "1 1 calc(50% - 3px)" }}
                  >
                    Ver fluxo
                  </button>
                  <button
                    className="btn soft"
                    onClick={() => setShowForceStageModal({ threadId: t.id })}
                    style={{ fontSize: 11, padding: "6px 10px", flex: "1 1 calc(50% - 3px)" }}
                  >
                    Forçar etapa
                  </button>
                  <Link 
                    to={`/contacts/${t.id}`} 
                    className="btn soft" 
                    style={{ fontSize: 11, padding: "6px 10px", flex: "1 1 calc(50% - 3px)" }}
                  >
                    CRM
                  </Link>
                  <a 
                    className="btn soft" 
                    href={`/#/chat?thread=${t.id}`} 
                    style={{ fontSize: 11, padding: "6px 10px", flex: "1 1 calc(50% - 3px)" }}
                  >
                    Chat
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal Ver Fluxo */}
      {showFlowModal && (() => {
        const thread = rows.find(t => String(t.id) === String(showFlowModal.threadId));
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
              onClick={() => setShowFlowModal(null)}
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
              <div style={{ padding: modalIsMobile ? "12px 14px" : "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: modalIsMobile ? 16 : 18, fontWeight: 600 }}>⚙️ Fluxo de Automação</h3>
                <button onClick={() => setShowFlowModal(null)} style={{ padding: "6px 10px", background: "transparent", border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer", fontSize: 18, color: "var(--text)" }}>✕</button>
              </div>
              <div style={{ flex: 1, overflowY: "auto", padding: modalIsMobile ? "12px 14px" : "16px 20px" }}>
                {thread ? (() => {
                  const funnelId = (thread as any)?.funnel_id || (thread as any)?.metadata?.funnel_id;
                  const stageId = (thread as any)?.stage_id || (thread as any)?.metadata?.stage_id;
                  
                  const funnel = funnelId ? INITIAL_FUNNELS.find(f => String(f.id) === String(funnelId)) : null;
                  const stage = funnel && stageId ? funnel.stages.find(s => String(s.id) === String(stageId)) : null;
                  const automationName = funnel?.name || "Automação ativa";
                  const stageName = stage?.name || "Etapa atual";
                  const audioName = stage?.audio_id ? INITIAL_AUDIOS.find(a => String(a.id) === String(stage.audio_id))?.display_name : null;
                  const actions = automationActions[String(thread.id)] || [];

                  if (!funnelId) {
                    return (
                      <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--muted)" }}>
                        <div style={{ fontSize: 48, marginBottom: 16 }}>⚙️</div>
                        <p style={{ margin: 0, fontSize: 14 }}>Nenhuma automação ativa para este contato.</p>
                        <p style={{ margin: "8px 0 0 0", fontSize: 12, color: "var(--muted)" }}>
                          Thread ID: {thread.id} | Funnel ID: {funnelId || "não definido"}
                        </p>
                      </div>
                    );
                  }

                  return (
                    <div style={{ display: "grid", gap: 16 }}>
                      <div className="card" style={{ padding: modalIsMobile ? 12 : 16 }}>
                        <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Automação Ativa</div>
                        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{automationName}</div>
                        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 8 }}>📍 {stageName}</div>
                        {stage && (
                          <div style={{ padding: 8, background: "var(--bg)", borderRadius: 6, fontSize: 12, color: "var(--text)" }}>
                            <div style={{ marginBottom: 4, fontWeight: 600 }}>Fase: {stage.phase}</div>
                            {audioName && <div style={{ color: "var(--muted)" }}>🎵 Áudio: {audioName}</div>}
                          </div>
                        )}
                      </div>
                      <div>
                        <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Últimas Ações</div>
                        {actions.length > 0 ? (
                          <div style={{ display: "grid", gap: 8 }}>
                            {actions.map((action) => {
                              const audioName = action.audio_id ? INITIAL_AUDIOS.find(a => String(a.id) === String(action.audio_id))?.display_name : null;
                              const actionIcon = action.action_type === "audio_sent" ? "🎵" : action.action_type === "text_sent" ? "💬" : action.action_type === "image_sent" ? "🖼️" : action.action_type === "link_sent" ? "🔗" : action.action_type === "stage_moved" ? "📍" : action.action_type === "tag_added" ? "🏷️" : "⚙️";
                              return (
                                <div key={String(action.id)} className="card" style={{ padding: modalIsMobile ? 10 : 12, display: "flex", alignItems: "flex-start", gap: 10 }}>
                                  <div style={{ width: 6, height: 6, borderRadius: 999, background: action.status === "executed" ? "#10b981" : action.status === "failed" ? "#dc2626" : "#f59e0b", marginTop: 6, flexShrink: 0 }} />
                                  <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                                      <span>{actionIcon}</span>
                                      <span>{audioName || action.action_description}</span>
                                    </div>
                                    <div style={{ fontSize: 11, color: "var(--muted)" }}>
                                      {new Date(action.executed_at).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="card" style={{ padding: 16, textAlign: "center", color: "var(--muted)" }}>
                            <div style={{ fontSize: 13 }}>Nenhuma ação registrada ainda.</div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })() : (
                  <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--muted)" }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
                    <p style={{ margin: 0, fontSize: 14 }}>Contato não encontrado.</p>
                  </div>
                )}
              </div>
            </div>
          </>
        );
      })()}

      {/* Modal Forçar Etapa */}
      {showForceStageModal && (() => {
        const thread = rows.find(t => String(t.id) === String(showForceStageModal.threadId));
        const modalIsMobile = window.innerWidth < 768;
        const availableStages = forceStageFunnel ? stages.filter(s => String(s.funnelId) === forceStageFunnel) : [];

        async function handleForceStage() {
          if (!thread || !forceStageFunnel || !forceStageStage) {
            console.error("[FORÇAR ETAPA] Validação falhou:", { thread: !!thread, forceStageFunnel, forceStageStage });
            return;
          }
          setSavingStage(true);
          try {
            console.log("[FORÇAR ETAPA] Iniciando atualização:", { 
              threadId: thread.id, 
              funnelId: forceStageFunnel, 
              stageId: forceStageStage 
            });
            
            // Atualiza via metadata (onde os campos estão armazenados)
            const currentMeta = (thread as any).metadata || {};
            const updatedMeta = {
              ...currentMeta,
              funnel_id: forceStageFunnel,
              stage_id: forceStageStage,
            };
            
            console.log("[FORÇAR ETAPA] Metadata atual:", currentMeta);
            console.log("[FORÇAR ETAPA] Metadata novo:", updatedMeta);
            
            const updatedThread = await updateThread(thread.id, { 
              metadata: updatedMeta
            });
            
            console.log("[FORÇAR ETAPA] Thread atualizada:", updatedThread);
            
            // Extrai valores atualizados da resposta do backend
            const updatedFunnelId = (updatedThread as any).funnel_id || (updatedThread as any).metadata?.funnel_id || forceStageFunnel;
            const updatedStageId = (updatedThread as any).stage_id || (updatedThread as any).metadata?.stage_id || forceStageStage;
            const updatedMetadata = (updatedThread as any).metadata || updatedMeta;
            
            console.log("[FORÇAR ETAPA] Valores extraídos:", { updatedFunnelId, updatedStageId, updatedMetadata });
            
            // Atualiza o estado local IMEDIATAMENTE
            setRows(prev => {
              const updated = prev.map(r => {
                if (String(r.id) === String(thread.id)) {
                  const newRow = { 
                    ...r, 
                    metadata: updatedMetadata, 
                    funnel_id: updatedFunnelId, 
                    stage_id: updatedStageId 
                  };
                  console.log("[FORÇAR ETAPA] Row atualizado localmente:", { 
                    id: newRow.id, 
                    funnel_id: newRow.funnel_id, 
                    stage_id: newRow.stage_id,
                    display: getFunnelStageDisplay(newRow as Row)
                  });
                  return newRow;
                }
                return r;
              });
              console.log("[FORÇAR ETAPA] Rows após atualização:", updated);
              return updated;
            });
            
            // Recarrega a lista para garantir sincronização completa
            setTimeout(async () => {
              try {
                console.log("[FORÇAR ETAPA] Recarregando threads do backend...");
                const freshThreads = await listThreads();
                console.log("[FORÇAR ETAPA] Threads recarregados:", freshThreads.length);
                
                setRows(prev => {
                  const map = new Map(prev.map(r => [String(r.id), r]));
                  for (const t of freshThreads) {
                    const existing = map.get(String(t.id));
                    if (existing) {
                      const funnelId = (t as any).funnel_id || (t as any).metadata?.funnel_id;
                      const stageId = (t as any).stage_id || (t as any).metadata?.stage_id;
                      const metadata = (t as any).metadata || {};
                      
                      console.log(`[FORÇAR ETAPA] Atualizando thread ${t.id}:`, { funnelId, stageId });
                      
                      // Preserva dados locais mas atualiza do backend
                      map.set(String(t.id), {
                        ...existing,
                        funnel_id: funnelId,
                        stage_id: stageId,
                        metadata: metadata,
                      });
                    }
                  }
                  const result = Array.from(map.values());
                  const updatedRow = result.find(r => String(r.id) === String(thread.id));
                  if (updatedRow) {
                    console.log("[FORÇAR ETAPA] Row final após recarregar:", {
                      id: updatedRow.id,
                      funnel_id: updatedRow.funnel_id,
                      stage_id: updatedRow.stage_id,
                      display: getFunnelStageDisplay(updatedRow as Row)
                    });
                  }
                  return result;
                });
              } catch (e) {
                console.error("[FORÇAR ETAPA] Erro ao recarregar threads:", e);
              }
            }, 300);
            
            // Força re-render da tabela
            console.log("[FORÇAR ETAPA] Fechando modal e forçando re-render");
            
            setShowForceStageModal(null);
            setForceStageFunnel("");
            setForceStageStage("");
            
            // Força atualização visual imediata
            setTimeout(() => {
              console.log("[FORÇAR ETAPA] Forçando atualização visual");
              setRows(prev => [...prev]); // Cria novo array para forçar re-render
            }, 100);
          } catch (error) {
            console.error("[FORÇAR ETAPA] Erro completo:", error);
            alert(`Falha ao atualizar etapa: ${error instanceof Error ? error.message : String(error)}`);
          } finally {
            setSavingStage(false);
          }
        }

        return (
          <>
            <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.5)", zIndex: 10000 }} onClick={() => setShowForceStageModal(null)} />
            <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: modalIsMobile ? "90vw" : 500, maxWidth: "90vw", background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 12, boxShadow: "0 4px 12px rgba(0,0,0,0.15)", zIndex: 10001, display: "flex", flexDirection: "column", maxHeight: "90vh", overflow: "hidden" }}>
              <div style={{ padding: modalIsMobile ? "12px 14px" : "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, fontSize: modalIsMobile ? 16 : 18, fontWeight: 600 }}>📍 Forçar Etapa</h3>
                <button onClick={() => setShowForceStageModal(null)} style={{ padding: "6px 10px", background: "transparent", border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer", fontSize: 18, color: "var(--text)" }}>✕</button>
              </div>
              <div style={{ flex: 1, overflowY: "auto", padding: modalIsMobile ? "12px 14px" : "16px 20px" }}>
                {thread ? (
                  <div style={{ display: "grid", gap: 16 }}>
                    <div>
                      <label style={{ display: "block", marginBottom: 8, fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Contato</label>
                      <div style={{ padding: 12, background: "var(--bg)", borderRadius: 8, fontSize: 14 }}>
                        {getDisplayName(thread)}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                        Thread ID: {thread.id}
                      </div>
                    </div>
                    <div>
                      <label style={{ display: "block", marginBottom: 8, fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Funil</label>
                      <select 
                        className="select" 
                        value={forceStageFunnel} 
                        onChange={e => { 
                          console.log("[FORÇAR ETAPA] Funil selecionado:", e.target.value);
                          setForceStageFunnel(e.target.value); 
                          setForceStageStage(""); 
                        }} 
                        style={{ width: "100%", fontSize: 14 }}
                      >
                        <option value="">Selecione um funil</option>
                        {funnels.map(f => (
                          <option key={f.id} value={String(f.id)}>{f.name}</option>
                        ))}
                      </select>
                      {forceStageFunnel && (
                        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                          Funil selecionado: {forceStageFunnel}
                        </div>
                      )}
                    </div>
                    <div>
                      <label style={{ display: "block", marginBottom: 8, fontSize: 13, fontWeight: 600, color: "var(--text)" }}>Etapa</label>
                      <select 
                        className="select" 
                        value={forceStageStage} 
                        onChange={e => {
                          console.log("[FORÇAR ETAPA] Etapa selecionada:", e.target.value);
                          setForceStageStage(e.target.value);
                        }} 
                        disabled={!forceStageFunnel} 
                        style={{ width: "100%", fontSize: 14, opacity: !forceStageFunnel ? 0.5 : 1 }}
                      >
                        <option value="">Selecione uma etapa</option>
                        {availableStages.map(s => (
                          <option key={s.id} value={String(s.id)}>{s.name}</option>
                        ))}
                      </select>
                      {forceStageStage && (
                        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                          Etapa selecionada: {forceStageStage} ({availableStages.find(s => String(s.id) === forceStageStage)?.name || "N/A"})
                        </div>
                      )}
                      {!forceStageFunnel && (
                        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                          Selecione um funil primeiro
                        </div>
                      )}
                      {forceStageFunnel && availableStages.length === 0 && (
                        <div style={{ fontSize: 11, color: "#dc2626", marginTop: 4 }}>
                          Nenhuma etapa disponível para este funil
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--muted)" }}>
                    <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
                    <p style={{ margin: 0, fontSize: 14 }}>Contato não encontrado.</p>
                    <p style={{ margin: "8px 0 0 0", fontSize: 12, color: "var(--muted)" }}>
                      Buscando thread ID: {showForceStageModal.threadId} | Total de rows: {rows.length}
                    </p>
                  </div>
                )}
              </div>
              <div style={{ padding: modalIsMobile ? "12px 14px" : "16px 20px", borderTop: "1px solid var(--border)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button className="btn soft" onClick={() => { setShowForceStageModal(null); setForceStageFunnel(""); setForceStageStage(""); }} disabled={savingStage} style={{ fontSize: 13, padding: "8px 16px" }}>Cancelar</button>
                <button className="btn" onClick={handleForceStage} disabled={savingStage || !forceStageFunnel || !forceStageStage || !thread} style={{ fontSize: 13, padding: "8px 16px" }}>
                  {savingStage ? "Salvando..." : "Salvar"}
                </button>
              </div>
            </div>
          </>
        );
      })()}
    </div>
  );
}
