# api/app/services/content_detector.py
"""
Detector de Conteúdo - Detecta planos e checkout por CONTEÚDO da resposta (não por intent do usuário)
REGRA 2: A decisão NÃO DEPENDE DO USUÁRIO, e sim do CONTEÚDO da resposta gerada pelo LLM
"""
import re
from typing import Literal


def is_plan_explanation(text: str) -> bool:
    """
    REGRA 2: Detecta se o texto contém explicação de planos.
    
    A decisão NÃO depende do intent do usuário, mas sim do conteúdo da resposta do LLM.
    
    Args:
        text: Texto da resposta gerada pelo LLM
    
    Returns:
        True se contém explicação de planos
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Keywords que indicam explicação de planos
    plan_keywords = [
        "plano mensal",
        "plano anual",
        "r$69",
        "r$ 69",
        "r$69,90",
        "r$ 69,90",
        "12x de r$",
        "12x de r$ 49",
        "598,80",
        "598.80",
        "acesso ao life",
        "acesso à base do life",
        "acesso completo",
        "pode cancelar quando quiser",
        "parcelar em até 12x",
        "módulo exclusivo",
        "shape slim"
    ]
    
    return any(keyword in text_lower for keyword in plan_keywords)


def is_checkout(text: str) -> bool:
    """
    REGRA 2: Detecta se o texto contém checkout (link de compra).
    
    Args:
        text: Texto da resposta gerada pelo LLM
    
    Returns:
        True se contém checkout/link
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Keywords que indicam checkout
    checkout_keywords = [
        "edzz.la",
        "eduzz.la",
        "finalizar",
        "checkout",
        "link pra você",
        "aqui está o link",
        "clique aqui",
        "comprar agora",
        "assinar agora",
        "link de compra",
        "link para comprar"
    ]
    
    return any(keyword in text_lower for keyword in checkout_keywords)


def classify_response_content(text: str) -> Literal["PLAN_EXPLANATION", "CHECKOUT", "FASE_2", "OTHER"]:
    """
    Classifica o conteúdo da resposta do LLM em categorias do funil.
    
    Args:
        text: Texto da resposta gerada pelo LLM
    
    Returns:
        "PLAN_EXPLANATION": Contém explicação de planos
        "CHECKOUT": Contém link de checkout
        "FASE_2": Contém áudio2 + imagens (prova social)
        "OTHER": Outro conteúdo
    """
    if not text:
        return "OTHER"
    
    text_lower = text.lower()
    
    # Prioridade 1: Checkout (não deve ter áudio3)
    if is_checkout(text):
        return "CHECKOUT"
    
    # Prioridade 2: Explicação de planos (deve ter áudio3 antes)
    if is_plan_explanation(text):
        return "PLAN_EXPLANATION"
    
    # Prioridade 3: Fase 2 (áudio2 + imagens)
    if ("[áudio enviado: audio2" in text_lower or 
        "[áudio enviada: audio2" in text_lower or
        "audio2_dor_generica" in text_lower) and "img_resultado" in text_lower:
        return "FASE_2"
    
    return "OTHER"

