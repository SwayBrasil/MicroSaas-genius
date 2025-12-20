# api/app/services/state_machine.py
"""
Máquina de Estados Completa do Funil LIFE
Define todos os estados, transições e regras de negócio
"""
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass


# ==================== ENUMS DE ESTADO ====================

class LeadStage(str, Enum):
    """Estágio macro do lead"""
    FRIO = "frio"
    AQUECIMENTO = "aquecimento"
    AQUECIDO = "aquecido"
    QUENTE = "quente"
    ASSINANTE_PENDENTE = "assinante_pendente"
    ASSINANTE_ATIVO = "assinante_ativo"


class CurrentFlow(str, Enum):
    """Fluxo ativo"""
    FUNIL_LONGO = "FUNIL_LONGO"
    BF_MINI = "BF_MINI"
    NONE = "NONE"


class PurchaseStatus(str, Enum):
    """Status da compra"""
    NONE = "NONE"
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PainPoint(str, Enum):
    """Dor identificada"""
    NONE = "NONE"
    EMAGRECIMENTO_SECAR = "EMAGRECIMENTO_SECAR"
    GANHO_MASSA_BUMBUM = "GANHO_MASSA_BUMBUM"
    AUTOESTIMA_MOTIVACAO = "AUTOESTIMA_MOTIVACAO"
    POCHEte_FLACIDEZ_CELULITE = "POCHEte_FLACIDEZ_CELULITE"
    ALIMENTACAO_RESULTADO_NAO_VEM = "ALIMENTACAO_RESULTADO_NAO_VEM"


class PlanInterest(str, Enum):
    """Interesse em plano"""
    UNKNOWN = "UNKNOWN"
    MENSAL = "MENSAL"
    ANUAL = "ANUAL"


# ==================== ESTADOS DO FUNIL LONGO ====================

class FunilLongoStep(str, Enum):
    """Etapas do Funil Longo"""
    L1_ABERTURA = "L1_ABERTURA"
    L2_COLETA_DOR = "L2_COLETA_DOR"
    L3_DECISAO_OBJECAO = "L3_DECISAO_OBJECAO"
    L4_PERGUNTA_PLANOS = "L4_PERGUNTA_PLANOS"
    L5_PLANOS = "L5_PLANOS"
    L6_ESCOLHA_PLANO = "L6_ESCOLHA_PLANO"
    L7_AGUARDANDO_COMPRA = "L7_AGUARDANDO_COMPRA"
    L8_COMPRA_PENDENTE = "L8_COMPRA_PENDENTE"
    L9_POS_COMPRA = "L9_POS_COMPRA"


# ==================== ESTADOS DO MINI FUNIL BF ====================

class BFMiniStep(str, Enum):
    """Etapas do Mini Funil Black Friday"""
    BF1_OFERTA = "BF1_OFERTA"
    BF2_AGUARDANDO = "BF2_AGUARDANDO"
    BF3_AGUARDANDO_COMPRA = "BF3_AGUARDANDO_COMPRA"
    BF_FOLLOW_1 = "BF_FOLLOW_1"
    BF_FOLLOW_2 = "BF_FOLLOW_2"
    BF_FOLLOW_3 = "BF_FOLLOW_3"


# ==================== TIPOS DE EVENTOS ====================

class EventType(str, Enum):
    """Tipos de eventos que disparam transições"""
    # Mensagens do lead
    FIRST_CONTACT = "FIRST_CONTACT"
    DESCRIBES_PAIN = "DESCRIBES_PAIN"
    ASKS_PRICE = "ASKS_PRICE"
    OBJECTION = "OBJECTION"
    INTEREST = "INTEREST"
    ASKS_PLANS = "ASKS_PLANS"
    CONFIRMS_PLANS = "CONFIRMS_PLANS"
    CHOOSES_MENSAL = "CHOOSES_MENSAL"
    CHOOSES_ANUAL = "CHOOSES_ANUAL"
    CONFIRMS_PURCHASE = "CONFIRMS_PURCHASE"
    PURCHASE_ERROR = "PURCHASE_ERROR"
    ASKS_TECHNICAL = "ASKS_TECHNICAL"
    CONFUSION = "CONFUSION"
    NO_RESPONSE = "NO_RESPONSE"
    
    # Webhooks
    WEBHOOK_PAID = "WEBHOOK_PAID"
    WEBHOOK_PENDING = "WEBHOOK_PENDING"
    WEBHOOK_FAILED = "WEBHOOK_FAILED"
    WEBHOOK_REFUNDED = "WEBHOOK_REFUNDED"
    
    # Timers/Follow-ups
    TIMER_FOLLOWUP = "TIMER_FOLLOWUP"
    TIMER_RESCUE = "TIMER_RESCUE"
    
    # Black Friday
    BF_TRIGGER = "BF_TRIGGER"
    BF_CONFIRMS = "BF_CONFIRMS"
    BF_OBJECTION = "BF_OBJECTION"
    
    # Casos especiais
    RETURNS_AFTER_DAYS = "RETURNS_AFTER_DAYS"
    EMPTY_MESSAGE = "EMPTY_MESSAGE"


# ==================== DEFINIÇÃO DE TRANSIÇÕES ====================

@dataclass
class Transition:
    """Define uma transição de estado"""
    from_step: str
    event: EventType
    to_step: str
    action: str  # Nome da função que executa a ação
    conditions: Optional[List[str]] = None  # Condições adicionais (ex: "purchase_status != PAID")


# Tabela de transições do Funil Longo
FUNIL_LONGO_TRANSITIONS: List[Transition] = [
    # L1_ABERTURA
    Transition(
        from_step=FunilLongoStep.L1_ABERTURA,
        event=EventType.DESCRIBES_PAIN,
        to_step=FunilLongoStep.L2_COLETA_DOR,
        action="handle_l2_coleta_dor"
    ),
    Transition(
        from_step=FunilLongoStep.L1_ABERTURA,
        event=EventType.ASKS_PRICE,
        to_step=FunilLongoStep.L4_PERGUNTA_PLANOS,
        action="handle_l4_pergunta_planos_with_context"
    ),
    Transition(
        from_step=FunilLongoStep.L1_ABERTURA,
        event=EventType.EMPTY_MESSAGE,
        to_step=FunilLongoStep.L1_ABERTURA,
        action="handle_empty_message"
    ),
    
    # L2_COLETA_DOR
    Transition(
        from_step=FunilLongoStep.L2_COLETA_DOR,
        event=EventType.OBJECTION,
        to_step=FunilLongoStep.L3_DECISAO_OBJECAO,
        action="handle_l3_objeção"
    ),
    Transition(
        from_step=FunilLongoStep.L2_COLETA_DOR,
        event=EventType.INTEREST,
        to_step=FunilLongoStep.L4_PERGUNTA_PLANOS,
        action="handle_l3_interesse"
    ),
    Transition(
        from_step=FunilLongoStep.L2_COLETA_DOR,
        event=EventType.ASKS_TECHNICAL,
        to_step=FunilLongoStep.L3_DECISAO_OBJECAO,
        action="handle_l3_duvida_tecnica"
    ),
    
    # L3_DECISAO_OBJECAO
    Transition(
        from_step=FunilLongoStep.L3_DECISAO_OBJECAO,
        event=EventType.INTEREST,
        to_step=FunilLongoStep.L4_PERGUNTA_PLANOS,
        action="handle_l4_pergunta_planos"
    ),
    
    # L4_PERGUNTA_PLANOS
    Transition(
        from_step=FunilLongoStep.L4_PERGUNTA_PLANOS,
        event=EventType.CONFIRMS_PLANS,
        to_step=FunilLongoStep.L5_PLANOS,
        action="handle_l5_planos"
    ),
    Transition(
        from_step=FunilLongoStep.L4_PERGUNTA_PLANOS,
        event=EventType.ASKS_PRICE,
        to_step=FunilLongoStep.L5_PLANOS,
        action="handle_l5_planos"
    ),
    
    # L5_PLANOS
    Transition(
        from_step=FunilLongoStep.L5_PLANOS,
        event=EventType.CHOOSES_MENSAL,
        to_step=FunilLongoStep.L6_ESCOLHA_PLANO,
        action="handle_l6_mensal"
    ),
    Transition(
        from_step=FunilLongoStep.L5_PLANOS,
        event=EventType.CHOOSES_ANUAL,
        to_step=FunilLongoStep.L6_ESCOLHA_PLANO,
        action="handle_l6_anual"
    ),
    Transition(
        from_step=FunilLongoStep.L5_PLANOS,
        event=EventType.ASKS_TECHNICAL,
        to_step=FunilLongoStep.L5_PLANOS,
        action="handle_l5_duvida"
    ),
    
    # L6_ESCOLHA_PLANO
    Transition(
        from_step=FunilLongoStep.L6_ESCOLHA_PLANO,
        event=EventType.CONFIRMS_PURCHASE,
        to_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
        action="handle_l7_aguardando"
    ),
    
    # L7_AGUARDANDO_COMPRA
    Transition(
        from_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
        event=EventType.WEBHOOK_PAID,
        to_step=FunilLongoStep.L9_POS_COMPRA,
        action="handle_l9_pos_compra"
    ),
    Transition(
        from_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
        event=EventType.WEBHOOK_PENDING,
        to_step=FunilLongoStep.L8_COMPRA_PENDENTE,
        action="handle_l8_pendente"
    ),
    Transition(
        from_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
        event=EventType.PURCHASE_ERROR,
        to_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
        action="handle_l7_erro"
    ),
    Transition(
        from_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
        event=EventType.TIMER_RESCUE,
        to_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
        action="handle_l7_resgate"
    ),
    
    # L8_COMPRA_PENDENTE
    Transition(
        from_step=FunilLongoStep.L8_COMPRA_PENDENTE,
        event=EventType.WEBHOOK_PAID,
        to_step=FunilLongoStep.L9_POS_COMPRA,
        action="handle_l9_pos_compra"
    ),
    Transition(
        from_step=FunilLongoStep.L8_COMPRA_PENDENTE,
        event=EventType.CONFIRMS_PURCHASE,
        to_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
        action="handle_l7_aguardando"
    ),
]


# Tabela de transições do Mini Funil BF
BF_MINI_TRANSITIONS: List[Transition] = [
    # BF1_OFERTA
    Transition(
        from_step=BFMiniStep.BF1_OFERTA,
        event=EventType.BF_CONFIRMS,
        to_step=BFMiniStep.BF3_AGUARDANDO_COMPRA,
        action="handle_bf3_aguardando"
    ),
    Transition(
        from_step=BFMiniStep.BF1_OFERTA,
        event=EventType.BF_OBJECTION,
        to_step=BFMiniStep.BF2_AGUARDANDO,
        action="handle_bf2_objeção"
    ),
    Transition(
        from_step=BFMiniStep.BF1_OFERTA,
        event=EventType.NO_RESPONSE,
        to_step=BFMiniStep.BF_FOLLOW_1,
        action="handle_bf_follow_1"
    ),
    
    # BF2_AGUARDANDO
    Transition(
        from_step=BFMiniStep.BF2_AGUARDANDO,
        event=EventType.BF_CONFIRMS,
        to_step=BFMiniStep.BF3_AGUARDANDO_COMPRA,
        action="handle_bf3_aguardando"
    ),
    
    # BF3_AGUARDANDO_COMPRA
    Transition(
        from_step=BFMiniStep.BF3_AGUARDANDO_COMPRA,
        event=EventType.WEBHOOK_PAID,
        to_step=FunilLongoStep.L9_POS_COMPRA,
        action="handle_l9_pos_compra"
    ),
    
    # Follow-ups BF
    Transition(
        from_step=BFMiniStep.BF_FOLLOW_1,
        event=EventType.BF_CONFIRMS,
        to_step=BFMiniStep.BF3_AGUARDANDO_COMPRA,
        action="handle_bf3_aguardando"
    ),
    Transition(
        from_step=BFMiniStep.BF_FOLLOW_1,
        event=EventType.NO_RESPONSE,
        to_step=BFMiniStep.BF_FOLLOW_2,
        action="handle_bf_follow_2"
    ),
    Transition(
        from_step=BFMiniStep.BF_FOLLOW_2,
        event=EventType.NO_RESPONSE,
        to_step=BFMiniStep.BF_FOLLOW_3,
        action="handle_bf_follow_3"
    ),
]


# ==================== REGRAS GLOBAIS ====================

class StateMachineRules:
    """Regras globais da máquina de estados"""
    
    # Tempos de follow-up (em minutos)
    FOLLOWUP_DELAY_AFTER_PLANOS = 60  # 1 hora após enviar planos
    FOLLOWUP_DELAY_AFTER_LINK = 120  # 2 horas após enviar link
    RESCUE_DELAY = 180  # 3 horas após link sem resposta
    BF_FOLLOWUP_DELAY_1 = 30  # 30 minutos
    BF_FOLLOWUP_DELAY_2 = 60  # 1 hora
    BF_FOLLOWUP_DELAY_3 = 120  # 2 horas
    
    # Máximos
    MAX_FOLLOWUP_ATTEMPTS = 3
    MAX_DUVIDA_CYCLES = 2  # Máximo de ciclos de dúvida em L6
    
    # Anti-spam
    MIN_TIME_BETWEEN_FOLLOWUPS = 60  # 1 hora mínimo entre follow-ups
    MIN_TIME_SINCE_LAST_INBOUND = 30  # 30 minutos desde última mensagem do lead
    
    @staticmethod
    def can_send_followup(
        last_inbound_at: Optional[float],
        last_followup_at: Optional[float],
        purchase_status: PurchaseStatus,
        followup_count: int
    ) -> bool:
        """Verifica se pode enviar follow-up"""
        import time
        now = time.time()
        
        # Não envia se já pagou
        if purchase_status == PurchaseStatus.PAID:
            return False
        
        # Não envia se excedeu máximo
        if followup_count >= StateMachineRules.MAX_FOLLOWUP_ATTEMPTS:
            return False
        
        # Não envia se lead respondeu recentemente
        if last_inbound_at:
            time_since_inbound = (now - last_inbound_at) / 60  # minutos
            if time_since_inbound < StateMachineRules.MIN_TIME_SINCE_LAST_INBOUND:
                return False
        
        # Não envia se já enviou follow-up recentemente
        if last_followup_at:
            time_since_followup = (now - last_followup_at) / 60  # minutos
            if time_since_followup < StateMachineRules.MIN_TIME_BETWEEN_FOLLOWUPS:
                return False
        
        return True


# ==================== TEMPLATES DE MENSAGENS ====================

class MessageTemplates:
    """Templates de mensagens fixas"""
    
    # L1 - Abertura
    L1_PERGUNTA_DOR = "Me conta rapidinho: hoje teu foco é mais secar, ganhar massa, ou os dois?"
    
    # L2 - Após provas sociais
    L2_CTA = "Me conta aqui gata, o que tá faltando pra tu dar esse passo?"
    
    # L3 - Objeção
    L3_QUEBRA_OBJECAO = "Posso te explicar rapidinho os planos pra você ver o que encaixa melhor?"
    
    # L3 - Interesse
    L3_INTERESSE = "Perfeita. Posso te explicar melhor os planos?"
    
    # L4 - Pergunta planos
    L4_PERGUNTA = "Quer que eu te explique os planos agora?"
    
    # L5 - Após planos
    L5_PERGUNTA_FINAL = "Agora me fala, gata: qual plano faz mais sentido pra você?"
    
    # L6 - Dúvida
    L6_PERGUNTA_NOVAMENTE = "Qual plano faz mais sentido pra você: mensal ou anual?"
    
    # L6 - Vou pensar
    L6_DESTRAVAMENTO = "É mais por preço, tempo, ou insegurança de não conseguir seguir?"
    
    # L7 - Confirma compra
    L7_CONFIRMA = "Perfeito, já já confirma aqui; se demorar me manda print do pagamento"
    
    # L7 - Erro
    L7_ERRO = "Vou te ajudar a resolver. Pode tentar outro cartão ou prefere PIX?"
    
    # L8 - Pendente
    L8_PERGUNTA = "Vi que ficou pendente. Quer que eu te ajude a concluir agora?"
    
    # BF
    BF_PERGUNTA = "Quer que eu te mande o link com a condição de hoje?"
    
    # Casos especiais
    EMPTY_MESSAGE_RESPONSE = "Não entendi certinho. Teu objetivo hoje é mais secar, ganhar massa, ou os dois?"
    
    # Links
    LINK_MENSAL = "https://edzz.la/GQRLF?a=10554737"
    LINK_ANUAL = "https://edzz.la/DO408?a=10554737"
    
    # Template de planos (usar do funnel_packages.py)
    # Template pós-compra (usar do post_purchase.py)

