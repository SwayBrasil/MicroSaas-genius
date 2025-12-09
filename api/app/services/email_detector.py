# app/services/email_detector.py
"""
Serviço para detectar e extrair emails de mensagens.
"""
import re
from typing import Optional


def extract_email_from_text(text: str) -> Optional[str]:
    """
    Extrai email de um texto usando regex.
    
    Args:
        text: Texto para analisar
        
    Returns:
        Email encontrado ou None
    """
    if not text:
        return None
    
    # Regex para email (bem comum)
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    matches = re.findall(email_pattern, text)
    
    if matches:
        # Retorna o primeiro email encontrado
        email = matches[0].lower().strip()
        # Validação básica
        if len(email) > 5 and "@" in email and "." in email.split("@")[1]:
            return email
    
    return None


def should_update_contact_email(message_content: str, current_email: Optional[str] = None) -> Optional[str]:
    """
    Verifica se a mensagem contém um email e se deve atualizar o contato.
    
    Args:
        message_content: Conteúdo da mensagem
        current_email: Email atual do contato (se houver)
        
    Returns:
        Email para atualizar ou None
    """
    detected_email = extract_email_from_text(message_content)
    
    if not detected_email:
        return None
    
    # Se já tem email e é o mesmo, não precisa atualizar
    if current_email and current_email.lower() == detected_email:
        return None
    
    # Se não tem email ou é diferente, retorna o novo
    return detected_email


