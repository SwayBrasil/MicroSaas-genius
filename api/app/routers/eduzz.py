# app/routers/eduzz.py
import os
import hmac
import hashlib
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..db import get_db
from ..models import Contact, SaleEvent, SubscriptionExternal, ProductExternal, CartEvent
from ..services.themembers_service import (
    get_user_by_email,
    create_user_with_product,
)
from ..services.post_purchase import (
    identify_plan_type,
    send_post_purchase_message,
)

router = APIRouter(prefix="/webhook", tags=["webhooks"])

# 🔐 Segredo do Eduzz (da tela de Segurança)
EDUZZ_SECRET = os.getenv("EDUZZ_SECRET", "edzwgp_3eg5UCwaCxwoiFCn07FoIVGcxFFMHk7pCXYwvIyyIqwUl4lri")


def verify_eduzz_signature(body: bytes, signature: str | None):
    """
    Valida o x-signature enviado pela Eduzz usando HMAC-SHA256.
    """
    if not signature:
        raise HTTPException(status_code=400, detail="Missing x-signature header")

    expected = hmac.new(
        EDUZZ_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    # Usa compare_digest pra evitar timing attack
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")




@router.post("/eduzz")
async def webhook_eduzz(
    request: Request,
    x_signature: str | None = Header(default=None, alias="x-signature"),
    db: Session = Depends(get_db),
):
    """
    Webhook para receber eventos da Eduzz.
    
    Valida a assinatura HMAC-SHA256 e processa eventos de venda aprovada,
    criando usuários na The Members quando necessário e relacionando com contatos.
    """
    # 1) Lê body cru e valida assinatura
    raw_body = await request.body()
    verify_eduzz_signature(raw_body, x_signature)

    # 2) Converte para JSON
    payload = await request.json()

    event = payload.get("event")
    buyer_email = payload.get("buyer_email")
    product_id = payload.get("product_id")  # ID do produto na Eduzz
    order_id = payload.get("order_id")
    event_id = payload.get("event_id")
    timestamp = payload.get("timestamp")
    value = payload.get("value")  # em centavos

    # 3) Processa eventos de abandonment (carrinho abandonado)
    if event == "cart.abandonment" or event == "abandonment":
        if not buyer_email:
            raise HTTPException(status_code=400, detail="buyer_email is required for abandonment events")
        
        # Busca contato
        contact = db.query(Contact).filter(Contact.email == buyer_email).first()
        
        # Cria evento de carrinho abandonado
        cart_event = CartEvent(
            source="eduzz",
            event_type="abandonment",
            email=buyer_email,
            cart_id=order_id or payload.get("cart_id"),
            product_id=product_id,
            value=value,
            contact_id=contact.id if contact else None,
            raw_data=payload,
        )
        db.add(cart_event)
        db.commit()
        
        return {
            "status": "ok",
            "action": "abandonment_recorded",
            "cart_event_id": cart_event.id,
        }
    
    # 4) Identifica tipo de plano ANTES de criar o SaleEvent (para sale.approved)
    plan_type = None
    if event == "sale.approved" and buyer_email:
        plan_type = identify_plan_type(product_id, value)
    
    # 5) Salva o evento de venda (independente do tipo de evento)
    sale_event = SaleEvent(
        source="eduzz",
        event=event,
        event_id=event_id,
        order_id=order_id,
        buyer_email=buyer_email or "",
        buyer_name=payload.get("buyer_name"),
        value=value,
        product_id=product_id,
        plan_type=plan_type,
        raw_payload=payload,
    )

    # Loga todos os eventos para debug (incluindo diferentes status de fatura)
    invoice_status = payload.get("invoice_status") or payload.get("status")
    if invoice_status:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[EDUZZ_WEBHOOK] Evento recebido: {event}, Status fatura: {invoice_status}, Email: {buyer_email}, Product: {product_id}")
    
    if event != "sale.approved":
        # Salva evento mas não processa criação de usuário
        # Nota: Eventos como "invoice.created", "invoice.paid" podem vir separados
        # Atualmente só processamos "sale.approved" que indica venda confirmada
        db.add(sale_event)
        db.commit()
        return {
            "status": "ignored",
            "reason": "event not handled",
            "event": event,
            "invoice_status": invoice_status,
            "note": "Apenas eventos 'sale.approved' são processados para criação de usuário"
        }

    if not buyer_email:
        raise HTTPException(status_code=400, detail="buyer_email is required")

    # 6) Verifica se há carrinho abandonado para recuperar
    if buyer_email:
        abandoned_cart = (
            db.query(CartEvent)
            .filter(
                CartEvent.email == buyer_email,
                CartEvent.event_type == "abandonment",
                CartEvent.recovered == False
            )
            .order_by(CartEvent.created_at.desc())
            .first()
        )
        
        if abandoned_cart:
            # Marca como recuperado
            abandoned_cart.recovered = True
            abandoned_cart.recovered_at = datetime.now()
            abandoned_cart.order_id = order_id
            db.add(abandoned_cart)
            
            # Também cria evento de carrinho recuperado
            recovery_cart_event = CartEvent(
                source="eduzz",
                event_type="sale",
                email=buyer_email,
                cart_id=abandoned_cart.cart_id,
                order_id=order_id,
                product_id=product_id,
                value=value,
                contact_id=abandoned_cart.contact_id,
                recovered=True,
                recovered_at=datetime.now(),
                raw_data=payload,
            )
            db.add(recovery_cart_event)

    # 6) Busca contato no banco pelo email
    contact = db.query(Contact).filter(Contact.email == buyer_email).first()
    
    # Se não encontrou por email, tenta buscar por themembers_user_id (caso já tenha sido criado antes)
    if not contact:
        # Vai buscar na The Members primeiro para ver se já existe
        themembers_user, _ = await get_user_by_email(buyer_email)
        if themembers_user:
            themembers_user_id = str(themembers_user.get("id", ""))
            contact = db.query(Contact).filter(Contact.themembers_user_id == themembers_user_id).first()

    # 7) Regra de mapeamento de produto
    themembers_product_id = os.getenv("THEMEMBERS_DEFAULT_PRODUCT_ID", "2352153")
    # TODO: Implementar mapeamento product_id (Eduzz) -> product_id (TheMembers)

    # 8) Verifica se usuário já existe na The Members
    themembers_user, themembers_subscription = await get_user_by_email(buyer_email)
    themembers_user_id = None

    if themembers_user:
        themembers_user_id = str(themembers_user.get("id", ""))
        action = "user_already_exists"
    else:
        # 9) Não existe: cria usuário + assinatura
        buyer_name = payload.get("buyer_name", "Aluno")
        buyer_last_name = payload.get("buyer_last_name", "ViaEduzz")
        
        # Se buyer_name vier completo, tenta dividir
        if buyer_name and " " in buyer_name and not buyer_last_name:
            parts = buyer_name.split(" ", 1)
            buyer_name = parts[0]
            buyer_last_name = parts[1] if len(parts) > 1 else "ViaEduzz"
        
        buyer_document = payload.get("buyer_document") or payload.get("document")
        buyer_phone = payload.get("buyer_phone") or payload.get("phone")
        
        accession_date = "2025-01-01"
        if timestamp:
            try:
                accession_date = timestamp.split("T")[0]
            except:
                pass

        created_response = await create_user_with_product(
            email=buyer_email,
            name=buyer_name,
            last_name=buyer_last_name,
            document=buyer_document,
            phone=buyer_phone,
            reference_id=order_id,
            accession_date=accession_date,
            product_id=themembers_product_id,
        )
        
        # Extrai user_id da resposta
        if isinstance(created_response, dict):
            # A resposta pode vir em diferentes formatos
            if "user" in created_response:
                themembers_user_id = str(created_response["user"].get("id", ""))
            elif "users" in created_response and len(created_response["users"]) > 0:
                themembers_user_id = str(created_response["users"][0].get("id", ""))
            elif "id" in created_response:
                themembers_user_id = str(created_response["id"])
        
        # Busca novamente para pegar subscription
        themembers_user, themembers_subscription = await get_user_by_email(buyer_email)
        if themembers_user:
            themembers_user_id = str(themembers_user.get("id", ""))
        
        action = "user_created"

    # 8) Atualiza ou cria contato
    if contact:
        # Atualiza contato existente
        if not contact.email:
            contact.email = buyer_email
        if not contact.themembers_user_id and themembers_user_id:
            contact.themembers_user_id = themembers_user_id
        if not contact.name and payload.get("buyer_name"):
            contact.name = payload.get("buyer_name")
    else:
        # Cria novo contato
        # Busca usuário padrão (Admin) para vincular
        from ..models import User
        default_user = db.query(User).filter(User.email == "Admin").first()
        user_id = default_user.id if default_user else None
        
        contact = Contact(
            email=buyer_email,
            name=payload.get("buyer_name", "Cliente Eduzz"),
            phone=payload.get("buyer_phone") or payload.get("phone"),
            themembers_user_id=themembers_user_id,
            user_id=user_id,  # Vincula ao usuário Admin se existir
            thread_id=None,  # Sem thread (venda direta sem conversa)
        )
        db.add(contact)
    
    db.flush()  # Para ter o ID do contato

    # 9) Atualiza sale_event com contact_id e themembers_user_id
    sale_event.contact_id = contact.id
    sale_event.themembers_user_id = themembers_user_id
    db.add(sale_event)

    # 10) Cria ou atualiza produto da Eduzz no banco (se ainda não existe)
    if product_id:
        eduzz_product = db.query(ProductExternal).filter(
            ProductExternal.external_product_id == product_id,
            ProductExternal.source == "eduzz"
        ).first()
        
        if not eduzz_product:
            # Tenta pegar o nome do produto do payload
            product_title = payload.get("product_name") or payload.get("product_title") or f"Produto Eduzz {product_id}"
            
            eduzz_product = ProductExternal(
                external_product_id=product_id,
                title=product_title,
                status="active",
                source="eduzz",
                raw_data={"product_id": product_id, "eduzz_payload": payload},
            )
            db.add(eduzz_product)
            db.flush()
    
    # 11) Cria ou atualiza subscription_external
    if themembers_user_id and themembers_subscription:
        # Busca produto externo (The Members)
        product_external = db.query(ProductExternal).filter(
            ProductExternal.external_product_id == themembers_product_id,
            ProductExternal.source == "themembers"
        ).first()
        
        # Se não existe, cria (opcional - pode sincronizar depois)
        if not product_external:
            product_external = ProductExternal(
                external_product_id=themembers_product_id,
                title=f"Produto The Members {themembers_product_id}",
                status="active",
                source="themembers",
                raw_data={"product_id": themembers_product_id},
            )
            db.add(product_external)
            db.flush()

        # Busca subscription existente
        subscription = db.query(SubscriptionExternal).filter(
            SubscriptionExternal.themembers_user_id == themembers_user_id,
            SubscriptionExternal.contact_id == contact.id,
        ).first()

        # Extrai dados da subscription da The Members
        subscription_data = themembers_subscription if isinstance(themembers_subscription, dict) else {}
        
        if subscription:
            # Atualiza subscription existente
            subscription.status = subscription_data.get("status", "active")
            subscription.last_payment_at = datetime.now()
            if subscription_data.get("expires_at"):
                try:
                    subscription.expires_at = datetime.fromisoformat(
                        subscription_data["expires_at"].replace("Z", "+00:00")
                    )
                except:
                    pass
            subscription.raw_data = subscription_data
        else:
            # Cria nova subscription
            expires_at = None
            if subscription_data.get("expires_at"):
                try:
                    expires_at = datetime.fromisoformat(
                        subscription_data["expires_at"].replace("Z", "+00:00")
                    )
                except:
                    pass

            subscription = SubscriptionExternal(
                contact_id=contact.id,
                themembers_user_id=themembers_user_id,
                product_external_id=product_external.id if product_external else None,
                status=subscription_data.get("status", "active"),
                started_at=datetime.now(),
                last_payment_at=datetime.now(),
                expires_at=expires_at,
                source="eduzz",
                raw_data=subscription_data,
            )
            db.add(subscription)

    db.commit()
    
    # 12) Busca link de acesso personalizado da The Members (se disponível)
    access_link = None
    if themembers_subscription or themembers_user:
        import logging
        logger = logging.getLogger(__name__)
        
        # Subscription pode ser um array ou um objeto
        subscription_list = []
        if themembers_subscription:
            if isinstance(themembers_subscription, list):
                subscription_list = themembers_subscription
            elif isinstance(themembers_subscription, dict):
                subscription_list = [themembers_subscription]
        
        # Tenta pegar link de acesso da subscription (primeira do array se for array)
        if subscription_list:
            subscription_data = subscription_list[0] if subscription_list else {}
            # Log para debug (apenas em desenvolvimento)
            if os.getenv("ENVIRONMENT") != "production":
                logger.debug(f"[EDUZZ_WEBHOOK] Subscription data keys: {list(subscription_data.keys()) if isinstance(subscription_data, dict) else 'not a dict'}")
            
            # Tenta vários campos possíveis
            access_link = (
                subscription_data.get("access_link") or 
                subscription_data.get("link") or 
                subscription_data.get("access_url") or
                subscription_data.get("first_access_link") or
                subscription_data.get("first_access_url") or
                subscription_data.get("login_link") or
                subscription_data.get("login_url") or
                subscription_data.get("url") or
                subscription_data.get("access") or
                subscription_data.get("course_access_link") or
                subscription_data.get("course_link")
            )
        
        # Se não encontrou na subscription, tenta no user
        if not access_link and themembers_user:
            user_data = themembers_user if isinstance(themembers_user, dict) else {}
            # Log para debug
            if os.getenv("ENVIRONMENT") != "production":
                logger.debug(f"[EDUZZ_WEBHOOK] User data keys: {list(user_data.keys()) if isinstance(user_data, dict) else 'not a dict'}")
            
            access_link = (
                user_data.get("access_link") or 
                user_data.get("link") or 
                user_data.get("access_url") or
                user_data.get("first_access_link") or
                user_data.get("first_access_url") or
                user_data.get("login_link") or
                user_data.get("login_url") or
                user_data.get("url") or
                user_data.get("access") or
                user_data.get("course_access_link") or
                user_data.get("course_link")
            )
        
        # Se ainda não encontrou, tenta construir o link manualmente usando user_id
        if not access_link and themembers_user:
            user_id = themembers_user.get("id") if isinstance(themembers_user, dict) else None
            if user_id:
                base_url = os.getenv("THEMEMBERS_BASE_URL", "https://registration.themembers.dev.br/api").replace("/api", "")
                
                # Formato do link configurável via variável de ambiente
                # Opções: "access/{user_id}", "first-access/{user_id}", "login?user_id={user_id}", etc.
                link_format = os.getenv("THEMEMBERS_ACCESS_LINK_FORMAT", "first-access/{user_id}")
                
                # Substitui {user_id} pelo ID real
                access_link = f"{base_url}/{link_format}".replace("{user_id}", str(user_id))
                
                logger.info(f"[EDUZZ_WEBHOOK] Link de acesso construído: {access_link}")
        
        # Se ainda não encontrou, loga para investigação
        if not access_link:
            logger.info(f"[EDUZZ_WEBHOOK] Link de acesso não encontrado na resposta da The Members. Subscription: {bool(subscription_list)}, User: {bool(themembers_user)}")
    
    # 13) Envia mensagem pós-compra se a venda foi aprovada e contato tem thread
    post_purchase_sent = False
    if event == "sale.approved" and contact and contact.thread_id:
        try:
            post_purchase_sent = send_post_purchase_message(
                db=db,
                contact=contact,
                sale_event=sale_event,
                plan_type=plan_type or "mensal",
                access_link=access_link,
            )
            # Atualiza flag no sale_event
            sale_event.post_purchase_sent = post_purchase_sent
            db.commit()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[EDUZZ_WEBHOOK] Erro ao enviar mensagem pós-compra: {str(e)}", exc_info=True)

    return {
        "status": "ok",
        "action": action,
        "contact_id": contact.id,
        "themembers_user_id": themembers_user_id,
        "subscription_created": themembers_user_id is not None,
        "plan_type": plan_type,
        "post_purchase_sent": post_purchase_sent,
    }


# ==================== ENDPOINT DE TESTE ====================

class TestSaleRequest(BaseModel):
    """Payload para simular uma compra de teste"""
    buyer_email: str
    buyer_name: Optional[str] = None
    buyer_phone: Optional[str] = None
    product_id: Optional[str] = None  # "2457307" (mensal) ou "2562423" (anual)
    value: Optional[int] = None  # em centavos: 6990 (mensal) ou 59880 (anual)
    order_id: Optional[str] = None
    plan_type: Optional[str] = None  # "mensal" ou "anual" (opcional, será detectado automaticamente)


@router.post("/test-sale", tags=["webhooks"])
async def test_sale_webhook(
    body: TestSaleRequest,
    db: Session = Depends(get_db),
):
    """
    Endpoint de TESTE para simular uma compra sem precisar comprar de verdade.
    
    ⚠️ ATENÇÃO: Este endpoint só funciona em ambiente de desenvolvimento/teste.
    Ele simula o webhook da Eduzz sem validar assinatura HMAC.
    
    Exemplo de uso:
    ```bash
    curl -X POST http://localhost:8000/webhook/test-sale \
      -H "Content-Type: application/json" \
      -d '{
        "buyer_email": "teste@exemplo.com",
        "buyer_name": "Maria Silva",
        "buyer_phone": "+5561999999999",
        "product_id": "2457307",
        "value": 6990
      }'
    ```
    """
    # Verifica se está em modo de desenvolvimento
    if os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(
            status_code=403,
            detail="Este endpoint de teste não está disponível em produção"
        )
    
    # Prepara payload simulado do Eduzz
    order_id = body.order_id or f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    product_id = body.product_id or "2457307"  # Default: mensal
    value = body.value or 6990  # Default: R$ 69,90
    
    # Detecta tipo de plano se não foi fornecido
    plan_type = body.plan_type or identify_plan_type(product_id, value)
    
    # Cria payload simulado
    simulated_payload = {
        "event": "sale.approved",
        "event_id": f"TEST-{order_id}",
        "order_id": order_id,
        "buyer_email": body.buyer_email,
        "buyer_name": body.buyer_name or "Cliente Teste",
        "buyer_phone": body.buyer_phone,
        "product_id": product_id,
        "value": value,
        "timestamp": datetime.now().isoformat(),
        "invoice_status": "paid",
        "status": "approved",
    }
    
    # Se forneceu telefone, busca ou cria thread primeiro
    thread = None
    if body.buyer_phone:
        from ..models import Thread
        
        # Função para normalizar telefone (mesma lógica do webhook)
        def _normalize_phone(phone: str) -> str:
            if not phone:
                return ""
            normalized = str(phone).replace("whatsapp:", "").strip()
            normalized = normalized.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if normalized and not normalized.startswith("+"):
                normalized = "+" + normalized
            return normalized
        
        normalized_phone = _normalize_phone(body.buyer_phone)
        
        # Busca thread existente com esse telefone
        threads = db.query(Thread).filter(Thread.external_user_phone.isnot(None)).all()
        for t in threads:
            if _normalize_phone(t.external_user_phone) == normalized_phone:
                thread = t
                break
        
        # Se não encontrou thread, cria uma nova automaticamente
        if not thread:
            from ..models import User
            default_user = db.query(User).filter(User.email == "Admin").first()
            user_id = default_user.id if default_user else None
            
            thread = Thread(
                user_id=user_id,
                title=body.buyer_name or f"WhatsApp {normalized_phone[-4:]}",
                external_user_phone=normalized_phone,
                origin="test",
            )
            db.add(thread)
            db.flush()
            
            # Cria uma mensagem inicial para simular conversa
            from ..models import Message
            initial_message = Message(
                thread_id=thread.id,
                role="user",
                content="Oi, quero saber do LIFE",
            )
            db.add(initial_message)
            db.commit()
            db.refresh(thread)
    
    # Busca contato existente por email OU por thread_id (se thread foi encontrada/criada)
    contact = None
    if thread:
        # Primeiro tenta buscar contato que já está vinculado a essa thread
        contact = db.query(Contact).filter(Contact.thread_id == thread.id).first()
    
    # Se não encontrou por thread, busca por email
    if not contact:
        contact = db.query(Contact).filter(Contact.email == body.buyer_email).first()
    
    # Se ainda não encontrou, cria novo contato
    if not contact:
        from ..models import User
        default_user = db.query(User).filter(User.email == "Admin").first()
        user_id = default_user.id if default_user else None
        
        contact = Contact(
            email=body.buyer_email,
            name=body.buyer_name or "Cliente Teste",
            phone=body.buyer_phone,
            user_id=user_id,
            thread_id=thread.id if thread else None,
        )
        db.add(contact)
        db.flush()
    else:
        # Atualiza contato existente (mas só vincula thread se não tiver uma já)
        if thread and not contact.thread_id:
            # Verifica se já existe outro contato com essa thread
            existing_contact_with_thread = db.query(Contact).filter(Contact.thread_id == thread.id).first()
            if not existing_contact_with_thread:
                contact.thread_id = thread.id
            elif existing_contact_with_thread.id != contact.id:
                # Já existe outro contato com essa thread, não vincula
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"[TEST_SALE] Thread {thread.id} já está vinculada ao contato {existing_contact_with_thread.id}. Não vinculando contato {contact.id}.")
        
        # Atualiza email se não tiver
        if not contact.email:
            contact.email = body.buyer_email
        # Atualiza telefone se não tiver
        if not contact.phone and body.buyer_phone:
            contact.phone = body.buyer_phone
    
    db.commit()
    db.refresh(contact)
    
    # Se não tem thread vinculada, avisa mas continua
    if not contact.thread_id:
        return {
            "status": "warning",
            "message": f"Contato criado/encontrado (ID: {contact.id}), mas não tem thread vinculada. A mensagem pós-compra não será enviada.",
            "contact_id": contact.id,
            "buyer_email": body.buyer_email,
            "note": "Para enviar mensagem pós-compra, forneça um telefone válido. Uma thread será criada automaticamente.",
        }
    
    # Processa como se fosse um webhook real (mas sem validar assinatura)
    # Usa a mesma lógica do webhook real
    try:
        # Identifica tipo de plano
        plan_type = identify_plan_type(product_id, value)
        
        # Cria SaleEvent
        sale_event = SaleEvent(
            source="test",
            event="sale.approved",
            event_id=simulated_payload["event_id"],
            order_id=order_id,
            buyer_email=body.buyer_email,
            buyer_name=body.buyer_name or "Cliente Teste",
            value=value,
            product_id=product_id,
            plan_type=plan_type,
            contact_id=contact.id,
            raw_payload=simulated_payload,
        )
        db.add(sale_event)
        db.flush()
        
        # Tenta criar usuário na The Members (opcional - pode falhar se não configurado)
        themembers_user_id = None
        access_link = None
        try:
            themembers_user, themembers_subscription = await get_user_by_email(body.buyer_email)
            
            if not themembers_user:
                # Tenta criar usuário na The Members
                buyer_name = body.buyer_name or "Cliente"
                buyer_last_name = "Teste"
                if " " in buyer_name:
                    parts = buyer_name.split(" ", 1)
                    buyer_name = parts[0]
                    buyer_last_name = parts[1]
                
                created_response = await create_user_with_product(
                    email=body.buyer_email,
                    name=buyer_name,
                    last_name=buyer_last_name,
                    phone=body.buyer_phone,
                    reference_id=order_id,
                    accession_date=datetime.now().strftime("%Y-%m-%d"),
                    product_id=os.getenv("THEMEMBERS_DEFAULT_PRODUCT_ID", "2352153"),
                )
                
                # Busca novamente para pegar subscription
                themembers_user, themembers_subscription = await get_user_by_email(body.buyer_email)
            
            if themembers_user:
                themembers_user_id = str(themembers_user.get("id", ""))
                contact.themembers_user_id = themembers_user_id
                
                # Busca link de acesso (subscription pode ser array)
                if themembers_subscription:
                    subscription_list = []
                    if isinstance(themembers_subscription, list):
                        subscription_list = themembers_subscription
                    elif isinstance(themembers_subscription, dict):
                        subscription_list = [themembers_subscription]
                    
                    if subscription_list:
                        subscription_data = subscription_list[0]
                        access_link = (
                            subscription_data.get("access_link") or 
                            subscription_data.get("link") or 
                            subscription_data.get("access_url") or
                            subscription_data.get("first_access_link") or
                            subscription_data.get("first_access_url") or
                            subscription_data.get("login_link") or
                            subscription_data.get("login_url")
                        )
                
                # Se não encontrou na subscription, tenta construir o link manualmente usando user_id
                if not access_link and themembers_user:
                    user_id = themembers_user.get("id") if isinstance(themembers_user, dict) else None
                    if user_id:
                        base_url = os.getenv("THEMEMBERS_BASE_URL", "https://registration.themembers.dev.br/api").replace("/api", "")
                        
                        # Formato do link configurável via variável de ambiente
                        link_format = os.getenv("THEMEMBERS_ACCESS_LINK_FORMAT", "first-access/{user_id}")
                        
                        # Substitui {user_id} pelo ID real
                        access_link = f"{base_url}/{link_format}".replace("{user_id}", str(user_id))
                        
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"[TEST_SALE] Link de acesso construído: {access_link}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"[TEST_SALE] Não foi possível criar/buscar usuário na The Members: {str(e)}")
        
        sale_event.themembers_user_id = themembers_user_id
        db.commit()
        
        # Envia mensagem pós-compra
        post_purchase_sent = False
        if contact.thread_id:
            try:
                post_purchase_sent = send_post_purchase_message(
                    db=db,
                    contact=contact,
                    sale_event=sale_event,
                    plan_type=plan_type,
                    access_link=access_link,
                )
                sale_event.post_purchase_sent = post_purchase_sent
                db.commit()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"[TEST_SALE] Erro ao enviar mensagem pós-compra: {str(e)}", exc_info=True)
        
        return {
            "status": "ok",
            "message": "Compra simulada com sucesso!",
            "contact_id": contact.id,
            "thread_id": contact.thread_id,
            "thread_created": thread.id if thread else None,
            "themembers_user_id": themembers_user_id,
            "plan_type": plan_type,
            "post_purchase_sent": post_purchase_sent,
            "access_link": access_link or "[LINK PERSONALIZADO]",
            "order_id": order_id,
            "phone": body.buyer_phone,
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[TEST_SALE] Erro ao processar compra simulada: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar compra simulada: {str(e)}"
        )


@router.get("/debug/themembers/{email}", tags=["webhooks"])
async def debug_themembers_user(
    email: str,
    db: Session = Depends(get_db),
):
    """
    Endpoint de DEBUG para verificar o que a API da The Members retorna.
    Útil para descobrir qual campo contém o link de acesso.
    """
    if os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(
            status_code=403,
            detail="Este endpoint de debug não está disponível em produção"
        )
    
    try:
        user, subscription = await get_user_by_email(email)
        
        # Processa subscription (pode ser array ou objeto)
        subscription_list = []
        subscription_keys = None
        if subscription:
            if isinstance(subscription, list):
                subscription_list = subscription
                if subscription_list and isinstance(subscription_list[0], dict):
                    subscription_keys = list(subscription_list[0].keys())
            elif isinstance(subscription, dict):
                subscription_list = [subscription]
                subscription_keys = list(subscription.keys())
        
        # Tenta construir link possível
        possible_links = []
        if user and isinstance(user, dict):
            user_id = user.get("id")
            if user_id:
                base_url = os.getenv("THEMEMBERS_BASE_URL", "https://registration.themembers.dev.br/api").replace("/api", "")
                possible_links = [
                    f"{base_url}/access/{user_id}",
                    f"{base_url}/login?user_id={user_id}",
                    f"{base_url}/first-access/{user_id}",
                    f"{base_url}/access?token={user_id}",
                    f"{base_url}/login/{user_id}",
                ]
        
        return {
            "email": email,
            "user_found": user is not None,
            "subscription_found": subscription is not None,
            "user": user,
            "subscription": subscription,
            "subscription_is_array": isinstance(subscription, list),
            "subscription_count": len(subscription_list) if subscription_list else 0,
            "user_keys": list(user.keys()) if isinstance(user, dict) else None,
            "subscription_keys": subscription_keys,
            "user_id": user.get("id") if isinstance(user, dict) else None,
            "possible_access_links": possible_links,
            "note": "Se nenhum link funcionar, verifique a documentação da API da The Members ou entre em contato com o suporte para descobrir o formato correto do link de acesso.",
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[DEBUG_THEMEMBERS] Erro: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar usuário: {str(e)}"
        )

