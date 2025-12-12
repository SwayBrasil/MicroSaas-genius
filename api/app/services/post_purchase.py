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
        access_link: Link personalizado de acesso da The Members (opcional)
    
    Returns:
        Mensagem formatada
    """
    nome = contact_name or "gatinha"
    
    # Usa link personalizado se fornecido, senão usa placeholder
    link_personalizado = access_link or "[LINK PERSONALIZADO]"
    
    mensagem = f"""*AGORA VOCÊ FAZ PARTE DO LIFE!! Vamos nessa juntas 🩷*

{nome}, acessos enviados para o seu e-mail, gatinha. Confere porque pode ter caído no spam, mas só pra garantir que tá tudo certinho, aqui estão os links essenciais pra você aproveitar tudo do LIFE:

📲 Baixa o app do LIFE e tenha acesso a todos os conteúdos:

Android: https://play.google.com/store/apps/details?id=com.lifeversao.mobile&pli=1

iPhone: https://apps.apple.com/us/app/life-sua-melhor-vers%C3%A3o/id6535646977

📢 Nosso grupo de avisos no WhatsApp (entra lá pra ficar por dentro de tudo! 🚀)

👉 https://chat.whatsapp.com/CMXnSC6BuDuDiBfeEWWiMt

Link de primeiro acesso (Disponível por apenas 24h):

{link_personalizado}

💬 Dúvidas sobre treinos, dieta, ajustes na alimentação e tudo que envolve sua rotina no LIFE: falar com suporte

👉 https://wa.link/f6fqv4

💻 Questões técnicas (pagamento, planos, acesso, etc.): falar com suporte técnico

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
    Envia mensagem de pós-compra via WhatsApp se o contato tiver uma thread ativa.
    
    Args:
        db: Sessão do banco de dados
        contact: Contato que fechou a compra
        sale_event: Evento de venda
        plan_type: Tipo de plano ("mensal" ou "anual")
    
    Returns:
        True se a mensagem foi enviada, False caso contrário
    """
    try:
        # Busca thread do contato
        if not contact.thread_id:
            logger.info(f"[POST_PURCHASE] Contato {contact.id} não tem thread vinculada. Mensagem não será enviada.")
            return False
        
        thread = db.query(Thread).filter(Thread.id == contact.thread_id).first()
        if not thread:
            logger.warning(f"[POST_PURCHASE] Thread {contact.thread_id} não encontrada para contato {contact.id}.")
            return False
        
        # Verifica se tem telefone
        if not thread.external_user_phone:
            logger.warning(f"[POST_PURCHASE] Thread {thread.id} não tem telefone vinculado.")
            return False
        
        # Gera mensagem personalizada
        mensagem = get_post_purchase_message(
            contact_name=contact.name,
            plan_type=plan_type,
            access_link=access_link
        )
        
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

