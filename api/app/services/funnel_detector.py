# api/app/services/funnel_detector.py
"""Detecta automaticamente qual funil e etapa um lead deve entrar baseado na mensagem"""
from typing import Dict, Any, Optional, Tuple
import re


def detect_funnel_and_stage(
    message: str,
    thread_meta: Optional[Dict[str, Any]] = None,
    is_first_message: bool = False
) -> Dict[str, Any]:
    """
    Detecta qual funil e etapa o lead deve entrar baseado na mensagem.
    
    Args:
        message: Mensagem do usuário
        thread_meta: Metadata atual da thread (para verificar se já está em um funil)
        is_first_message: Se é a primeira mensagem da thread
    
    Returns:
        Dict com funnel_id, stage_id, source, tags, etc.
    """
    message_lower = message.lower().strip()
    
    # Se já está em um funil, mantém (a menos que seja uma nova entrada explícita)
    if thread_meta and thread_meta.get("funnel_id") and not is_first_message:
        # Verifica se a mensagem indica mudança de funil
        if any(keyword in message_lower for keyword in ["black friday", "bf", "promoção", "desconto 50", "50%"]):
            # Pode ser um funil específico (BF ou recuperação)
            pass  # Continua para detectar
        else:
            # Mantém o funil atual
            return {
                "funnel_id": thread_meta.get("funnel_id"),
                "stage_id": thread_meta.get("stage_id"),
                "source": thread_meta.get("source", "WhatsApp orgânico"),
                "tags": thread_meta.get("tags", []),
            }
    
    # Detecção de funil baseada na mensagem
    result = {
        "funnel_id": None,
        "stage_id": None,
        "source": "WhatsApp orgânico",  # Default
        "tags": [],
    }
    
    # 1. DETECÇÃO DE FUNIL
    
    # Funil Longo (LIFE) - padrão principal
    # Palavras-chave: "life", "quero saber", "como funciona", "emagrecer", "transformar", etc.
    life_keywords = [
        "life", "quero saber", "como funciona", "emagrecer", "emagrecimento",
        "transformar", "corpo", "barriga", "perder peso", "definir", "ganhar massa",
        "treino", "dieta", "nutrição", "fitness", "academia", "exercício"
    ]
    
    # Mini Funil Black Friday
    bf_keywords = ["black friday", "bf", "promoção", "promocao", "oferta especial"]
    
    # Funil de Recuperação 50%
    recovery_keywords = ["desconto 50", "50%", "recuperação", "recuperacao", "não comprei", "não comprou"]
    
    # Detecta qual funil
    if any(keyword in message_lower for keyword in bf_keywords):
        result["funnel_id"] = "2"  # Mini Funil BF
        result["stage_id"] = "1"  # Etapa inicial: Oferta Black Friday
        result["source"] = "Black Friday"
        result["tags"] = ["black_friday", "promoção"]
    elif any(keyword in message_lower for keyword in recovery_keywords):
        result["funnel_id"] = "3"  # Funil de Recuperação 50%
        result["stage_id"] = "1"  # Etapa inicial: Oferta 50%
        result["source"] = "Recuperação pós-plataforma"
        result["tags"] = ["recuperação", "desconto_50"]
    elif any(keyword in message_lower for keyword in life_keywords) or is_first_message:
        # Funil Longo é o padrão
        result["funnel_id"] = "1"  # Funil Longo (LIFE)
        result["stage_id"] = "1"  # Etapa inicial: Boas-vindas e Qualificação
        result["source"] = "WhatsApp orgânico"
        result["tags"] = ["life", "interessado"]
    
    # 2. DETECÇÃO DE TAGS ADICIONAIS baseadas no conteúdo
    
    tags = result.get("tags", [])
    
    # Tags de dor/objetivo
    if any(word in message_lower for word in ["barriga", "abdomen", "pochete", "flacidez"]):
        tags.append("dor_barriga")
    if any(word in message_lower for word in ["emagrecer", "perder peso", "emagrecimento"]):
        tags.append("dor_emagrecimento")
    if any(word in message_lower for word in ["ganhar massa", "massa muscular", "hipertrofia"]):
        tags.append("dor_ganho_massa")
    if any(word in message_lower for word in ["autoestima", "auto estima", "vergonha", "espelho"]):
        tags.append("dor_autoestima")
    if any(word in message_lower for word in ["celulite", "flacidez", "pele"]):
        tags.append("dor_composicao")
    
    # Tags de urgência
    if any(word in message_lower for word in ["urgente", "rápido", "logo", "agora"]):
        tags.append("urgente")
    
    # Tags de interesse
    if any(word in message_lower for word in ["quero", "gostaria", "interessado", "interesse"]):
        tags.append("interessado")
    
    result["tags"] = list(set(tags))  # Remove duplicatas
    
    # 3. DETECÇÃO DE SOURCE mais específica
    
    # Se menciona Eduzz, The Members, etc.
    if "eduzz" in message_lower:
        result["source"] = "Eduzz compra" if "comprou" in message_lower else "Eduzz abandono"
    elif "the members" in message_lower or "members" in message_lower:
        result["source"] = "The Members"
    
    return result


def should_advance_stage(
    message: str,
    current_funnel_id: str,
    current_stage_id: str,
    thread_meta: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Verifica se o lead deve avançar para a próxima etapa baseado na mensagem.
    
    Returns:
        Dict com next_stage_id se deve avançar, ou None
    """
    # TODO: Implementar lógica de avanço de etapa baseada em:
    # - Condições da etapa atual
    # - Intenção detectada na mensagem
    # - Resposta da IA (next_stage do response_processor)
    
    # Por enquanto, retorna None (não avança automaticamente)
    # O avanço será feito pelo response_processor quando a IA retornar next_stage
    return None

