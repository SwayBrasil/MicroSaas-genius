# api/app/services/support_detector.py
"""Detecta mensagens de suporte e aciona takeover automático"""
import re
from typing import Dict, Optional, Tuple


# Palavras-chave que indicam suporte (não venda)
SUPPORT_KEYWORDS = [
    # Problemas de acesso
    "não consigo acessar",
    "meu app não funciona",
    "tive problema na plataforma",
    "perdi o acesso",
    "não consigo entrar",
    "erro no login",
    "email não chegou",
    "não reconhece meu usuário",
    "não tá abrindo",
    "app não abre",
    "plataforma não carrega",
    
    # Cancelamento e cobrança
    "quero cancelar",
    "cancelar",
    "cancelamento",
    "fatura",
    "cobrança",
    "cartão",
    "pagamento",
    "estorno",
    "reembolso",
    "não autorizei",
    
    # Problemas técnicos
    "bug",
    "erro",
    "não funciona",
    "travou",
    "travado",
    "lento",
    "demora",
    "não carrega",
    "problema técnico",
    
    # Acesso e conta
    "já sou aluna",
    "já sou cliente",
    "já tenho conta",
    "renovar",
    "renovação",
    "mudar email",
    "trocar email",
    "esqueci senha",
    "recuperar senha",
    
    # Suporte geral
    "suporte",
    "atendimento",
    "ajuda técnica",
    "problema",
    "dúvida técnica",
]


def detect_support(message: str) -> Tuple[bool, Optional[str]]:
    """
    Detecta se a mensagem é sobre suporte (não venda).
    
    Args:
        message: Mensagem do usuário
    
    Returns:
        Tuple de (is_support, reason)
        - is_support: True se é suporte, False se é venda
        - reason: Motivo da detecção (para log)
    """
    if not message or not message.strip():
        return False, None
    
    message_lower = message.lower().strip()
    
    # Verifica cada palavra-chave
    for keyword in SUPPORT_KEYWORDS:
        if keyword in message_lower:
            return True, f"Palavra-chave detectada: '{keyword}'"
    
    # Padrões adicionais
    patterns = [
        r"não\s+(consigo|consegui|conseguir)\s+(acessar|entrar|abrir|usar)",
        r"(app|plataforma|site)\s+(não|não\s+está|está\s+com)\s+(funcionando|abrindo|carregando)",
        r"(quero|preciso|gostaria)\s+(cancelar|estornar|reembolso)",
        r"(problema|erro|bug)\s+(com|no|na)\s+(app|plataforma|sistema)",
        r"já\s+(sou|tenho)\s+(aluna|cliente|conta|assinante)",
    ]
    
    for pattern in patterns:
        if re.search(pattern, message_lower):
            return True, f"Padrão detectado: {pattern}"
    
    return False, None


def should_trigger_takeover(message: str, thread_meta: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
    """
    Decide se deve acionar takeover humano baseado na mensagem.
    
    Args:
        message: Mensagem do usuário
        thread_meta: Metadata da thread (para contexto adicional)
    
    Returns:
        Tuple de (should_takeover, reason)
    """
    is_support, reason = detect_support(message)
    
    if is_support:
        return True, reason
    
    return False, None

