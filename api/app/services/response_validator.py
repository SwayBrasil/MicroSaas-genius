# api/app/services/response_validator.py
"""
Validador de respostas do LLM.
Garante que respostas críticas sigam templates fixos quando necessário.
"""
import re
from typing import Optional, Dict, Any, Tuple


def validate_response_for_stage(
    response: str,
    stage_id: Optional[str] = None,
    phase: Optional[str] = None,
    thread_meta: Optional[Dict[str, Any]] = None,
    user_message: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida resposta do LLM baseado na etapa atual do funil.
    
    CORREÇÃO D: Usa intent_classifier para não exigir áudio3 em CHOOSE_PLAN.
    
    Args:
        response: Resposta do LLM (texto)
        stage_id: ID da etapa atual (ex: "2", "4")
        phase: Fase atual (ex: "aquecimento", "quente")
        thread_meta: Metadados da thread
        user_message: Mensagem do usuário (para detectar intent)
    
    Returns:
        Tuple de (is_valid, error_reason, corrected_response)
        - is_valid: True se resposta está válida
        - error_reason: Razão do erro (se houver)
        - corrected_response: Resposta corrigida (se necessário)
    """
    response_lower = response.lower()
    
    # FASE 2 (aquecimento) - Deve ter áudio2 + imagens
    if stage_id == "2" or phase == "aquecimento":
        # Verifica se tem áudio2
        has_audio2 = bool(re.search(r'\[áudio enviado:.*audio2', response_lower, re.IGNORECASE))
        
        # Verifica se tem imagens de resultado
        has_result_images = bool(re.search(r'\[imagem enviada:.*img_resultado', response_lower, re.IGNORECASE))
        
        # Se não tem áudio2 OU não tem imagens, inválido
        if not has_audio2:
            return False, "FASE_2_MISSING_AUDIO2", None
        if not has_result_images:
            return False, "FASE_2_MISSING_IMAGES", None
        
        # Verifica se tem texto explicativo demais (não deve ter)
        # Se tem frases como "aqui é um áudio" ou "lembra", remove
        problematic_phrases = [
            "aqui é um áudio",
            "lembra",
            "vou te enviar",
            "te mando",
            "aqui está"
        ]
        
        for phrase in problematic_phrases:
            if phrase in response_lower:
                return False, f"FASE_2_PROBLEMATIC_PHRASE_{phrase.upper()}", None
    
    # FASE 3 (quente/planos) - Validação condicionada à intenção
    if stage_id == "4" or phase == "quente":
        # CORREÇÃO D: Detecta intent para saber se é ASK_PLANS ou CHOOSE_PLAN
        intent = "OTHER"
        if user_message:
            from .intent_classifier import detect_plans_intent
            current_stage = phase or (thread_meta.get("lead_stage") if thread_meta else None)
            intent = detect_plans_intent(user_message, current_stage)
            print(f"[VALIDATOR] 🎯 Intent detectado para validação: {intent}")
        
        # Verifica se tem texto dos planos ou link de checkout
        has_planos_text = bool(
            re.search(r'(plano mensal|plano anual|r\$69|r\$598|12x)', response_lower, re.IGNORECASE)
        )
        has_checkout_link = bool(
            re.search(r'(edzz\.la|https?://|link|checkout)', response_lower, re.IGNORECASE)
        )
        
        # Verifica se tem áudio3
        has_audio3 = bool(re.search(r'\[áudio enviado:.*audio3', response_lower, re.IGNORECASE))
        
        # CORREÇÃO D: Se é CHOOSE_PLAN, NÃO exige áudio3
        if intent == "CHOOSE_PLAN":
            print(f"[VALIDATOR] ✅ Intent é CHOOSE_PLAN - não exige áudio3")
            # Valida que tem link de checkout ou texto de fechamento
            if not has_checkout_link and not has_planos_text:
                return False, "FASE_3_CHOOSE_PLAN_MISSING_LINK", None
            # Se tem áudio3 em CHOOSE_PLAN, isso é um problema (não deveria ter)
            if has_audio3:
                print(f"[VALIDATOR] ⚠️ CHOOSE_PLAN tem áudio3 - isso não deveria acontecer")
            return True, None, None
        
        # Se é ASK_PLANS, exige áudio3 + texto dos planos
        if intent == "ASK_PLANS":
            if not has_audio3:
                return False, "FASE_3_MISSING_AUDIO3", None
            if not has_planos_text:
                return False, "FASE_3_MISSING_PLANOS_TEXT", None
            # Verifica se tem apenas áudio sem texto (erro crítico)
            if has_audio3 and not has_planos_text:
                return False, "FASE_3_AUDIO_WITHOUT_TEXT", None
        
        # Se intent não foi detectado mas tem conteúdo de planos, valida genérico
        # (fallback para compatibilidade)
        if not has_planos_text:
            return False, "FASE_3_MISSING_PLANOS_TEXT", None
    
    # Validações gerais
    # Remove frases problemáticas comuns
    problematic_patterns = [
        (r'aqui é um áudio[^\n]*', ''),
        (r'lembra[^\n]*', ''),
        (r'vou te enviar[^\n]*', ''),
        (r'te mando[^\n]*', ''),
    ]
    
    corrected = response
    for pattern, replacement in problematic_patterns:
        if re.search(pattern, corrected, re.IGNORECASE):
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
            corrected = re.sub(r'\n\n+', '\n\n', corrected)  # Remove quebras duplas extras
            corrected = corrected.strip()
    
    # Se foi corrigido, retorna corrigido
    if corrected != response:
        return False, "PROBLEMATIC_PHRASES_REMOVED", corrected
    
    return True, None, None


def should_use_fixed_package(
    stage_id: Optional[str] = None,
    phase: Optional[str] = None,
    intent: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Decide se deve usar pacote fixo ao invés de LLM.
    
    Args:
        stage_id: ID da etapa atual
        phase: Fase atual
        intent: Intent detectado (ex: "DOR_DETECTADA", "INTERESSE_PLANO")
    
    Returns:
        Tuple de (should_use_fixed, package_name)
    """
    # FASE 2 - Sempre usa pacote fixo quando detecta dor
    if intent == "DOR_DETECTADA" or (stage_id == "2" and intent is None):
        return True, "PACOTE_FASE_2"
    
    # FASE 3 - Sempre usa pacote fixo quando detecta interesse em planos
    if intent == "INTERESSE_PLANO" or (stage_id == "4" and intent is None):
        return True, "PACOTE_FASE_3"
    
    return False, None

