# app/services/themembers_service.py
"""
Serviço de integração com The Members API.
"""
import os
import logging
from typing import Optional, Dict, Any, List, Tuple
import httpx
from fastapi import HTTPException

# Tokens obrigatórios via ENV (sem defaults para evitar vazamento)
THEMEMBERS_DEV_TOKEN = os.getenv("THEMEMBERS_DEV_TOKEN")
THEMEMBERS_PLATFORM_TOKEN = os.getenv("THEMEMBERS_PLATFORM_TOKEN")
THEMEMBERS_BASE_URL = os.getenv("THEMEMBERS_BASE_URL", "https://registration.themembers.dev.br/api")
THEMEMBERS_PUBLIC_BASE_URL = os.getenv("THEMEMBERS_PUBLIC_BASE_URL", "https://registration.themembers.dev.br")

# Base URL separada para magic-link (pode ser outro serviço/host)
THEMEMBERS_MAGICLINK_BASE_URL = os.getenv("THEMEMBERS_MAGICLINK_BASE_URL", THEMEMBERS_BASE_URL)

# Endpoint para magic-link (padrão oficial: partners/magic-link)
# Documentação: https://documentation.themembers.dev.br/api-gerenciamento-de-usuarios/referencia-da-api/link-magico
THEMEMBERS_MAGICLINK_ENDPOINT = os.getenv("THEMEMBERS_MAGICLINK_ENDPOINT", "partners/magic-link")

# Path público para login mágico (ex: /login-magico)
THEMEMBERS_LOGIN_MAGIC_PATH = os.getenv("THEMEMBERS_LOGIN_MAGIC_PATH", "/login-magico")

logger = logging.getLogger(__name__)


# ========== HELPERS CENTRALIZADOS ==========

def _has_magiclink_tokens() -> bool:
    """
    Verifica se os tokens necessários para magic-link estão configurados.
    
    Returns:
        True se THEMEMBERS_DEV_TOKEN e THEMEMBERS_PLATFORM_TOKEN estão configurados (não vazios)
    """
    return bool(THEMEMBERS_DEV_TOKEN and THEMEMBERS_PLATFORM_TOKEN)


def _classify_access_link(url: str) -> str:
    """
    Classifica o tipo de link de acesso retornado.
    
    Args:
        url: URL do link de acesso
    
    Returns:
        "login_magico" se contém "/login-magico/" (ou path configurado)
        "compra_concluida_fallback" se contém "/compra-concluida/"
        "unknown" caso contrário
    """
    if not url or not isinstance(url, str):
        return "unknown"
    
    login_magic_path = THEMEMBERS_LOGIN_MAGIC_PATH.strip('/')
    
    # Verifica se é login mágico (path configurado ou padrão)
    if f"/{login_magic_path}/" in url or url.endswith(f"/{login_magic_path}"):
        return "login_magico"
    
    # Verifica se é fallback compra-concluida
    if "/compra-concluida/" in url or "/compra-concluida?" in url:
        return "compra_concluida_fallback"
    
    return "unknown"


async def get_products() -> List[Dict[str, Any]]:
    """
    Busca todos os produtos da The Members.
    
    Returns:
        Lista de produtos com seus dados completos.
    """
    url = f"{THEMEMBERS_BASE_URL}/products/all-products/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            # A API pode retornar em diferentes formatos
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "products" in data:
                return data["products"]
            elif isinstance(data, dict):
                return [data]
            else:
                return []
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=500,
                detail=f"TheMembers API error: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching products: {str(e)}"
            )


async def get_user_by_email(email: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Busca usuário na The Members pelo email.
    
    IMPORTANTE: Se a API retornar 401/403, não lança HTTPException(500).
    Retorna (None, None) e loga como "integração indisponível" para permitir fallback.
    
    Args:
        email: Email do usuário
        
    Returns:
        Tupla (user, subscription) ou (None, None) se não encontrado ou integração indisponível.
    """
    url = f"{THEMEMBERS_BASE_URL}/users/show-email/{email}/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            
            if resp.status_code == 200:
                data = resp.json()
                return data.get("user"), data.get("subscription")
            
            if resp.status_code == 404:
                return None, None
            
            # 401/403: Não lança 500, retorna None e loga como integração indisponível
            if resp.status_code in [401, 403]:
                logger.warning(f"[THEMEMBERS][users] Unauthorized ({resp.status_code}). Integração indisponível.")
                return None, None
            
            # Outros erros: loga mas não lança 500 para permitir fallback
            logger.warning(f"[THEMEMBERS][users] Erro HTTP {resp.status_code}: {resp.text[:200]}")
            return None, None
            
        except httpx.HTTPStatusError as e:
            # Se for 401/403, não lança exceção
            if e.response.status_code in [401, 403]:
                logger.warning(f"[THEMEMBERS][users] Unauthorized ({e.response.status_code}). Integração indisponível.")
                return None, None
            # Outros erros HTTP: loga e retorna None
            logger.warning(f"[THEMEMBERS][users] HTTP error {e.response.status_code}: {str(e)}")
            return None, None
        except Exception as e:
            # Erros inesperados: loga mas retorna None para permitir fallback
            logger.error(f"[THEMEMBERS][users] Erro ao buscar usuário: {str(e)}", exc_info=True)
            return None, None


async def create_user_with_product(
    email: str,
    name: str,
    last_name: str,
    document: str | None = None,
    phone: str | None = None,
    reference_id: str | None = None,
    accession_date: str | None = None,
    product_id: str | None = None,
) -> Dict[str, Any]:
    """
    Cria usuário + assinatura em um passo, usando o endpoint /users/create.
    
    Args:
        email: Email do usuário
        name: Primeiro nome
        last_name: Sobrenome
        document: CPF/CNPJ (opcional)
        phone: Telefone (opcional)
        reference_id: ID de referência externa (ex: order_id da Eduzz)
        accession_date: Data de adesão (formato YYYY-MM-DD)
        product_id: ID do produto na The Members
        
    Returns:
        Resposta completa da API The Members
    """
    if not product_id:
        product_id = os.getenv("THEMEMBERS_DEFAULT_PRODUCT_ID", "2352153")
    
    url = f"{THEMEMBERS_BASE_URL}/users/create/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"

    payload = {
        "product_id": [product_id],
        "users": [
            {
                "name": name,
                "last_name": last_name,
                "email": email,
                "document": document,
                "phone": phone,
                "reference_id": reference_id,
                "accession_date": accession_date or "2025-01-01",
            }
        ],
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=500,
                detail=f"TheMembers create user error: {e.response.status_code} - {e.response.text}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creating user: {str(e)}"
            )


async def get_course_reports(
    product_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Dict[str, Any]:
    """
    Busca relatórios de cursos/produtos da The Members.
    
    Args:
        product_id: ID do produto (opcional)
        start_date: Data inicial (formato YYYY-MM-DD)
        end_date: Data final (formato YYYY-MM-DD)
    
    Returns:
        Dados de relatórios
    """
    # Monta URL com parâmetros opcionais
    base_url = f"{THEMEMBERS_BASE_URL}/reports/course-reports/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"
    
    params = {}
    if product_id:
        params["product_id"] = product_id
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=500,
                detail=f"TheMembers reports error: {e.response.status_code} - {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching reports: {str(e)}"
            )


# Circuit breaker para magic-link (evita spam de 404)
import time
_MAGICLINK_DISABLED_UNTIL = 0  # epoch timestamp

def _magiclink_is_temporarily_disabled() -> bool:
    """Verifica se magic-link está temporariamente desabilitado (circuit breaker)"""
    return time.time() < _MAGICLINK_DISABLED_UNTIL

def _disable_magiclink_for(seconds: int = 900):
    """Desabilita magic-link por N segundos (padrão: 15 minutos)"""
    global _MAGICLINK_DISABLED_UNTIL
    _MAGICLINK_DISABLED_UNTIL = time.time() + seconds
    logger.warning(f"[THEMEMBERS][magic-link] ⚠️ Circuit breaker ativado: desabilitado por {seconds}s")

async def get_magic_link(email: str) -> Optional[str]:
    """
    Obtém o "Link Mágico" oficial do The Members para um email.
    
    Endpoint oficial: POST {URL_BASE}/partners/magic-link/{dev_token}/{platform_token}
    Documentação: https://documentation.themembers.dev.br/api-gerenciamento-de-usuarios/referencia-da-api/link-magico
    
    Formato de resposta esperado:
    - {"status": "success", "url": "https://.../login-magico/{token_magico}"}
    
    Tokens necessários:
    - THEMEMBERS_DEV_TOKEN: Token do desenvolvedor
    - THEMEMBERS_PLATFORM_TOKEN: Token da plataforma (obtido em: Plataforma > Configurações > Token)
    
    IMPORTANTE:
    - Link mágico expira em ~24 horas e é uso único
    - Se receber 404 consistente, ativa circuit breaker para evitar spam
    - Se tokens não configurados, retorna None imediatamente (fail-fast)
    
    Args:
        email: Email do usuário
    
    Returns:
        URL completa do link mágico (login-magico/<jwt>) ou None se não conseguir gerar
    """
    # Fail-fast: se tokens não configurados, retorna None imediatamente
    if not _has_magiclink_tokens():
        logger.debug(f"[THEMEMBERS][magic-link] Tokens não configurados, retornando None imediatamente")
        return None
    
    # Circuit breaker: se magic-link foi desabilitado recentemente, pula
    if _magiclink_is_temporarily_disabled():
        logger.debug(f"[THEMEMBERS][magic-link] ⏭️ Circuit breaker ativo, pulando tentativa para {email}")
        return None
    
    try:
        # Usa base URL específica para magic-link (pode ser diferente da API principal)
        # URL_BASE da API (ex: https://registration.themembers.dev.br/api)
        base_url = THEMEMBERS_MAGICLINK_BASE_URL
        endpoint_path = THEMEMBERS_MAGICLINK_ENDPOINT.strip('/')
        
        # Endpoints oficiais conforme documentação:
        # https://documentation.themembers.dev.br/api-gerenciamento-de-usuarios/referencia-da-api/link-magico
        # Formato 1 (preferencial): tokens no path
        # Formato 2 (alternativo): tokens na querystring
        possible_endpoints = [
            # Formato 1: POST {URL_BASE}/partners/magic-link/{dev_token}/{platform_token}
            f"{base_url}/{endpoint_path}/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}",
            # Formato 2: POST {URL_BASE}/partners/magic-link/?developer_token=...&platform_token=...
            f"{base_url}/{endpoint_path}/?developer_token={THEMEMBERS_DEV_TOKEN}&platform_token={THEMEMBERS_PLATFORM_TOKEN}",
        ]
        
        payload = {"email": email}
        
        logger.info(f"[THEMEMBERS][magic-link] Tentando obter link mágico para email: {email}")
        logger.info(f"[THEMEMBERS][magic-link] Endpoint configurado: {endpoint_path}")
        
        # Sempre usa POST conforme documentação oficial
        # Documentação: https://documentation.themembers.dev.br/api-gerenciamento-de-usuarios/referencia-da-api/link-magico
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in possible_endpoints:
                try:
                    logger.info(f"[THEMEMBERS][magic-link] Tentando POST: {url[:80]}...")
                    resp = await client.post(url, json=payload)
                    
                    logger.info(f"[THEMEMBERS][magic-link] Response status: {resp.status_code} para {url[:60]}...")
                    
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            
                            # Formato esperado pela API: {"status": "success", "url": "https://.../login-magico/{token_magico}"}
                            # Documentação: https://documentation.themembers.dev.br/api-gerenciamento-de-usuarios/referencia-da-api/link-magico
                            
                            # PRIORIDADE 1: URL completa (formato primário da API)
                            magic_link_url = data.get("url")
                            
                            if magic_link_url and isinstance(magic_link_url, str) and magic_link_url.startswith("http"):
                                logger.info(f"[THEMEMBERS][magic-link] ✅ URL completa obtida (formato oficial): {magic_link_url[:50]}...")
                                return magic_link_url
                            
                            # FALLBACK: Campos alternativos (caso API retorne formato diferente)
                            magic_link_url = (
                                data.get("link") or 
                                data.get("magic_link") or
                                data.get("access_url") or
                                data.get("login_url")
                            )
                            
                            if magic_link_url and isinstance(magic_link_url, str) and magic_link_url.startswith("http"):
                                logger.info(f"[THEMEMBERS][magic-link] ✅ URL completa obtida (formato alternativo): {magic_link_url[:50]}...")
                                return magic_link_url
                            
                            # FALLBACK FINAL: Apenas token/JWT na resposta - construir URL pública
                            # (Apenas se API não retornar URL completa)
                            token = (
                                data.get("token") or 
                                data.get("jwt") or 
                                data.get("access_token") or
                                data.get("magic_token")
                            )
                            
                            if token and isinstance(token, str):
                                logger.warning(f"[THEMEMBERS][magic-link] ⚠️ API retornou apenas token (não URL completa). Construindo URL...")
                                
                                # Usa custom domain para construir URL pública
                                custom_domain = os.getenv("THEMEMBERS_CUSTOM_DOMAIN") or os.getenv("PURCHASE_SUCCESS_DOMAIN")
                                if not custom_domain:
                                    logger.warning(f"[THEMEMBERS][magic-link] ⚠️ Token obtido mas THEMEMBERS_CUSTOM_DOMAIN não configurado")
                                    return None
                                
                                # Remove protocolo se presente e preserva www. se existir
                                if custom_domain.startswith("http://") or custom_domain.startswith("https://"):
                                    base_domain = custom_domain.rstrip('/')
                                else:
                                    base_domain = f"https://{custom_domain.rstrip('/')}"
                                
                                # Path do login mágico (default: /login-magico)
                                login_path = THEMEMBERS_LOGIN_MAGIC_PATH.strip('/')
                                
                                # Constrói URL: https://www.dominio.com/login-magico/<token>
                                constructed_url = f"{base_domain}/{login_path}/{token}"
                                
                                logger.info(f"[THEMEMBERS][magic-link] ✅ URL construída: {constructed_url[:50]}...")
                                return constructed_url
                            
                            # Se não encontrou nem URL nem token
                            logger.warning(f"[THEMEMBERS][magic-link] ⚠️ Resposta não contém URL nem token. Campos: {list(data.keys())}")
                            logger.debug(f"[THEMEMBERS][magic-link] Response body: {str(data)[:300]}")
                            
                        except Exception as e:
                            logger.warning(f"[THEMEMBERS][magic-link] ⚠️ Erro ao parsear JSON: {str(e)}")
                            logger.debug(f"[THEMEMBERS][magic-link] Response text: {resp.text[:300]}")
                    
                    elif resp.status_code == 404:
                        logger.debug(f"[THEMEMBERS][magic-link] Endpoint não encontrado (404): {url[:60]}...")
                        # Se todos os endpoints retornarem 404, ativa circuit breaker
                        if url == possible_endpoints[-1]:  # Última tentativa
                            logger.warning(f"[THEMEMBERS][magic-link] ⚠️ Todos os endpoints retornaram 404. Ativando circuit breaker por 15min.")
                            _disable_magiclink_for(900)  # 15 minutos
                        continue  # Tenta próximo endpoint
                    
                    elif resp.status_code in [401, 403]:
                        logger.error(f"[THEMEMBERS][magic-link] ❌ Erro de autenticação ({resp.status_code}). Ativando circuit breaker.")
                        _disable_magiclink_for(1800)  # 30 minutos para erros de auth
                        return None  # Não tenta outros endpoints se é problema de auth
                    
                    else:
                        logger.debug(f"[THEMEMBERS][magic-link] Status {resp.status_code} para {url[:60]}...")
                        continue  # Tenta próximo endpoint
                        
                except httpx.TimeoutException:
                    logger.warning(f"[THEMEMBERS][magic-link] ⚠️ Timeout ao chamar: {url[:60]}...")
                    continue
                except httpx.HTTPStatusError as e:
                    logger.debug(f"[THEMEMBERS][magic-link] HTTP {e.response.status_code} para {url[:60]}...")
                    continue
                except Exception as e:
                    logger.debug(f"[THEMEMBERS][magic-link] Erro ao chamar {url[:60]}...: {str(e)}")
                    continue
            
            # Se chegou aqui, nenhum endpoint funcionou
            logger.warning(f"[THEMEMBERS][magic-link] ⚠️ Nenhum endpoint de magic-link funcionou para {email}")
            return None
                    
    except Exception as e:
        logger.error(f"[THEMEMBERS][magic-link] ❌ Erro geral ao obter magic-link: {str(e)}", exc_info=True)
        return None


async def validate_with_curl(link: str) -> Tuple[bool, int, str]:
    """
    Fallback: Valida link usando curl via subprocess (mais robusto em Docker).
    
    Usado quando httpx falha mas curl funciona (problemas com IPv6, HTTP/2, TLS handshake).
    
    Args:
        link: URL para validar
    
    Returns:
        Tupla (is_valid, status_code, error_message)
    """
    import asyncio
    import subprocess
    
    try:
        # curl com flags:
        # -sS: silent mas mostra erros
        # -L: segue redirects
        # --max-time 20: timeout total
        # -w: escreve HTTP code e final URL
        # -o /dev/null: descarta output
        cmd = [
            "curl",
            "-sS",
            "-L",
            "--max-time", "20",
            "-w", "\nHTTP_CODE=%{http_code}\nFINAL_URL=%{url_effective}\n",
            "-o", "/dev/null",
            link
        ]
        
        logger.info(f"[VALIDATE_LINK] [CURL_FALLBACK] Executando curl para {link[:50]}...")
        
        # Executa curl de forma assíncrona
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp"  # Diretório seguro
        )
        
        stdout, stderr = await process.communicate()
        return_code = process.returncode
        
        # Parse output do curl
        output = stdout.decode('utf-8', errors='ignore').strip()
        error_output = stderr.decode('utf-8', errors='ignore').strip()
        
        # Extrai HTTP code e final URL do output
        http_code = None
        final_url = link
        
        for line in output.split('\n'):
            if line.startswith('HTTP_CODE='):
                try:
                    http_code = int(line.split('=')[1])
                except (ValueError, IndexError):
                    pass
            elif line.startswith('FINAL_URL='):
                final_url = line.split('=', 1)[1] if '=' in line else link
        
        # Se curl retornou erro (return_code != 0) ou não conseguiu HTTP code
        if return_code != 0 or http_code is None:
            error_msg = f"curl failed (exit={return_code}): {error_output[:200]}"
            logger.warning(f"[VALIDATE_LINK] [CURL_FALLBACK] {error_msg}")
            return False, 0, error_msg
        
        # Considera válido se HTTP 200-399 (sucesso e redirects)
        is_valid = 200 <= http_code < 400
        
        if is_valid:
            logger.info(f"[VALIDATE_LINK] [CURL_FALLBACK] ✅ Link válido (HTTP {http_code}): {link[:50]}... → {final_url[:50]}...")
            return True, http_code, ""
        else:
            logger.info(f"[VALIDATE_LINK] [CURL_FALLBACK] Link inválido (HTTP {http_code}): {link[:50]}... → {final_url[:50]}...")
            return False, http_code, f"HTTP {http_code}"
            
    except FileNotFoundError:
        error_msg = "curl não encontrado no sistema"
        logger.warning(f"[VALIDATE_LINK] [CURL_FALLBACK] {error_msg}")
        return False, 0, error_msg
    except Exception as e:
        error_msg = f"Erro ao executar curl: {type(e).__name__}: {repr(e)}"
        logger.warning(f"[VALIDATE_LINK] [CURL_FALLBACK] {error_msg}")
        return False, 0, error_msg


async def validate_link_exists(link: str, follow_redirects: bool = True) -> Tuple[bool, int, str]:
    """
    Valida se um link existe fazendo uma requisição GET com httpx.
    
    Se httpx falhar, usa fallback automático para curl (mais robusto em Docker).
    
    Para links de login/magic-link, usa follow_redirects=True para validar
    o destino final (muitos links de login têm múltiplos redirects).
    
    Configurações httpx para máxima compatibilidade em Docker:
    - http2=False: Evita problemas com HTTP/2 em alguns ambientes
    - trust_env=False: Não usa proxy/SSL do ambiente (mais previsível)
    - follow_redirects=True: Segue redirects até destino final
    - timeout separado: connect=5s, read=15s (necessário para Cloudflare/WAF/WordPress)
    
    Args:
        link: URL para validar
        follow_redirects: Se True, segue redirects até o destino final
    
    Returns:
        Tupla (is_valid, status_code, error_message)
        - is_valid: True se status final é 200 ou redirect válido
        - status_code: Código HTTP retornado (final se follow_redirects=True)
        - error_message: Mensagem de erro (se houver)
    """
    # Primeira tentativa: httpx com configurações seguras
    try:
        # Timeout separado: connect (5s) + read (15s) - necessário para Cloudflare/WAF/WordPress
        timeout = httpx.Timeout(5.0, connect=5.0, read=15.0)
        
        # Headers com User-Agent para evitar bloqueio por WAF
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SwayBot/1.0; +https://swaybrasil.com)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        # Configurações para máxima compatibilidade em Docker:
        # - http2=False: Evita problemas com HTTP/2 handshake em alguns ambientes
        # - trust_env=False: Não usa proxy/SSL do ambiente (mais previsível)
        # - follow_redirects: Segue redirects até destino final
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=follow_redirects,
            headers=headers,
            http2=False,  # Desabilita HTTP/2 (evita problemas em Docker)
            trust_env=False,  # Não usa proxy/SSL do ambiente
        ) as client:
            # Tenta GET (mais confiável que HEAD para WordPress/sites dinâmicos)
            resp = await client.get(link)
            status = resp.status_code
            final_url = str(resp.url)
            
            # Log detalhado para diagnóstico
            redirect_history = [str(r.url) for r in resp.history] if hasattr(resp, 'history') else []
            if redirect_history:
                logger.info(f"[VALIDATE_LINK] [HTTPX] Redirect chain para {link[:50]}...: {len(redirect_history)} hops → {final_url[:60]}...")
            
            # Aceita 200 (OK) e redirects (301, 302, 303, 307)
            # Se follow_redirects=True, o status final já é o destino
            is_valid = status in [200, 301, 302, 303, 307]
            
            if not is_valid:
                error_body = resp.text[:500] if hasattr(resp, 'text') else ""
                logger.info(f"[VALIDATE_LINK] [HTTPX] Link inválido (status {status}): {link[:50]}... → {final_url[:50]}...")
                return False, status, error_body
            
            logger.info(f"[VALIDATE_LINK] [HTTPX] ✅ Link válido (status {status}): {link[:50]}... → {final_url[:50]}...")
            return True, status, ""
            
    except httpx.TimeoutException as e:
        error_msg = f"Timeout (connect/read): {type(e).__name__}: {repr(e)}"
        logger.warning(f"[VALIDATE_LINK] [HTTPX] {error_msg} ao validar link {link[:50]}...")
        logger.info(f"[VALIDATE_LINK] [HTTPX] Tentando fallback para curl...")
        # Fallback para curl
        return await validate_with_curl(link)
        
    except httpx.ConnectError as e:
        error_msg = f"Connection error: {type(e).__name__}: {repr(e)}"
        logger.warning(f"[VALIDATE_LINK] [HTTPX] {error_msg} ao validar link {link[:50]}...")
        logger.info(f"[VALIDATE_LINK] [HTTPX] Tentando fallback para curl...")
        # Fallback para curl
        return await validate_with_curl(link)
        
    except httpx.HTTPStatusError as e:
        # HTTPStatusError não é necessariamente um erro fatal (pode ser 404, 500, etc.)
        # Mas se for erro de cliente/servidor, tenta curl como fallback
        if e.response.status_code >= 500:
            error_msg = f"HTTP server error {e.response.status_code}: {type(e).__name__}: {repr(e)}"
            logger.warning(f"[VALIDATE_LINK] [HTTPX] {error_msg} ao validar link {link[:50]}...")
            logger.info(f"[VALIDATE_LINK] [HTTPX] Tentando fallback para curl...")
            return await validate_with_curl(link)
        else:
            # Erros 4xx são válidos (link existe, mas retorna erro de cliente)
            error_msg = f"HTTP error {e.response.status_code}: {type(e).__name__}: {repr(e)}"
            logger.info(f"[VALIDATE_LINK] [HTTPX] {error_msg} ao validar link {link[:50]}...")
            return False, e.response.status_code, error_msg
            
    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__}: {repr(e)}"
        logger.warning(f"[VALIDATE_LINK] [HTTPX] {error_msg} ao validar link {link[:50]}...")
        logger.info(f"[VALIDATE_LINK] [HTTPX] Tentando fallback para curl...")
        # Fallback para curl em qualquer exceção não tratada
        return await validate_with_curl(link)


async def resolve_first_access_link(
    email: str,
    user_id: Optional[str] = None,
    subscription_data: Optional[Dict[str, Any]] = None,
    user_data: Optional[Dict[str, Any]] = None,
    transaction_key: Optional[str] = None,
    order_id: Optional[str] = None,
) -> Optional[str]:
    """
    Resolve o link de primeiro acesso da The Members usando estratégias em ordem de prioridade.
    
    Ordem de estratégias (mais robusta para produção):
    1. MAGIC-LINK: Endpoint oficial "Link Mágico" com JWT (login-magico/<jwt>)
    2. A: Link direto retornado pela API (campos em subscription/user) - se for link de login
    3. B: Endpoint de geração oficial documentado (se existir)
    4. ÚLTIMO: compra-concluida/?transactionkey=... (apenas como fallback)
    
    IMPORTANTE: Fail-fast - se tokens não configurados, não tenta estratégias que dependem de API TheMembers.
    Vai direto para fallback compra-concluida se transaction_key disponível.
    
    Critérios:
    - Considera "link de acesso" aquele que contenha /login-magico/ (ou path configurado)
    - Se retornar compra-concluida, marca em log como "fallback não ideal"
    
    Args:
        email: Email do usuário
        user_id: ID do usuário (opcional, será buscado se não fornecido)
        subscription_data: Dados da subscription (opcional)
        user_data: Dados do usuário (opcional)
        transaction_key: Chave de transação (para fallback compra-concluida)
        order_id: ID do pedido (opcional)
    
    Returns:
        Link de primeiro acesso válido ou None
    """
    strategy_used = None
    link_found = None
    
    try:
        # ========== FAIL-FAST: Verifica tokens antes de tentar estratégias ==========
        if not _has_magiclink_tokens():
            logger.info(f"[RESOLVE_ACCESS_LINK] Tokens não configurados, pulando estratégias TheMembers e indo para fallback")
            # Vai direto para fallback compra-concluida se transaction_key disponível
            if transaction_key:
                strategy_used = "FALLBACK_COMPRA_CONCLUIDA"
                custom_domain = os.getenv("THEMEMBERS_CUSTOM_DOMAIN") or os.getenv("PURCHASE_SUCCESS_DOMAIN")
                if custom_domain:
                    if custom_domain.startswith("http://") or custom_domain.startswith("https://"):
                        base_domain = custom_domain.rstrip('/')
                    else:
                        base_domain = f"https://{custom_domain.rstrip('/')}"
                    fallback_link = f"{base_domain}/compra-concluida/?transactionkey={transaction_key}"
                    logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Fallback direto (tokens não configurados): {fallback_link[:80]}...")
                    is_valid, status, error = await validate_link_exists(fallback_link, follow_redirects=True)
                    if is_valid:
                        logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ [Estratégia {strategy_used}] Fallback usado (tokens não configurados): {fallback_link[:50]}...")
                        return fallback_link
            # Se não tem transaction_key, retorna None
            logger.warning(f"[RESOLVE_ACCESS_LINK] Tokens não configurados e transaction_key não disponível. Não é possível gerar link.")
            return None
        
        # ========== ESTRATÉGIA 1: MAGIC-LINK REAL (JWT do The Members) ==========
        strategy_used = "MAGIC-LINK"
        logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Tentando obter link mágico oficial com JWT (sem buscar user)...")
        
        magic_link = await get_magic_link(email)
        if magic_link:
            logger.info(f"[RESOLVE_ACCESS_LINK] ✅ [Estratégia {strategy_used}] Link mágico obtido: {magic_link[:50]}...")
            # Valida o link mágico com follow_redirects=True (links de login têm redirects)
            # IMPORTANTE: Link mágico expira em ~24h e é uso único, então validação pode falhar após uso/expirado
            is_valid, status, error = await validate_link_exists(magic_link, follow_redirects=True)
            if is_valid:
                # Verifica se é realmente um link de login-magico
                # Aceita tanto o path configurado quanto o padrão "/login-magico/"
                login_magic_path = THEMEMBERS_LOGIN_MAGIC_PATH.strip('/')
                is_login_magic = (
                    f"/{login_magic_path}/" in magic_link or 
                    magic_link.endswith(f"/{login_magic_path}") or
                    "/login-magico/" in magic_link  # Path padrão da API
                )
                
                if is_login_magic:
                    link_type = _classify_access_link(magic_link)
                    logger.info(f"[RESOLVE_ACCESS_LINK] ✅ [Estratégia {strategy_used}] Link de login mágico válido (status {status}, link_type={link_type}): {magic_link[:50]}...")
                    return magic_link
                else:
                    logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ [Estratégia {strategy_used}] Link obtido mas não é login-magico: {magic_link[:50]}...")
            else:
                logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ [Estratégia {strategy_used}] Link mágico inválido (status {status}): {error[:100]}")
                logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ Nota: Link mágico expira em ~24h e é uso único. Pode estar expirado ou já usado.")
                # Continua para outras estratégias mesmo se o magic-link for inválido
        else:
            logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Link mágico não disponível, continuando para outras estratégias...")
        
        # Se não temos user_id ou dados, tenta buscar usuário (necessário para estratégias A/B)
        # Mas se falhar (incluindo 401/403), continua para estratégias que não precisam de usuário (fallback)
        user_fetch_failed = False
        if not user_id or not user_data:
            # Só tenta buscar usuário se tokens estão configurados (fail-fast)
            if _has_magiclink_tokens():
                logger.info(f"[RESOLVE_ACCESS_LINK] Buscando usuário na The Members para email: {email}")
                user_data_fetched, subscription_data_fetched = await get_user_by_email(email)
                
                if not user_data_fetched:
                    logger.warning(f"[RESOLVE_ACCESS_LINK] Usuário não encontrado na The Members para email: {email}")
                    user_fetch_failed = True
                else:
                    if not user_data:
                        user_data = user_data_fetched
                    if not subscription_data:
                        subscription_data = subscription_data_fetched
                    
                    if not user_id:
                        user_id = user_data.get("id") if isinstance(user_data, dict) else None
            else:
                # Tokens não configurados, não tenta buscar usuário
                logger.info(f"[RESOLVE_ACCESS_LINK] Tokens não configurados, pulando busca de usuário")
                user_fetch_failed = True
        
        # Se não tem user_id mas temos transaction_key, pula estratégias A/B e vai direto para fallback
        if not user_id and transaction_key:
            logger.info(f"[RESOLVE_ACCESS_LINK] User ID não disponível, mas temos transaction_key. Pulando estratégias A/B e indo para fallback...")
            user_fetch_failed = True
        
        # Só tenta estratégias A/B se temos user_id
        if not user_fetch_failed and user_id:
            logger.info(f"[RESOLVE_ACCESS_LINK] User ID: {user_id}")
            
            # ========== ESTRATÉGIA 2: Link direto retornado pela API (se for link de login) ==========
        strategy_used = "A"
        logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Buscando link direto na resposta da API...")
        
        # Campos possíveis para link de acesso
        possible_fields = [
            "first_access_url",
            "firstAccessUrl",
            "first_access_link",
            "access_link",
            "access_url",
            "registration_url",
            "registrationUrl",
            "login_link",
            "login_url",
            "link",
            "url",
        ]
        
        # Tenta na subscription primeiro
        if subscription_data:
            subscription_list = []
            if isinstance(subscription_data, list):
                subscription_list = subscription_data
            elif isinstance(subscription_data, dict):
                subscription_list = [subscription_data]
            
            for sub in subscription_list:
                if isinstance(sub, dict):
                    for field in possible_fields:
                        link_candidate = sub.get(field)
                        if link_candidate and isinstance(link_candidate, str) and link_candidate.startswith("http"):
                            logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Link encontrado na subscription (campo: {field}): {link_candidate[:50]}...")
                            link_found = link_candidate
                            break
                    if link_found:
                        break
        
        # Tenta no user
        if not link_found and user_data:
            if isinstance(user_data, dict):
                for field in possible_fields:
                    link_candidate = user_data.get(field)
                    if link_candidate and isinstance(link_candidate, str) and link_candidate.startswith("http"):
                        logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Link encontrado no user (campo: {field}): {link_candidate[:50]}...")
                        link_found = link_candidate
                        break
        
        # Valida link encontrado na estratégia A
        if link_found:
            is_valid, status, error = await validate_link_exists(link_found, follow_redirects=True)
            if is_valid:
                link_type = _classify_access_link(link_found)
                logger.info(f"[RESOLVE_ACCESS_LINK] ✅ [Estratégia {strategy_used}] Link válido (status {status}, link_type={link_type}): {link_found[:50]}...")
                return link_found
            else:
                logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ [Estratégia {strategy_used}] Link inválido (status {status}): {link_found[:50]}...")
                link_found = None
        
        # ========== ESTRATÉGIA B: Tenta chamar endpoint que gera o link ==========
        strategy_used = "B"
        logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Tentando chamar endpoint para gerar link...")
        
        # Validação de tokens (obrigatórios via ENV) - já verificamos antes, mas double-check
        if not _has_magiclink_tokens():
            logger.warning(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Tokens não configurados, pulando estratégia B")
        else:
            # Endpoints possíveis para gerar link de primeiro acesso
            possible_endpoints = [
                f"/users/{user_id}/first-access",
                f"/users/{user_id}/first-access-link",
                f"/users/{user_id}/generate-first-access",
                f"/users/{user_id}/access-link",
                f"/users/{user_id}/registration-link",
            ]
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                for endpoint_path in possible_endpoints:
                    try:
                        url = f"{THEMEMBERS_BASE_URL}{endpoint_path}/{THEMEMBERS_DEV_TOKEN}/{THEMEMBERS_PLATFORM_TOKEN}"
                        logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Tentando endpoint: {endpoint_path}")
                        
                        # Tenta GET primeiro
                        resp = await client.get(url)
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            
                            # Procura link na resposta
                            if isinstance(data, dict):
                                for field in possible_fields:
                                    link_candidate = data.get(field)
                                    if link_candidate and isinstance(link_candidate, str) and link_candidate.startswith("http"):
                                        logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Link gerado via endpoint (campo: {field}): {link_candidate[:50]}...")
                                        link_found = link_candidate
                                        break
                                
                                # Se não encontrou em campos conhecidos, tenta valores diretos
                                if not link_found:
                                    for key, value in data.items():
                                        if isinstance(value, str) and value.startswith("http") and ("access" in key.lower() or "link" in key.lower() or "url" in key.lower()):
                                            logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Link encontrado em campo dinâmico ({key}): {value[:50]}...")
                                            link_found = value
                                            break
                            
                            if link_found:
                                is_valid, status, error = await validate_link_exists(link_found, follow_redirects=True)
                                if is_valid:
                                    link_type = _classify_access_link(link_found)
                                    logger.info(f"[RESOLVE_ACCESS_LINK] ✅ [Estratégia {strategy_used}] Link válido (status {status}, link_type={link_type}): {link_found[:50]}...")
                                    return link_found
                                else:
                                    logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ [Estratégia {strategy_used}] Link inválido (status {status}): {link_found[:50]}...")
                                    link_found = None
                        
                        elif resp.status_code == 404:
                            logger.debug(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Endpoint não encontrado: {endpoint_path}")
                            continue
                        else:
                            logger.debug(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Endpoint retornou {resp.status_code}: {endpoint_path}")
                            continue
                            
                    except httpx.HTTPStatusError as e:
                        logger.debug(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Erro HTTP {e.response.status_code} em {endpoint_path}")
                        continue
                    except Exception as e:
                        logger.debug(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Erro ao chamar {endpoint_path}: {str(e)}")
                        continue
        
        # ========== ESTRATÉGIA GMAIL: Buscar link no Gmail (fallback quando API indisponível) ==========
        strategy_used = "GMAIL_FALLBACK"
        logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Tentando buscar link de login mágico no Gmail...")
        
        try:
            from ..services.gmail_magiclink_service import get_magic_link_from_gmail
            
            gmail_result = await get_magic_link_from_gmail(email)
            if gmail_result and gmail_result.get("url"):
                gmail_link = gmail_result["url"]
                logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Link encontrado no Gmail: {gmail_link[:50]}...")
                
                # Valida o link encontrado
                is_valid, status, error = await validate_link_exists(gmail_link, follow_redirects=True)
                if is_valid:
                    link_type = _classify_access_link(gmail_link)
                    logger.info(f"[RESOLVE_ACCESS_LINK] ✅ [Estratégia {strategy_used}] Link válido (status {status}, link_type={link_type}, source=gmail): {gmail_link[:50]}...")
                    return gmail_link
                else:
                    logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ [Estratégia {strategy_used}] Link do Gmail inválido (status {status}): {gmail_link[:50]}...")
            else:
                logger.debug(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Link não encontrado no Gmail")
        except Exception as e:
            # Erro no Gmail não deve quebrar o fluxo
            logger.warning(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Erro ao buscar no Gmail (seguindo para fallback): {str(e)}")
        
        # ========== ESTRATÉGIA ÚLTIMA: compra-concluida/?transactionkey=... (FALLBACK) ==========
        strategy_used = "FALLBACK_COMPRA_CONCLUIDA"
        logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Tentando fallback compra-concluida (não é link de primeiro acesso ideal)...")
        
        custom_domain = os.getenv("THEMEMBERS_CUSTOM_DOMAIN") or os.getenv("PURCHASE_SUCCESS_DOMAIN")
        if custom_domain and transaction_key:
            # Remove protocolo se presente
            if custom_domain.startswith("http://") or custom_domain.startswith("https://"):
                base_domain = custom_domain.rstrip('/')
            else:
                base_domain = f"https://{custom_domain.rstrip('/')}"
            
            # Formato compra-concluida (fallback)
            fallback_link = f"{base_domain}/compra-concluida/?transactionkey={transaction_key}"
            
            logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Testando fallback: {fallback_link[:80]}...")
            is_valid, status, error = await validate_link_exists(fallback_link, follow_redirects=True)
            if is_valid:
                link_type = _classify_access_link(fallback_link)
                logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ [Estratégia {strategy_used}] Fallback usado: não é link de primeiro acesso ideal (status {status}, link_type={link_type}): {fallback_link[:50]}...")
                logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ Link retornado é 'compra-concluida', não 'login-magico'. Cliente deve receber acesso por e-mail.")
                return fallback_link
            else:
                logger.debug(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Fallback inválido (status {status}): {fallback_link[:50]}...")
        
        # Verifica se há fallback genérico configurado via ENV
        fallback_link = os.getenv("POST_PURCHASE_ACCESS_LINK")
        if fallback_link and fallback_link.startswith("http"):
            logger.info(f"[RESOLVE_ACCESS_LINK] [Estratégia {strategy_used}] Fallback genérico encontrado: {fallback_link[:50]}...")
            is_valid, status, error = await validate_link_exists(fallback_link, follow_redirects=True)
            if is_valid:
                link_type = _classify_access_link(fallback_link)
                logger.warning(f"[RESOLVE_ACCESS_LINK] ⚠️ [Estratégia {strategy_used}] Fallback genérico usado (status {status}, link_type={link_type}): {fallback_link[:50]}...")
                return fallback_link
        
        # Se chegou aqui, nenhuma estratégia funcionou
        logger.warning(f"[RESOLVE_ACCESS_LINK] ❌ Não foi possível gerar link de primeiro acesso válido para {email}")
        logger.info(f"[RESOLVE_ACCESS_LINK] Estratégias tentadas: MAGIC-LINK (JWT), A (busca direta), B (endpoint), FALLBACK_COMPRA_CONCLUIDA")
        return None
        
    except Exception as e:
        logger.error(f"[RESOLVE_ACCESS_LINK] ❌ Erro ao resolver link de acesso: {str(e)}", exc_info=True)
        return None



