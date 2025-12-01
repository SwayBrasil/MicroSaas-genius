// frontend/src/data/funnels.ts
// Estrutura inicial dos funis mapeados
import type { Funnel, FunnelStage } from "../types/funnel";

export const INITIAL_FUNNELS: Funnel[] = [
  {
    id: 1,
    name: "Funil Longo (LIFE)",
    type: "life_funil_longo",
    description: "Do 'quero saber do Life' → diagnóstico → proposta de plano → link de compra → pós-compra ou recuperação.",
    is_active: true,
    stages: [
      {
        id: 1,
        funnel_id: 1,
        name: "Boas-vindas e Qualificação",
        order: 1,
        phase: "frio",
        audio_id: 1, // life_funil_longo_01_boas_vindas_e_qualificacao_inicial
        conditions: [
          {
            type: "user_message_contains",
            value: "quero saber do life",
            operator: "contains",
          },
        ],
      },
      {
        id: 2,
        funnel_id: 1,
        name: "Diagnóstico de Dores",
        order: 2,
        phase: "aquecimento",
        audio_id: 2, // life_funil_longo_02_dor_generica (ou variantes)
        actions: [
          {
            type: "send_text",
            value: "life_funil_longo_prova_social",
            delay_seconds: 0,
          },
        ],
        conditions: [
          {
            type: "user_message_intent",
            value: "dor_emagrecimento|dor_ganho_massa|dor_pochete|dor_autoestima|dor_composicao",
            operator: "contains",
          },
        ],
      },
      {
        id: 3,
        funnel_id: 1,
        name: "Explicação dos Planos",
        order: 3,
        phase: "aquecido",
        audio_id: 3, // life_funil_longo_03_explicacao_planos
        actions: [
          {
            type: "send_text",
            value: "life_funil_longo_planos",
            delay_seconds: 0,
          },
        ],
        conditions: [
          {
            type: "user_message_contains",
            value: "claro|quero saber|planos|preço",
            operator: "contains",
          },
        ],
      },
      {
        id: 4,
        funnel_id: 1,
        name: "Fechamento - Escolha do Plano",
        order: 4,
        phase: "quente",
        text_template: "life_funil_longo_plano_anual|life_funil_longo_plano_mensal",
        conditions: [
          {
            type: "user_choice",
            value: "plano_anual|plano_mensal",
            operator: "equals",
          },
        ],
        actions: [
          {
            type: "send_link",
            value: "https://edzz.la/DO408?a=10554737|https://edzz.la/GQRLF?a=10554737",
            delay_seconds: 0,
          },
        ],
      },
      {
        id: 5,
        funnel_id: 1,
        name: "Recuperação Pós Não Compra",
        order: 5,
        phase: "quente",
        audio_id: 4, // life_funil_longo_04_recuperacao_pos_nao_compra
        conditions: [
          {
            type: "external_webhook",
            value: "eduzz_no_purchase",
            operator: "equals",
          },
        ],
      },
    ],
  },
  {
    id: 2,
    name: "Mini Funil Black Friday",
    type: "life_mini_funil_bf",
    description: "Oferta específica de BF + follow-ups.",
    is_active: true,
    stages: [
      {
        id: 6,
        funnel_id: 2,
        name: "Oferta Black Friday",
        order: 1,
        phase: "aquecido",
        audio_id: 5, // life_mini_funil_bf_01_oferta_black_friday
        conditions: [
          {
            type: "user_message_contains",
            value: "",
            operator: "equals", // Dispara automaticamente para leads aquecidas
          },
        ],
      },
      {
        id: 7,
        funnel_id: 2,
        name: "Follow-up Sem Resposta",
        order: 2,
        phase: "quente",
        audio_id: 6, // life_mini_funil_bf_02_followup_sem_resposta
        conditions: [
          {
            type: "time_elapsed",
            value: "3600", // 1 hora em segundos
            operator: "greater_than",
          },
        ],
      },
    ],
  },
  {
    id: 3,
    name: "Funil de Recuperação Pós-Plataforma (50%)",
    type: "life_recuperacao_50",
    description: "Lead aqueceu na plataforma, não comprou → recebe oferta com 50% + sequência de follow-up.",
    is_active: true,
    stages: [
      {
        id: 8,
        funnel_id: 3,
        name: "Texto Oferta 50%",
        order: 1,
        phase: "aquecido",
        text_template: "life_recuperacao_50_01_texto_oferta_50",
        conditions: [
          {
            type: "external_webhook",
            value: "platform_no_purchase",
            operator: "equals",
          },
        ],
      },
      {
        id: 9,
        funnel_id: 3,
        name: "Follow-up Áudio 1",
        order: 2,
        phase: "quente",
        audio_id: 7, // life_recuperacao_50_02_audio_followup
        conditions: [
          {
            type: "time_elapsed",
            value: "1800", // 30 minutos
            operator: "greater_than",
          },
        ],
      },
      {
        id: 10,
        funnel_id: 3,
        name: "Último Chamado",
        order: 3,
        phase: "quente",
        audio_id: 8, // life_recuperacao_50_03_audio_ultimo_chamado
        conditions: [
          {
            type: "time_elapsed",
            value: "3600", // 1 hora
            operator: "greater_than",
          },
        ],
      },
    ],
  },
];

