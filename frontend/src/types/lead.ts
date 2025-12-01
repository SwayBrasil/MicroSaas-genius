// frontend/src/types/lead.ts
export type LeadLevel = "frio" | "morno" | "quente" | "desconhecido";

export type UIMessage = {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  is_human?: boolean;
};

// Tipo expandido para Lead/Contato com todos os campos necessários
export type LeadData = {
  id: number | string;
  funnel_id?: number | string | null;  // ID do funil
  stage_id?: number | string | null;  // ID da etapa no funil
  product_id?: number | string | null;  // ID do produto/plano principal
  source?: string | null;  // Origem: "Eduzz compra", "Eduzz abandono", "The Members", "WhatsApp orgânico", etc.
  tags?: string[];  // Lista de tags (strings simples)
  temperature?: LeadLevel;  // Alias para lead_level
  score?: number | null;  // Alias para lead_score
};

