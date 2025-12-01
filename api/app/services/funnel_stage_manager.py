# api/app/services/funnel_stage_manager.py
"""Gerencia atualização automática de etapas do funil baseado em eventos"""
from typing import Dict, Optional, Any
import json
from datetime import datetime


# Mapeamento de eventos para etapas do funil
EVENT_TO_STAGE = {
    # Funil Longo (funnel_id = 1)
    "USER_SENT_FIRST_MESSAGE": {
        "funnel_id": "1",
        "stage_id": "1",  # Boas-vindas e Qualificação
        "lead_level": "frio",
        "phase": "frio"
    },
    "USER_SENT_DOR": {
        "funnel_id": "1",
        "stage_id": "2",  # Diagnóstico de Dores
        "lead_level": "morno",
        "phase": "aquecimento"
    },
    "IA_SENT_EXPLICACAO_PLANOS": {
        "funnel_id": "1",
        "stage_id": "3",  # Explicação dos Planos
        "lead_level": "morno",
        "phase": "aquecido"
    },
    "USER_ESCOLHEU_PLANO": {
        "funnel_id": "1",
        "stage_id": "4",  # Fechamento - Escolha do Plano
        "lead_level": "quente",
        "phase": "quente"
    },
    "EDUZZ_WEBHOOK_APROVADA": {
        "funnel_id": "1",
        "stage_id": "5",  # Pós-Compra
        "lead_level": "quente",
        "phase": "assinante"
    },
    "TEMPO_LIMITE_PASSOU": {
        "funnel_id": "1",
        "stage_id": "6",  # Recuperação Pós Não Compra
        "lead_level": "quente",
        "phase": "recuperacao"
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
    
    # Detecta se mencionou dor/objetivo
    dor_keywords = [
        "dor", "problema", "incomoda", "quero emagrecer", "quero perder peso",
        "barriga", "flacidez", "celulite", "autoestima", "vergonha",
        "não gosto", "me incomoda", "me derruba", "travamento"
    ]
    
    if any(keyword in message_lower for keyword in dor_keywords):
        current_stage = thread_meta.get("stage_id", "1")
        # Só atualiza se ainda não está na etapa de dor
        if current_stage == "1":
            return "USER_SENT_DOR"
    
    # Detecta escolha de plano
    plano_keywords = ["mensal", "anual", "plano mensal", "plano anual", "quero o mensal", "quero o anual"]
    if any(keyword in message_lower for keyword in plano_keywords):
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

