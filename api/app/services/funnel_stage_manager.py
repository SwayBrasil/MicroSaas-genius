# api/app/services/funnel_stage_manager.py
"""Gerencia atualização automática de etapas do funil baseado em eventos"""
from typing import Dict, Optional, Any
import json
from datetime import datetime


# Mapeamento de eventos para etapas do funil
EVENT_TO_STAGE = {
    # ========== FUNIL LONGO (funnel_id = 1) ==========
    
    # FASE 1 - Lead Frio
    "USER_SENT_FIRST_MESSAGE": {
        "funnel_id": "1",
        "stage_id": "1",
        "lead_level": "frio",
        "phase": "frio",
        "name": "Lead Frio"
    },
    "IA_SENT_AUDIO1_BOAS_VINDAS": {
        "funnel_id": "1",
        "stage_id": "1",
        "lead_level": "frio",
        "phase": "frio",
        "name": "Lead Frio - Áudio 1 enviado"
    },
    
    # FASE 2 - Aquecimento (Descoberta da Dor)
    "USER_SENT_DOR": {
        "funnel_id": "1",
        "stage_id": "2",
        "lead_level": "morno",
        "phase": "aquecimento",
        "name": "Aquecimento - Dor detectada"
    },
    "IA_SENT_AUDIO2_DOR": {
        "funnel_id": "1",
        "stage_id": "2",
        "lead_level": "morno",
        "phase": "aquecimento",
        "name": "Aquecimento - Áudio 2 enviado"
    },
    "IA_SENT_PROVAS_SOCIAIS": {
        "funnel_id": "1",
        "stage_id": "2",
        "lead_level": "morno",
        "phase": "aquecimento",
        "name": "Aquecimento - Provas sociais enviadas"
    },
    
    # FASE 3 - Aquecido (Objeção ou Interesse)
    "USER_SENT_OBJECAO": {
        "funnel_id": "1",
        "stage_id": "3",
        "lead_level": "morno",
        "phase": "aquecido",
        "name": "Aquecido - Objeção detectada"
    },
    "USER_SENT_INTERESSE": {
        "funnel_id": "1",
        "stage_id": "3",
        "lead_level": "morno",
        "phase": "aquecido",
        "name": "Aquecido - Interesse detectado"
    },
    "IA_QUEBROU_OBJECAO": {
        "funnel_id": "1",
        "stage_id": "3",
        "lead_level": "morno",
        "phase": "aquecido",
        "name": "Aquecido - Objeção quebrada"
    },
    
    # FASE 4 - Quente (Apresentação dos Planos)
    "USER_PEDIU_PLANOS": {
        "funnel_id": "1",
        "stage_id": "4",
        "lead_level": "quente",
        "phase": "quente",
        "name": "Quente - Planos solicitados"
    },
    "IA_SENT_EXPLICACAO_PLANOS": {
        "funnel_id": "1",
        "stage_id": "4",
        "lead_level": "quente",
        "phase": "quente",
        "name": "Quente - Planos apresentados"
    },
    
    # FASE 5 - Fechamento
    "USER_ESCOLHEU_PLANO": {
        "funnel_id": "1",
        "stage_id": "5",
        "lead_level": "quente",
        "phase": "quente",
        "name": "Fechamento - Plano escolhido"
    },
    "IA_ENVIOU_LINK_CHECKOUT": {
        "funnel_id": "1",
        "stage_id": "5",
        "lead_level": "quente",
        "phase": "quente",
        "name": "Fechamento - Link enviado"
    },
    
    # FASE 6 - Pós-Venda
    "EDUZZ_WEBHOOK_APROVADA": {
        "funnel_id": "1",
        "stage_id": "6",
        "lead_level": "quente",
        "phase": "assinante",
        "name": "Pós-Venda - Compra aprovada"
    },
    "IA_ENVIOU_ACESSOS": {
        "funnel_id": "1",
        "stage_id": "6",
        "lead_level": "quente",
        "phase": "assinante",
        "name": "Pós-Venda - Acessos enviados"
    },
    
    # FASE 7 - Carrinho Abandonado
    "CARRINHO_ABANDONADO": {
        "funnel_id": "1",
        "stage_id": "7",
        "lead_level": "quente",
        "phase": "quente_recebeu_oferta",
        "name": "Carrinho Abandonado"
    },
    "IA_ENVIOU_RECUPERACAO": {
        "funnel_id": "1",
        "stage_id": "7",
        "lead_level": "quente",
        "phase": "quente_recebeu_oferta",
        "name": "Recuperação enviada"
    },
    
    # ========== MINI FUNIL BF (funnel_id = 2) ==========
    "BF_IMAGEM_ENVIADA": {
        "funnel_id": "2",
        "stage_id": "1",
        "lead_level": "frio",
        "phase": "frio",
        "name": "BF - Imagem enviada"
    },
    "BF_AUDIO_OFERTA_ENVIADO": {
        "funnel_id": "2",
        "stage_id": "2",
        "lead_level": "morno",
        "phase": "aquecimento",
        "name": "BF - Áudio de oferta enviado"
    },
    "BF_FOLLOWUP_1_ENVIADO": {
        "funnel_id": "2",
        "stage_id": "3",
        "lead_level": "morno",
        "phase": "aquecido",
        "name": "BF - Follow-up 1 enviado"
    },
    "BF_FOLLOWUP_2_ENVIADO": {
        "funnel_id": "2",
        "stage_id": "4",
        "lead_level": "morno",
        "phase": "aquecido",
        "name": "BF - Follow-up 2 enviado"
    },
    "BF_FOLLOWUP_3_ENVIADO": {
        "funnel_id": "2",
        "stage_id": "5",
        "lead_level": "morno",
        "phase": "aquecido",
        "name": "BF - Follow-up 3 enviado"
    },
}


def update_stage_from_event(
    thread_meta: Dict[str, Any],
    event: str,
    additional_data: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Atualiza a etapa do funil baseado em um evento.
    
    Args:
        thread_meta: Metadata atual da thread
        event: Nome do evento (ex: "USER_SENT_FIRST_MESSAGE")
        additional_data: Dados adicionais do evento
    
    Returns:
        Metadata atualizado
    """
    if event not in EVENT_TO_STAGE:
        return thread_meta
    
    stage_data = EVENT_TO_STAGE[event]
    
    # Atualiza metadata
    updated_meta = thread_meta.copy() if thread_meta else {}
    
    # Atualiza etapa do funil
    updated_meta["funnel_id"] = stage_data["funnel_id"]
    updated_meta["stage_id"] = stage_data["stage_id"]
    updated_meta["lead_level"] = stage_data["lead_level"]
    updated_meta["phase"] = stage_data["phase"]
    updated_meta["last_stage_update"] = datetime.now().isoformat()
    updated_meta["last_event"] = event
    
    # Mescla dados adicionais se houver
    if additional_data:
        updated_meta.update(additional_data)
    
    return updated_meta


def detect_stage_from_message(
    message: str,
    thread_meta: Optional[Dict[str, Any]] = None,
    is_first_message: bool = False
) -> Optional[str]:
    """
    Detecta qual evento deve ser disparado baseado na mensagem.
    
    Returns:
        Nome do evento ou None
    """
    message_lower = message.lower().strip()
    
    # Primeira mensagem
    if is_first_message or not thread_meta or not thread_meta.get("stage_id"):
        return "USER_SENT_FIRST_MESSAGE"
    
    # Detecta se mencionou dor/objetivo (FASE 2)
    dor_keywords = [
        "perder gordura", "pochete", "flacidez", "celulite",
        "ganhar massa", "bunda", "coxas", "falta de foco",
        "dieta", "alimentação", "constância",
        "dor", "problema", "incomoda", "quero emagrecer", "quero perder peso",
        "barriga", "autoestima", "vergonha",
        "não gosto", "me incomoda", "me derruba", "travamento", "objetivo"
    ]
    
    if any(keyword in message_lower for keyword in dor_keywords):
        current_stage = thread_meta.get("stage_id", "1")
        # Só atualiza se ainda não está na etapa de dor
        if current_stage == "1":
            return "USER_SENT_DOR"
    
    # Detecta objeções (FASE 3)
    objection_keywords = [
        "tô sem tempo", "tô sem dinheiro", "não sei se consigo",
        "não sei se funciona pra mim", "sem tempo", "sem dinheiro"
    ]
    if any(keyword in message_lower for keyword in objection_keywords):
        return "USER_SENT_OBJECAO"
    
    # Detecta interesse alto (FASE 3)
    interest_keywords = [
        "sim", "pode ser", "legal", "ok", "entendi", "faz sentido",
        "gostei", "quero saber", "me explica", "conta pra mim",
        "pode", "quero", "me mostra"
    ]
    if any(keyword in message_lower for keyword in interest_keywords):
        current_stage = thread_meta.get("stage_id", "2")
        if current_stage == "2":  # Se está na fase 2, avança para fase 3
            return "USER_SENT_INTERESSE"
    
    # Detecta pedido de planos (FASE 4)
    planos_keywords = [
        "preço", "preços", "quanto custa", "valores", "planos",
        "quero ver os precos", "me passa os preços", "quais os valores",
        "quero saber dos planos", "me mostra os planos", "investimento",
        "como funciona o pagamento", "quais são os planos"
    ]
    if any(keyword in message_lower for keyword in planos_keywords):
        return "USER_PEDIU_PLANOS"
    
    # Detecta escolha de plano (FASE 5)
    plano_anual_keywords = ["anual", "plano anual", "quero o anual", "vou querer o anual"]
    plano_mensal_keywords = ["mensal", "plano mensal", "quero o mensal", "vou querer o mensal"]
    
    if any(keyword in message_lower for keyword in plano_anual_keywords):
        return "USER_ESCOLHEU_PLANO"
    if any(keyword in message_lower for keyword in plano_mensal_keywords):
        return "USER_ESCOLHEU_PLANO"
    
    return None


def get_current_stage_info(thread_meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Retorna informações sobre a etapa atual do funil.
    
    Returns:
        Dict com funnel_id, stage_id, lead_level, phase
    """
    if not thread_meta:
        return {
            "funnel_id": None,
            "stage_id": None,
            "lead_level": "frio",
            "phase": "frio"
        }
    
    return {
        "funnel_id": thread_meta.get("funnel_id"),
        "stage_id": thread_meta.get("stage_id"),
        "lead_level": thread_meta.get("lead_level", "frio"),
        "phase": thread_meta.get("phase", "frio")
    }

