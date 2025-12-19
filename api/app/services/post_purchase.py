# app/services/post_purchase.py
"""
Serviço de pós-compra automático.
Dispara mensagem de boas-vindas após confirmação de venda via webhook Eduzz.
"""
import os
import logging
import asyncio
from typing import Optional
from sqlalchemy.orm import Session

from ..models import Contact, Thread, SaleEvent
from ..providers.twilio import send_text as twilio_send_text, is_configured as twilio_is_configured
from ..providers import meta as meta_provider

logger = logging.getLogger(__name__)

# Mapeamento de product_id da Eduzz para tipo de plano
# IDs reais dos produtos na Eduzz (confirmados em 04/12/2025):
EDUZZ_PRODUCT_MAPPING = {
    # Mensal: ACESSO MENSAL - LIFE 2025
    "2457307": "mensal",
    os.getenv("EDUZZ_PRODUCT_MENSAL_ID", "2457307"): "mensal",
    # Anual: LIFE ACESSO ANUAL - 2 ANOS
    "2562423": "anual",
    os.getenv("EDUZZ_PRODUCT_ANUAL_ID", "2562423"): "anual",
    # Fallback: identificar por valor (em centavos)
    # Mensal: R$ 69,90 = 6990 centavos
    # Anual: R$ 598,80 = 59880 centavos ou 12x de R$ 49,90 = 4990 centavos por parcela
}

# Valores aproximados para identificar plano por valor (em centavos)
PLANO_MENSAL_VALUE = 6990  # R$ 69,90
PLANO_ANUAL_VALUE = 59880  # R$ 598,80 (à vista)
PLANO_ANUAL_PARCELA = 4990  # R$ 49,90 (parcela)


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normaliza telefone para formato E.164 (ex: +5561999999999).
    
    Args:
        phone: Telefone em qualquer formato
    
    Returns:
        Telefone normalizado em E.164 ou None se inválido
    """
    if not phone:
        return None
    
    # Remove prefixos comuns
    normalized = str(phone).strip()
    normalized = normalized.replace("whatsapp:", "").replace("wa.me/", "")
    normalized = normalized.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Adiciona + se não tiver
    if normalized and not normalized.startswith("+"):
        # Se começa com 55 (Brasil), adiciona +
        if normalized.startswith("55") and len(normalized) >= 12:
            normalized = "+" + normalized
        # Se começa com 0, remove e adiciona +55
        elif normalized.startswith("0"):
            normalized = "+55" + normalized[1:]
        # Se tem 10-11 dígitos, assume Brasil e adiciona +55
        elif len(normalized) >= 10 and len(normalized) <= 11:
            normalized = "+55" + normalized
        else:
            normalized = "+" + normalized
    
    return normalized if normalized else None


def find_thread_by_phone(db: Session, phone: str) -> Optional[Thread]:
    """
    Busca thread por telefone normalizado.
    
    Args:
        db: Sessão do banco de dados
        phone: Telefone em qualquer formato
    
    Returns:
        Thread encontrada ou None
    """
    from ..models import Thread
    
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return None
    
    # Busca todas as threads com telefone
    threads = db.query(Thread).filter(Thread.external_user_phone.isnot(None)).all()
    
    for thread in threads:
        thread_phone_normalized = normalize_phone(thread.external_user_phone)
        if thread_phone_normalized == normalized_phone:
            logger.info(f"[FIND_THREAD] ✅ Thread encontrada: ID={thread.id}, Phone={thread.external_user_phone}")
            return thread
    
    logger.info(f"[FIND_THREAD] ⚠️ Nenhuma thread encontrada com telefone {normalized_phone}")
    return None


async def get_first_access_link_async(
    email: str,
    phone: Optional[str] = None,
    db_session: Optional[Session] = None
) -> Optional[str]:
    """
    Busca ou gera link de primeiro acesso personalizado da The Members (versão async).
    
    Usa resolve_first_access_link() que implementa estratégia A/B/C:
    - A: Busca link direto na resposta da API
    - B: Tenta chamar endpoint que gera o link
    - C: Valida fallback antes de usar
    
    Args:
        email: Email do usuário
        phone: Telefone (opcional, para busca alternativa)
        db_session: Sessão do banco (opcional, para buscar contato existente)
    
    Returns:
        Link de acesso personalizado válido ou None se não conseguir gerar
    """
    try:
        from ..services.themembers_service import resolve_first_access_link, get_user_by_email
        
        # Busca usuário na The Members para obter dados completos
        themembers_user, themembers_subscription = await get_user_by_email(email)
        
        if not themembers_user:
            logger.warning(f"[GET_ACCESS_LINK] Usuário não encontrado na The Members para email: {email}")
            return None
        
        # Usa resolve_first_access_link que implementa todas as estratégias
        access_link = await resolve_first_access_link(
            email=email,
            user_id=themembers_user.get("id") if isinstance(themembers_user, dict) else None,
            subscription_data=themembers_subscription,
            user_data=themembers_user,
        )
        
        if access_link:
            logger.info(f"[GET_ACCESS_LINK] ✅ Link de acesso gerado para {email}: {access_link[:50]}...")
        else:
            logger.warning(f"[GET_ACCESS_LINK] ⚠️ Não foi possível gerar link de acesso válido para {email}")
        
        return access_link
        
    except Exception as e:
        logger.error(f"[GET_ACCESS_LINK] ❌ Erro ao buscar link de acesso: {str(e)}", exc_info=True)
        return None


def identify_plan_type(product_id: Optional[str], value: Optional[int]) -> str:
    """
    Identifica o tipo de plano (mensal/anual) baseado no product_id ou valor.
    
    Args:
        product_id: ID do produto na Eduzz
        value: Valor da compra em centavos
    
    Returns:
        "mensal" ou "anual"
    """
    # Tenta identificar por product_id primeiro
    if product_id and product_id in EDUZZ_PRODUCT_MAPPING:
        return EDUZZ_PRODUCT_MAPPING[product_id]
    
    # Se não encontrou, tenta identificar por valor
    if value:
        # Anual: valor total alto OU parcela de ~R$ 49,90
        if value >= PLANO_ANUAL_VALUE or value == PLANO_ANUAL_PARCELA:
            return "anual"
        # Mensal: valor de ~R$ 69,90
        elif value == PLANO_MENSAL_VALUE or (PLANO_MENSAL_VALUE - 100 <= value <= PLANO_MENSAL_VALUE + 100):
            return "mensal"
    
    # Fallback: assume mensal se não conseguir identificar
    logger.warning(f"[POST_PURCHASE] Não foi possível identificar tipo de plano. product_id={product_id}, value={value}. Assumindo 'mensal'.")
    return "mensal"


def get_post_purchase_message(
    contact_name: Optional[str] = None, 
    plan_type: str = "mensal",
    access_link: Optional[str] = None
) -> str:
    """
    Gera a mensagem de pós-compra personalizada.
    
    Args:
        contact_name: Nome do contato (opcional)
        plan_type: Tipo de plano ("mensal" ou "anual")
        access_link: Link personalizado de acesso da The Members (gerado automaticamente para cada usuário)
                    Se None, a mensagem será enviada sem link (instruindo a verificar email)
    
    Returns:
        Mensagem formatada
    """
    nome = contact_name or "gatinha"
    
    # Verifica se o link é realmente um link de primeiro acesso (login-magico) ou apenas fallback (compra-concluida)
    is_login_magic_link = False
    if access_link:
        login_magic_path = os.getenv("THEMEMBERS_LOGIN_MAGIC_PATH", "/login-magico").strip('/')
        is_login_magic_link = f"/{login_magic_path}/" in access_link or access_link.endswith(f"/{login_magic_path}")
    
    # Constrói mensagem com ou sem link de primeiro acesso
    if access_link and is_login_magic_link:
        # Mensagem COM link de primeiro acesso REAL (login-magico)
        mensagem = f"""*AGORA VOCÊ FAZ PARTE DO LIFE!! Vamos nessa juntas 🩷*

{nome}, acessos enviados para o seu e-mail gatinha, confere porque pode ter caído no spam, mas só pra garantir que tá tudo certinho, aqui estão os links essenciais pra você aproveitar tudo do LIFE:

📲 Baixa o app do LIFE e tenha acesso a todos os conteúdos:

Android: https://play.google.com/store/apps/details?id=com.lifeversao.mobile&pli=1

iPhone: https://apps.apple.com/us/app/life-sua-melhor-vers%C3%A3o/id6535646977

📢 Nosso grupo de avisos no WhatsApp (entra lá pra ficar por dentro de tudo! 🚀)

👉 https://chat.whatsapp.com/CMXnSC6BuDuDiBfeEWWiMt

Link de primeiro acesso (Disponível por apenas 24h): 

{access_link}

💬 Dúvidas sobre treinos, dieta, ajustes na alimentação e tudo que envolve sua rotina no LIFE: Falar com suporte

👉 https://wa.link/f6fqv4

💻 Questões técnicas (pagamento, planos, acesso, etc.): Falar com suporte técnico

👉 https://wa.me/message/NNSPXOMMJ3YJB1

Se já pegou tudo, só seguir firme! Mas se tava faltando alguma coisa, agora tá tudo aí! 😘💖

Bora seguir focada? 🚀🔥"""
    elif access_link and not is_login_magic_link:
        # Mensagem COM link mas NÃO é login-magico (é fallback compra-concluida)
        logger.warning(f"[POST_PURCHASE] Link fornecido não é login-magico (é fallback): {access_link[:50]}...")
        mensagem = f"""*AGORA VOCÊ FAZ PARTE DO LIFE!! Vamos nessa juntas 🩷*

{nome}, acessos enviados para o seu e-mail gatinha, confere porque pode ter caído no spam, mas só pra garantir que tá tudo certinho, aqui estão os links essenciais pra você aproveitar tudo do LIFE:

📲 Baixa o app do LIFE e tenha acesso a todos os conteúdos:

Android: https://play.google.com/store/apps/details?id=com.lifeversao.mobile&pli=1

iPhone: https://apps.apple.com/us/app/life-sua-melhor-vers%C3%A3o/id6535646977

📢 Nosso grupo de avisos no WhatsApp (entra lá pra ficar por dentro de tudo! 🚀)

👉 https://chat.whatsapp.com/CMXnSC6BuDuDiBfeEWWiMt

🔗 Seu acesso será liberado por e-mail/área de membros. Confere sua caixa de entrada (pode ter caído no spam)!

👉 Link de apoio: {access_link}

💬 Dúvidas sobre treinos, dieta, ajustes na alimentação e tudo que envolve sua rotina no LIFE: Falar com suporte

👉 https://wa.link/f6fqv4

💻 Questões técnicas (pagamento, planos, acesso, etc.): Falar com suporte técnico

👉 https://wa.me/message/NNSPXOMMJ3YJB1

Se já pegou tudo, só seguir firme! Mas se tava faltando alguma coisa, agora tá tudo aí! 😘💖

Bora seguir focada? 🚀🔥"""
    else:
        # Mensagem SEM link (instruindo verificar email)
        logger.info(f"[POST_PURCHASE] Link de acesso não disponível. Mensagem será enviada sem link (instruindo verificar email)")
        mensagem = f"""*AGORA VOCÊ FAZ PARTE DO LIFE!! Vamos nessa juntas 🩷*

{nome}, acessos enviados para o seu e-mail gatinha, confere porque pode ter caído no spam, mas só pra garantir que tá tudo certinho, aqui estão os links essenciais pra você aproveitar tudo do LIFE:

📲 Baixa o app do LIFE e tenha acesso a todos os conteúdos:

Android: https://play.google.com/store/apps/details?id=com.lifeversao.mobile&pli=1

iPhone: https://apps.apple.com/us/app/life-sua-melhor-vers%C3%A3o/id6535646977

📢 Nosso grupo de avisos no WhatsApp (entra lá pra ficar por dentro de tudo! 🚀)

👉 https://chat.whatsapp.com/CMXnSC6BuDuDiBfeEWWiMt

🔗 Link de primeiro acesso: Confere seu e-mail que enviamos o link personalizado pra você!

💬 Dúvidas sobre treinos, dieta, ajustes na alimentação e tudo que envolve sua rotina no LIFE: Falar com suporte

👉 https://wa.link/f6fqv4

💻 Questões técnicas (pagamento, planos, acesso, etc.): Falar com suporte técnico

👉 https://wa.me/message/NNSPXOMMJ3YJB1

Se já pegou tudo, só seguir firme! Mas se tava faltando alguma coisa, agora tá tudo aí! 😘💖

Bora seguir focada? 🚀🔥"""
    
    return mensagem


def send_post_purchase_message(
    db: Session,
    contact: Contact,
    sale_event: SaleEvent,
    plan_type: str,
    access_link: Optional[str] = None,
) -> bool:
    """
    Envia mensagem de pós-compra via WhatsApp.
    
    A thread já deve estar vinculada ao contato antes de chamar esta função.
    Se não tiver thread_id, a função retorna False (thread deve ser criada antes).
    
    Args:
        db: Sessão do banco de dados
        contact: Contato que fechou a compra
        sale_event: Evento de venda
        plan_type: Tipo de plano ("mensal" ou "anual")
        access_link: Link personalizado de acesso (opcional)
    
    Returns:
        True se a mensagem foi enviada, False caso contrário
    """
    try:
        # Verifica se contato tem thread vinculada
        if not contact.thread_id:
            logger.warning(f"[POST_PURCHASE] Contato {contact.id} não tem thread vinculada. Mensagem não será enviada.")
            return False
        
        thread = db.query(Thread).filter(Thread.id == contact.thread_id).first()
        if not thread:
            logger.warning(f"[POST_PURCHASE] Thread {contact.thread_id} não encontrada para contato {contact.id}.")
            return False
        
        # Verifica se tem telefone na thread
        if not thread.external_user_phone:
            logger.warning(f"[POST_PURCHASE] Thread {thread.id} não tem telefone vinculado.")
            return False
        
        # Log do link recebido com classificação
        if access_link:
            from ..services.themembers_service import _classify_access_link
            link_type = _classify_access_link(access_link)
            logger.info(f"[POST_PURCHASE] Link de acesso recebido (link_type={link_type}): {access_link[:50]}...")
        else:
            logger.info(f"[POST_PURCHASE] Link de acesso não disponível")
        
        # Gera mensagem personalizada
        mensagem = get_post_purchase_message(
            contact_name=contact.name,
            plan_type=plan_type,
            access_link=access_link
        )
        
        # Log da mensagem gerada (primeiros 500 chars)
        logger.info(f"[POST_PURCHASE] Mensagem gerada (primeiros 500 chars): {mensagem[:500]}")
        
        # Escolhe o provider: Twilio se habilitado e configurado, senão Meta
        enable_twilio = os.getenv("ENABLE_TWILIO", "true").lower() == "true"
        use_twilio = enable_twilio and twilio_is_configured()
        
        # Verifica se Meta está configurado
        meta_access_token = os.getenv("META_ACCESS_TOKEN")
        meta_phone_number_id = os.getenv("META_PHONE_NUMBER_ID")
        meta_configured = bool(meta_access_token and meta_phone_number_id)
        
        if not use_twilio and not meta_configured:
            logger.error(f"[POST_PURCHASE] ❌ Nenhum provider configurado! Twilio desabilitado e Meta sem credenciais.")
            logger.error(f"[POST_PURCHASE] Configure ENABLE_TWILIO=true ou forneça META_ACCESS_TOKEN e META_PHONE_NUMBER_ID")
            return False
        
        logger.info(f"[POST_PURCHASE] Enviando mensagem pós-compra para thread {thread.id} (contato {contact.id}, plano {plan_type}) via {'Twilio' if use_twilio else 'Meta'}")
        
        if use_twilio:
            # Usa Twilio (síncrono)
            result = twilio_send_text(
                to_e164=thread.external_user_phone,
                body=mensagem,
                sender="BOT"
            )
            if not result:
                logger.warning(f"[POST_PURCHASE] Twilio retornou vazio, tentando Meta como fallback")
                use_twilio = False
        
        if not use_twilio:
            if not meta_configured:
                logger.error(f"[POST_PURCHASE] ❌ Meta não está configurado. Não é possível enviar mensagem.")
                return False
            
            # Usa Meta (assíncrono)
            try:
                # Remove o prefixo "whatsapp:" se existir para Meta
                phone = thread.external_user_phone
                if phone.startswith("whatsapp:"):
                    phone = phone.replace("whatsapp:", "")
                elif not phone.startswith("+"):
                    phone = f"+{phone}"
                
                # Executa a função assíncrona de forma segura
                try:
                    # Tenta obter o loop atual
                    loop = asyncio.get_running_loop()
                    # Se chegou aqui, há um loop rodando - usa ThreadPoolExecutor
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, meta_provider.send_text(phone, mensagem))
                        result = future.result(timeout=30)
                except RuntimeError:
                    # Não há loop rodando, pode usar asyncio.run diretamente
                    result = asyncio.run(meta_provider.send_text(phone, mensagem))
                
                logger.info(f"[POST_PURCHASE] ✅ Mensagem enviada via Meta: {result}")
            except Exception as meta_error:
                logger.error(f"[POST_PURCHASE] ❌ Erro ao enviar via Meta: {str(meta_error)}")
                raise
        
        logger.info(f"[POST_PURCHASE] ✅ Mensagem pós-compra enviada com sucesso para contato {contact.id}")
        return True
        
    except Exception as e:
        logger.error(f"[POST_PURCHASE] ❌ Erro ao enviar mensagem pós-compra: {str(e)}", exc_info=True)
        return False

