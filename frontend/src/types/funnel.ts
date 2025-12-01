// frontend/src/types/funnel.ts

/** Tipos de funil */
export type FunnelType = "life_funil_longo" | "life_mini_funil_bf" | "life_recuperacao_50" | "custom";

/** Fases macro do lead */
export type LeadPhase = "frio" | "aquecimento" | "aquecido" | "quente" | "assinante" | "assinante_fatura_pendente";

/** Áudio do sistema */
export type Audio = {
  id: number | string;
  filename_whatsapp: string; // Ex: "00000011-AUDIO-2025-11-24-22-40-30.opus"
  code_name: string; // Ex: "life_funil_longo_01_boas_vindas_e_qualificacao_inicial"
  display_name: string; // Nome amigável para exibição
  description?: string; // Descrição do áudio
  funnel_type: FunnelType; // Qual funil pertence
  stage_order?: number; // Ordem no funil
  context?: string; // Contexto de uso
  file_url?: string; // URL do arquivo de áudio
  duration_seconds?: number; // Duração em segundos
  created_at?: string;
  updated_at?: string;
};

/** Etapa de um funil */
export type FunnelStage = {
  id: number | string;
  funnel_id: number | string;
  name: string; // Ex: "Boas-vindas", "Apresentação", "Oferta", "Follow-up 1"
  order: number; // Ordem da etapa no funil
  phase: LeadPhase; // Fase macro do lead
  audio_id?: number | string | null; // Áudio a ser enviado nesta etapa
  text_template?: string; // Template de texto (se houver)
  conditions?: StageCondition[]; // Condições para avançar
  actions?: StageAction[]; // Ações a executar
  created_at?: string;
  updated_at?: string;
};

/** Condição para avançar de etapa */
export type StageCondition = {
  type: "user_message_contains" | "user_message_intent" | "time_elapsed" | "external_webhook" | "user_choice";
  value: string; // Valor da condição
  operator?: "equals" | "contains" | "greater_than" | "less_than";
};

/** Ação a executar na etapa */
export type StageAction = {
  type: "send_audio" | "send_text" | "send_image" | "send_link" | "wait" | "move_to_stage" | "tag_lead";
  value: string; // Valor da ação (ID do áudio, texto, etc)
  delay_seconds?: number; // Delay antes de executar
};

/** Funil completo */
export type Funnel = {
  id: number | string;
  name: string; // Ex: "Funil Longo (LIFE)", "Mini Funil Black Friday"
  type: FunnelType;
  description?: string;
  stages: FunnelStage[]; // Etapas do funil
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
};

/** Ação de automação executada */
export type AutomationAction = {
  id: number | string;
  thread_id: number | string;
  funnel_id?: number | string;
  stage_id?: number | string;
  audio_id?: number | string;
  action_type: "audio_sent" | "text_sent" | "image_sent" | "link_sent" | "stage_moved" | "tag_added";
  action_description: string; // Ex: "Áudio 1 enviado", "Follow-up agendado para 14:35"
  executed_at: string;
  status: "pending" | "executed" | "failed";
};

