# app/services/gmail_magiclink_service.py
"""
Serviço para buscar links de login mágico do Gmail quando a API TheMembers está indisponível.

Usa Gmail API (OAuth2) para ler e-mails transacionais da TheMembers e extrair links de acesso.
"""
import os
import re
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_API_AVAILABLE = True
except ImportError:
    GMAIL_API_AVAILABLE = False
    logger.warning("[GMAIL_MAGICLINK] Google API libraries não instaladas. Instale: pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2")

# Configurações do Gmail
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
GMAIL_ACCOUNT = os.getenv("GMAIL_ACCOUNT")

# Configurações TheMembers para validação
THEMEMBERS_CUSTOM_DOMAIN = os.getenv("THEMEMBERS_CUSTOM_DOMAIN", "palomamoraesnutri.com.br")
THEMEMBERS_LOGIN_MAGIC_PATH = os.getenv("THEMEMBERS_LOGIN_MAGIC_PATH", "login-magico")

# Timeout e retries
GMAIL_POLL_TIMEOUT = 60  # segundos
GMAIL_POLL_INTERVAL = 10  # segundos entre tentativas
GMAIL_MAX_ATTEMPTS = GMAIL_POLL_TIMEOUT // GMAIL_POLL_INTERVAL  # 6 tentativas


def _mask_token_in_url(url: str) -> str:
    """
    Mascara o token na URL para logs seguros.
    
    Exemplo: https://example.com/login-magico/ABC123XYZ... -> https://example.com/login-magico/ABC123XY...
    
    Args:
        url: URL completa com token
    
    Returns:
        URL com token mascarado (mostra apenas 8 primeiros caracteres)
    """
    if not url:
        return url
    
    # Regex para encontrar o token após /login-magico/
    pattern = r"(https?://[^\s\"'>]+/login-magico/)([A-Za-z0-9\-\._]+)"
    match = re.search(pattern, url)
    
    if match:
        base_url = match.group(1)
        token = match.group(2)
        # Mostra apenas 8 primeiros caracteres do token
        masked_token = token[:8] + "..." if len(token) > 8 else token
        return base_url + masked_token
    
    return url


def _is_gmail_configured() -> bool:
    """
    Verifica se as credenciais do Gmail estão configuradas.
    
    Returns:
        True se todas as credenciais necessárias estão presentes
    """
    return bool(
        GMAIL_CLIENT_ID and 
        GMAIL_CLIENT_SECRET and 
        GMAIL_REFRESH_TOKEN and 
        GMAIL_ACCOUNT
    )


def _build_gmail_service() -> Optional[Any]:
    """
    Constrói o serviço Gmail API usando refresh token.
    
    Returns:
        Serviço Gmail API ou None se não conseguir autenticar
    """
    if not GMAIL_API_AVAILABLE:
        logger.warning("[GMAIL_MAGICLINK] Google API libraries não disponíveis")
        return None
    
    if not _is_gmail_configured():
        logger.debug("[GMAIL_MAGICLINK] Credenciais Gmail não configuradas")
        return None
    
    try:
        # Cria credenciais a partir do refresh token
        creds = Credentials(
            token=None,  # Será renovado automaticamente
            refresh_token=GMAIL_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GMAIL_CLIENT_ID,
            client_secret=GMAIL_CLIENT_SECRET,
        )
        
        # Constrói o serviço Gmail
        service = build("gmail", "v1", credentials=creds)
        logger.debug("[GMAIL_MAGICLINK] Serviço Gmail construído com sucesso")
        return service
        
    except Exception as e:
        logger.error(f"[GMAIL_MAGICLINK] Erro ao construir serviço Gmail: {str(e)}", exc_info=True)
        return None


def _extract_login_magic_link_from_text(text: str) -> Optional[str]:
    """
    Extrai link de login mágico do texto do e-mail usando regex robusta.
    
    Args:
        text: Texto do e-mail (pode ser HTML ou texto plano)
    
    Returns:
        URL completa do link de login mágico ou None se não encontrar
    """
    if not text:
        return None
    
    # Regex robusta para encontrar links de login mágico
    # Aceita http/https, com ou sem www, e captura o token completo
    patterns = [
        # Padrão principal: https://dominio/login-magico/token
        r"https?://(?:www\.)?[^\s\"'<>]+/login-magico/[A-Za-z0-9\-\._~]+",
        # Padrão alternativo: pode ter espaços ou quebras de linha
        r"https?://(?:www\.)?[^\s\"'<>]+/login-magico/[A-Za-z0-9\-\._~]+",
        # Padrão com path configurável
        rf"https?://(?:www\.)?[^\s\"'<>]+/{THEMEMBERS_LOGIN_MAGIC_PATH}/[A-Za-z0-9\-\._~]+",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Retorna o primeiro match válido
            link = matches[0]
            # Valida que contém o path correto
            if f"/{THEMEMBERS_LOGIN_MAGIC_PATH}/" in link.lower() or "/login-magico/" in link.lower():
                logger.debug(f"[GMAIL_MAGICLINK] Link extraído: {_mask_token_in_url(link)}")
                return link
    
    return None


async def _search_recent_messages(
    service: Any,
    buyer_email: str,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Busca mensagens recentes no Gmail que possam conter link de login mágico.
    
    Args:
        service: Serviço Gmail API
        buyer_email: Email do comprador para filtrar
        max_results: Número máximo de resultados
    
    Returns:
        Lista de mensagens encontradas
    """
    try:
        # Query otimizada para encontrar e-mails de acesso da TheMembers
        # Busca nos últimos 2 dias, com termos relacionados a login/acesso
        query = (
            f'newer_than:2d '
            f'("login-magico" OR "login magico" OR "link de acesso" OR "acesso" OR "primeiro acesso") '
            f'from:themembers OR from:noreply OR subject:"acesso" OR subject:"login"'
        )
        
        logger.info(f"[GMAIL_MAGICLINK] Buscando mensagens com query: {query[:100]}...")
        
        # Lista mensagens
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()
        
        messages = results.get("messages", [])
        logger.info(f"[GMAIL_MAGICLINK] Encontradas {len(messages)} mensagens")
        
        return messages
        
    except HttpError as e:
        logger.error(f"[GMAIL_MAGICLINK] Erro HTTP ao buscar mensagens: {e.resp.status} - {str(e)}")
        return []
    except Exception as e:
        logger.error(f"[GMAIL_MAGICLINK] Erro ao buscar mensagens: {str(e)}", exc_info=True)
        return []


async def _get_message_content(service: Any, message_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtém o conteúdo completo de uma mensagem do Gmail.
    
    Args:
        service: Serviço Gmail API
        message_id: ID da mensagem
    
    Returns:
        Dados completos da mensagem ou None se erro
    """
    try:
        message = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()
        
        return message
        
    except HttpError as e:
        logger.error(f"[GMAIL_MAGICLINK] Erro HTTP ao obter mensagem {message_id}: {e.resp.status}")
        return None
    except Exception as e:
        logger.error(f"[GMAIL_MAGICLINK] Erro ao obter mensagem {message_id}: {str(e)}")
        return None


def _extract_text_from_message(message: Dict[str, Any]) -> str:
    """
    Extrai texto do corpo da mensagem (suporta HTML e texto plano).
    
    Args:
        message: Dados completos da mensagem do Gmail
    
    Returns:
        Texto extraído do corpo da mensagem
    """
    text_parts = []
    
    def extract_from_payload(payload: Dict[str, Any]):
        """Recursivamente extrai texto de todas as partes da mensagem"""
        if "parts" in payload:
            for part in payload["parts"]:
                extract_from_payload(part)
        else:
            body = payload.get("body", {})
            data = body.get("data")
            if data:
                import base64
                try:
                    decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                    text_parts.append(decoded)
                except Exception as e:
                    logger.debug(f"[GMAIL_MAGICLINK] Erro ao decodificar parte da mensagem: {str(e)}")
    
    payload = message.get("payload", {})
    extract_from_payload(payload)
    
    # Também tenta obter snippet (resumo) se disponível
    snippet = message.get("snippet", "")
    if snippet:
        text_parts.append(snippet)
    
    return " ".join(text_parts)


async def _find_magic_link_in_messages(
    service: Any,
    messages: List[Dict[str, Any]],
    buyer_email: str
) -> Optional[str]:
    """
    Procura link de login mágico nas mensagens encontradas.
    
    Args:
        service: Serviço Gmail API
        messages: Lista de mensagens do Gmail
        buyer_email: Email do comprador para validar
    
    Returns:
        URL do link de login mágico encontrado ou None
    """
    for msg in messages:
        try:
            message_id = msg.get("id")
            if not message_id:
                continue
            
            # Obtém conteúdo completo da mensagem
            message = await _get_message_content(service, message_id)
            if not message:
                continue
            
            # Extrai texto do corpo
            text = _extract_text_from_message(message)
            
            # Verifica se o e-mail menciona o buyer_email (pode estar em headers ou corpo)
            headers = message.get("payload", {}).get("headers", [])
            to_email = None
            for header in headers:
                if header.get("name", "").lower() == "to":
                    to_email = header.get("value", "")
                    break
            
            # Valida se o e-mail é para o comprador (pode estar no "to" ou mencionado no corpo)
            if buyer_email.lower() not in text.lower() and buyer_email.lower() not in (to_email or "").lower():
                logger.debug(f"[GMAIL_MAGICLINK] Mensagem {message_id} não relacionada ao buyer_email {buyer_email}")
                continue
            
            # Extrai link de login mágico
            link = _extract_login_magic_link_from_text(text)
            if link:
                logger.info(f"[GMAIL_MAGICLINK] ✅ Link encontrado na mensagem {message_id}: {_mask_token_in_url(link)}")
                return link
                
        except Exception as e:
            logger.warning(f"[GMAIL_MAGICLINK] Erro ao processar mensagem: {str(e)}")
            continue
    
    return None


async def get_magic_link_from_gmail(buyer_email: str) -> Optional[Dict[str, Any]]:
    """
    Busca link de login mágico no Gmail para um comprador específico.
    
    Implementa polling com retry: tenta por até 60s (6 tentativas com intervalo de 10s).
    
    Args:
        buyer_email: Email do comprador
    
    Returns:
        Dict com {"url": "<link>", "link_type": "login_magico", "source": "gmail"}
        ou None se não encontrar
    """
    if not GMAIL_API_AVAILABLE:
        logger.debug("[GMAIL_MAGICLINK] Google API libraries não disponíveis")
        return None
    
    if not _is_gmail_configured():
        logger.debug("[GMAIL_MAGICLINK] Credenciais Gmail não configuradas")
        return None
    
    # Constrói serviço Gmail
    service = _build_gmail_service()
    if not service:
        logger.warning("[GMAIL_MAGICLINK] Não foi possível construir serviço Gmail")
        return None
    
    logger.info(f"[GMAIL_MAGICLINK] Iniciando busca de link para {buyer_email} (timeout: {GMAIL_POLL_TIMEOUT}s)")
    
    # Polling: tenta até GMAIL_MAX_ATTEMPTS vezes
    for attempt in range(1, GMAIL_MAX_ATTEMPTS + 1):
        try:
            logger.info(f"[GMAIL_MAGICLINK] Tentativa {attempt}/{GMAIL_MAX_ATTEMPTS} para {buyer_email}")
            
            # Busca mensagens recentes
            messages = await _search_recent_messages(service, buyer_email)
            
            if not messages:
                logger.debug(f"[GMAIL_MAGICLINK] Nenhuma mensagem encontrada na tentativa {attempt}")
                if attempt < GMAIL_MAX_ATTEMPTS:
                    await asyncio.sleep(GMAIL_POLL_INTERVAL)
                continue
            
            # Procura link nas mensagens
            link = await _find_magic_link_in_messages(service, messages, buyer_email)
            
            if link:
                logger.info(f"[GMAIL_MAGICLINK] ✅ Link encontrado na tentativa {attempt}: {_mask_token_in_url(link)}")
                return {
                    "url": link,
                    "link_type": "login_magico",
                    "source": "gmail"
                }
            
            # Se não encontrou, espera antes da próxima tentativa
            if attempt < GMAIL_MAX_ATTEMPTS:
                logger.debug(f"[GMAIL_MAGICLINK] Link não encontrado, aguardando {GMAIL_POLL_INTERVAL}s antes da próxima tentativa...")
                await asyncio.sleep(GMAIL_POLL_INTERVAL)
                
        except HttpError as e:
            # Erros HTTP: loga mas não quebra o fluxo
            logger.warning(f"[GMAIL_MAGICLINK] Erro HTTP na tentativa {attempt}: {e.resp.status} - {str(e)}")
            if attempt < GMAIL_MAX_ATTEMPTS:
                await asyncio.sleep(GMAIL_POLL_INTERVAL)
            continue
        except Exception as e:
            # Outros erros: loga mas não quebra o fluxo
            logger.error(f"[GMAIL_MAGICLINK] Erro na tentativa {attempt}: {str(e)}", exc_info=True)
            if attempt < GMAIL_MAX_ATTEMPTS:
                await asyncio.sleep(GMAIL_POLL_INTERVAL)
            continue
    
    logger.warning(f"[GMAIL_MAGICLINK] ⚠️ Link não encontrado após {GMAIL_MAX_ATTEMPTS} tentativas para {buyer_email}")
    return None

