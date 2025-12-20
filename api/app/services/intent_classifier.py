# api/app/services/intent_classifier.py
"""
Classificador de Intenções - Detecta ASK_PLANS vs CHOOSE_PLAN vs OTHER
Determinístico, sem LLM
"""
import re
from typing import Literal


def detect_plans_intent(
    text: str,
    current_stage: str = None,
    last_bot_message: str = None
) -> Literal["ASK_PLANS", "CHOOSE_PLAN", "OTHER"]:
    """
    Detecta a intenção da mensagem relacionada a planos.
    
    Args:
        text: Mensagem do usuário
        current_stage: Stage atual (frio, aquecimento, aquecido, quente)
        last_bot_message: Última mensagem do bot (para contexto)
    
    Returns:
        "ASK_PLANS": Quer saber/conhecer os planos
        "CHOOSE_PLAN": Quer escolher/assinar um plano específico
        "OTHER": Outra intenção
    """
    if not text:
        return "OTHER"
    
    text_lower = text.lower().strip()
    
    # Padrões de escolha direta (CHOOSE_PLAN)
    choose_patterns = [
        r'\bquero\s+o\s+anual\b',
        r'\bquero\s+anual\b',
        r'\bvou\s+de\s+anual\b',
        r'\bescolho\s+anual\b',
        r'\bfechar\s+anual\b',
        r'\bassinar\s+anual\b',
        r'\bquero\s+o\s+mensal\b',
        r'\bquero\s+mensal\b',
        r'\bvou\s+de\s+mensal\b',
        r'\bescolho\s+mensal\b',
        r'\bfechar\s+mensal\b',
        r'\bassinar\s+mensal\b',
    ]
    
    # Verifica padrões de escolha
    for pattern in choose_patterns:
        if re.search(pattern, text_lower):
            return "CHOOSE_PLAN"
    
    # Caso especial: mensagem curta "anual" ou "mensal" isolada
    # Só é CHOOSE_PLAN se estiver em contexto apropriado
    if text_lower in ["anual", "mensal"]:
        # Verifica se a última mensagem do bot foi sobre escolher plano
        if last_bot_message:
            last_bot_lower = last_bot_message.lower()
            if any(phrase in last_bot_lower for phrase in [
                "qual plano faz mais sentido",
                "qual plano",
                "mensal ou anual",
                "escolhe",
                "faz mais sentido"
            ]):
                # E está em stage apropriado
                if current_stage in ["aquecido", "quente", "aquecimento"]:
                    return "CHOOSE_PLAN"
    
    # Padrões de pergunta/conhecimento (ASK_PLANS)
    ask_patterns = [
        r'\bquero\s+saber\s+(dos|sobre|os)\s+planos?\b',
        r'\bme\s+explica\s+(os|dos)\s+planos?\b',
        r'\bquanto\s+custa\b',
        r'\bvalores?\b',
        r'\bpreço\b',
        r'\bpreços\b',
        r'\bcomo\s+funciona\s+(o|os)\s+planos?\b',
        r'\bplanos?\b',  # Genérico, mas só se não for escolha
        r'\bopções\s+de\s+planos?\b',
        r'\bquais\s+(são|os)\s+planos?\b',
    ]
    
    # Verifica padrões de pergunta
    for pattern in ask_patterns:
        if re.search(pattern, text_lower):
            # Garante que não é escolha disfarçada
            if not any(choose in text_lower for choose in ["quero o", "vou de", "escolho", "fechar", "assinar"]):
                return "ASK_PLANS"
    
    return "OTHER"


def should_send_plans_explanation(
    intent: str,
    plans_already_explained: bool = False
) -> bool:
    """
    Decide se deve enviar explicação de planos (áudio3 + texto).
    
    Args:
        intent: Intenção detectada (ASK_PLANS, CHOOSE_PLAN, OTHER)
        plans_already_explained: Se os planos já foram explicados anteriormente
    
    Returns:
        True se deve enviar explicação completa
    """
    return intent == "ASK_PLANS" and not plans_already_explained


def should_send_checkout_link(
    intent: str,
    plans_already_explained: bool = False
) -> bool:
    """
    Decide se deve enviar link de checkout.
    
    Args:
        intent: Intenção detectada
        plans_already_explained: Se os planos já foram explicados
    
    Returns:
        True se deve enviar link de checkout
    """
    return intent == "CHOOSE_PLAN"


def extract_plan_choice(text: str) -> Literal["MENSAL", "ANUAL", None]:
    """
    Extrai qual plano foi escolhido da mensagem.
    
    Returns:
        "MENSAL", "ANUAL" ou None
    """
    if not text:
        return None
    
    text_lower = text.lower().strip()
    
    if "anual" in text_lower:
        return "ANUAL"
    elif "mensal" in text_lower:
        return "MENSAL"
    
    return None

