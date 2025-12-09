# app/routers/eduzz.py
import os
import hmac
import hashlib
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.orm import Session

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
    
    # 12) Envia mensagem pós-compra se a venda foi aprovada e contato tem thread
    post_purchase_sent = False
    if event == "sale.approved" and contact and contact.thread_id:
        try:
            post_purchase_sent = send_post_purchase_message(
                db=db,
                contact=contact,
                sale_event=sale_event,
                plan_type=plan_type or "mensal",
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

