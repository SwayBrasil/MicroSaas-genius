# app/routers/eduzz.py
import os
import hmac
import hashlib
import json
import uuid
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Header, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
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

# 🔐 Segredo do webhook (The Members → MyEduzz)
EDUZZ_SECRET = os.getenv("EDUZZ_SECRET") or os.getenv("THEMEMBERS_WEBHOOK_SECRET") or os.getenv("EDUZZ_WEBHOOK_ORIGIN", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev").lower()

# Headers possíveis para assinatura
SIGNATURE_HEADERS = ["x-signature", "x-hub-signature", "x-eduzz-signature", "signature"]

logger = logging.getLogger(__name__)


def verify_eduzz_signature(body: bytes, signature: str | None, request_headers: dict = None) -> tuple[bool, str]:
    """
    Valida a assinatura do webhook usando HMAC-SHA256.
    
    Returns:
        (is_valid, error_message) - True se válida, False com mensagem de erro se inválida
    """
    # Modo dev: permite bypass se não houver secret configurado
    if ENVIRONMENT == "dev" and not EDUZZ_SECRET:
        logger.warning(f"[EDUZZ_WEBHOOK] ⚠️ MODO DEV: Assinatura bypassada (nenhum secret configurado)")
        return True, None
    
    # Se não tem assinatura
    if not signature:
        if ENVIRONMENT == "production":
            return False, "Missing signature header (required in production)"
        else:
            logger.warning(f"[EDUZZ_WEBHOOK] ⚠️ MODO DEV: Header de assinatura ausente, mas continuando")
            return True, None
    
    # Se não tem secret configurado, não pode validar
    if not EDUZZ_SECRET:
        if ENVIRONMENT == "production":
            return False, "Webhook secret not configured"
        logger.warning(f"[EDUZZ_WEBHOOK] ⚠️ Secret não configurado. Não é possível validar assinatura.")
        return True, None
    
    # Valida assinatura HMAC-SHA256
    expected = hmac.new(
        EDUZZ_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    # Usa compare_digest pra evitar timing attack
    if not hmac.compare_digest(expected, signature):
        logger.error(f"[EDUZZ_WEBHOOK] ❌ Assinatura inválida. Esperado: {expected[:20]}..., Recebido: {signature[:20] if signature else 'None'}...")
        return False, "Invalid signature"
    
    logger.info(f"[EDUZZ_WEBHOOK] ✅ Assinatura validada com sucesso")
    return True, None


@router.get("/eduzz")
async def verify_webhook_url(request: Request):
    """
    Endpoint GET para verificação de URL pelo painel do The Members.
    Retorna 200 sem exigir assinatura, apenas para confirmação de que o endpoint existe.
    """
    logger.info(f"[EDUZZ_WEBHOOK] verify_url - GET /webhook/eduzz - IP: {request.client.host if request.client else 'unknown'}")
    return {"ok": True, "message": "Webhook endpoint is active"}


@router.post("/eduzz")
async def webhook_eduzz(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Webhook para receber eventos da Eduzz/The Members.
    
    Valida a assinatura HMAC-SHA256 e processa eventos de venda aprovada,
    criando usuários na The Members quando necessário e relacionando com contatos.
    
    Retorna sempre 200 para evitar retries desnecessários, exceto em casos críticos (401 para assinatura).
    """
    request_id = str(uuid.uuid4())[:8]
    status_code = 200
    response_data = {"received": True}
    
    try:
        # 🚨 LOG CRÍTICO: Webhook recebido (ANTES de qualquer validação)
        logger.info(f"[EDUZZ_WEBHOOK] ========== WEBHOOK RECEBIDO [ID: {request_id}] ==========")
        logger.info(f"[EDUZZ_WEBHOOK] Request ID: {request_id}")
        logger.info(f"[EDUZZ_WEBHOOK] IP: {request.client.host if request.client else 'unknown'}")
        logger.info(f"[EDUZZ_WEBHOOK] Path: {request.url.path}")
        logger.info(f"[EDUZZ_WEBHOOK] Method: {request.method}")
        
        # Busca assinatura em múltiplos headers possíveis
        signature = None
        signature_header_used = None
        for header_name in SIGNATURE_HEADERS:
            sig = request.headers.get(header_name) or request.headers.get(header_name.replace("-", "_"))
            if sig:
                signature = sig
                signature_header_used = header_name
                break
        
        # Log headers relevantes (sem vazar tokens)
        relevant_headers = {
            "user-agent": request.headers.get("user-agent"),
            "content-type": request.headers.get("content-type"),
            "signature_header": signature_header_used,
            "has_signature": bool(signature),
        }
        logger.info(f"[EDUZZ_WEBHOOK] Headers relevantes: {relevant_headers}")
        
        # 1) Lê body cru ANTES de validar assinatura (para logar mesmo se falhar)
        raw_body = await request.body()
        body_preview = raw_body[:500].decode('utf-8', errors='ignore') if raw_body else 'empty'
        logger.info(f"[EDUZZ_WEBHOOK] Body recebido (primeiros 500 chars): {body_preview}")
        
        # 2) Valida assinatura
        is_valid, sig_error = verify_eduzz_signature(raw_body, signature, dict(request.headers))
        if not is_valid:
            logger.error(f"[EDUZZ_WEBHOOK] ❌ Erro na validação de assinatura: {sig_error}")
            status_code = 401
            response_data = {"error": sig_error, "received": True}
            logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Assinatura inválida")
            return JSONResponse(status_code=status_code, content=response_data)
        
        # 3) Converte para JSON com tratamento robusto
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"[EDUZZ_WEBHOOK] ❌ Erro ao parsear JSON: {str(e)}")
            status_code = 400
            response_data = {"error": "Invalid JSON", "received": True, "details": str(e)}
            logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - JSON inválido")
            return JSONResponse(status_code=status_code, content=response_data)
        except Exception as e:
            logger.error(f"[EDUZZ_WEBHOOK] ❌ Erro inesperado ao parsear body: {str(e)}", exc_info=True)
            status_code = 400
            response_data = {"error": "Invalid request body", "received": True}
            logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Body inválido")
            return JSONResponse(status_code=status_code, content=response_data)
        
        # Extrai campos principais (com fallbacks para diferentes formatos e suporte a payloads aninhados)
        # Suporta payloads aninhados do TheMembers (ex: payload.buyer.email, payload.customer.phone)
        def extract_nested(data, *keys):
            """Extrai valor de campos aninhados ou planos"""
            for key in keys:
                if isinstance(data, dict):
                    # Tenta campo direto
                    if key in data:
                        value = data[key]
                        if value:
                            return value
                    # Tenta campo aninhado (ex: buyer.email, customer.phone)
                    if "." in key:
                        parts = key.split(".")
                        current = data
                        for part in parts:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                current = None
                                break
                        if current:
                            return current
            return None
        
        event = extract_nested(payload, "event", "type", "event_type") or payload.get("event") or payload.get("type") or payload.get("event_type")
        buyer_email = extract_nested(payload, "buyer_email", "email", "customer_email", "buyer.email", "customer.email") or payload.get("buyer_email") or payload.get("email") or payload.get("customer_email")
        buyer_phone = extract_nested(payload, "buyer_phone", "phone", "customer_phone", "mobile", "buyer.phone", "customer.phone", "buyer.mobile", "customer.mobile") or payload.get("buyer_phone") or payload.get("phone") or payload.get("customer_phone") or payload.get("mobile")
        buyer_name = extract_nested(payload, "buyer_name", "name", "customer_name", "buyer.name", "customer.name") or payload.get("buyer_name") or payload.get("name") or payload.get("customer_name")
        product_id = extract_nested(payload, "product_id", "product", "product_code", "product.id", "product_id") or payload.get("product_id") or payload.get("product") or payload.get("product_code")
        order_id = extract_nested(payload, "order_id", "order", "transaction_id", "invoice_id", "order.id", "transaction.id") or payload.get("order_id") or payload.get("order") or payload.get("transaction_id") or payload.get("invoice_id")
        transaction_key = extract_nested(payload, "transactionkey", "transaction_key", "chave", "key", "transaction.key") or payload.get("transactionkey") or payload.get("transaction_key") or payload.get("chave") or payload.get("key")
        event_id = extract_nested(payload, "event_id", "id", "external_id", "event.id") or payload.get("event_id") or payload.get("id") or payload.get("external_id") or order_id
        timestamp = extract_nested(payload, "timestamp", "created_at", "date", "event.timestamp") or payload.get("timestamp") or payload.get("created_at") or payload.get("date")
        value = extract_nested(payload, "value", "amount", "total", "payment.value", "transaction.amount") or payload.get("value") or payload.get("amount") or payload.get("total")  # em centavos
        
        # Log completo do payload parseado
        logger.info(f"[EDUZZ_WEBHOOK] ========== PAYLOAD PARSEADO [ID: {request_id}] ==========")
        logger.info(f"[EDUZZ_WEBHOOK] Event: {event}")
        logger.info(f"[EDUZZ_WEBHOOK] Buyer Email: {buyer_email}")
        logger.info(f"[EDUZZ_WEBHOOK] Buyer Phone: {buyer_phone}")
        logger.info(f"[EDUZZ_WEBHOOK] Buyer Name: {buyer_name}")
        logger.info(f"[EDUZZ_WEBHOOK] Product ID: {product_id}")
        logger.info(f"[EDUZZ_WEBHOOK] Order ID: {order_id}")
        logger.info(f"[EDUZZ_WEBHOOK] Event ID: {event_id}")
        logger.info(f"[EDUZZ_WEBHOOK] Value: {value}")
        logger.info(f"[EDUZZ_WEBHOOK] Timestamp: {timestamp}")
        
        # 4) Verifica idempotência ANTES de processar
        if event_id:
            existing_event = db.query(SaleEvent).filter(
                SaleEvent.event_id == event_id,
                SaleEvent.source == "eduzz"
            ).first()
            
            if existing_event:
                logger.info(f"[EDUZZ_WEBHOOK] ⚠️ Evento duplicado detectado (event_id: {event_id}). Já processado em {existing_event.created_at}")
                if existing_event.post_purchase_sent:
                    logger.info(f"[EDUZZ_WEBHOOK] ✅ Mensagem pós-compra já foi enviada anteriormente. Ignorando evento duplicado.")
                    response_data = {
                        "status": "duplicate",
                        "message": "Event already processed",
                        "event_id": event_id,
                        "post_purchase_sent": True,
                        "processed_at": existing_event.created_at.isoformat() if existing_event.created_at else None,
                    }
                    logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Evento duplicado")
                    return JSONResponse(status_code=200, content=response_data)
                else:
                    logger.warning(f"[EDUZZ_WEBHOOK] ⚠️ Evento duplicado mas mensagem pós-compra NÃO foi enviada. Reprocessando...")
        
        # 5) Processa eventos de abandonment (carrinho abandonado)
        if event == "cart.abandonment" or event == "abandonment":
            if not buyer_email:
                response_data = {"error": "buyer_email is required for abandonment events", "received": True}
                logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Abandonment sem email")
                return JSONResponse(status_code=200, content=response_data)
            
            try:
                contact = db.query(Contact).filter(Contact.email == buyer_email).first()
                
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
                
                response_data = {
                    "status": "ok",
                    "action": "abandonment_recorded",
                    "cart_event_id": cart_event.id,
                }
                logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Abandonment registrado")
                return JSONResponse(status_code=200, content=response_data)
            except Exception as e:
                logger.error(f"[EDUZZ_WEBHOOK] Erro ao processar abandonment: {str(e)}", exc_info=True)
                db.rollback()
                response_data = {"received": True, "error": "Error processing abandonment (logged)"}
                return JSONResponse(status_code=200, content=response_data)
        
        # 6) Identifica eventos de pagamento aprovado
        PAYMENT_APPROVED_EVENTS = [
            "myeduzz.invoice_paid",
            "myeduzz.contract_created",
            "sale.approved",
            "invoice.paid",
            "payment.approved",
        ]
        
        is_payment_approved = event in PAYMENT_APPROVED_EVENTS if event else False
        
        logger.info(f"[EDUZZ_WEBHOOK] Evento é pagamento aprovado? {is_payment_approved} (event: {event})")
        
        # 7) Identifica tipo de plano ANTES de criar o SaleEvent
        plan_type = None
        if is_payment_approved and buyer_email:
            plan_type = identify_plan_type(product_id, value)
            logger.info(f"[EDUZZ_WEBHOOK] Tipo de plano identificado: {plan_type}")
        
        # 8) Salva o evento de venda (independente do tipo de evento)
        try:
            sale_event = SaleEvent(
                source="eduzz",
                event=event or "unknown",
                event_id=event_id,
                order_id=order_id,
                buyer_email=buyer_email or "",
                buyer_name=buyer_name,
                value=value,
                product_id=product_id,
                plan_type=plan_type,
                raw_payload=payload,
            )
            
            invoice_status = payload.get("invoice_status") or payload.get("status")
            
            if not is_payment_approved:
                # Salva evento mas não processa criação de usuário/pós-compra
                logger.info(f"[EDUZZ_WEBHOOK] Evento '{event}' não é de pagamento aprovado. Salvando mas não processando.")
                db.add(sale_event)
                db.commit()
                response_data = {
                    "status": "ignored",
                    "reason": "event not handled",
                    "event": event,
                    "invoice_status": invoice_status,
                    "note": f"Apenas eventos de pagamento aprovado são processados: {', '.join(PAYMENT_APPROVED_EVENTS)}"
                }
                logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Evento ignorado: {event}")
                return JSONResponse(status_code=200, content=response_data)
            
            if not buyer_email:
                db.add(sale_event)
                db.commit()
                response_data = {"error": "buyer_email is required", "received": True}
                logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Sem buyer_email")
                return JSONResponse(status_code=200, content=response_data)
            
            # Continua processamento de pagamento aprovado...
            # (resto da lógica existente)
            # Por questões de espaço, vou manter a lógica existente mas dentro de try/except
            
            # 9) Verifica se há carrinho abandonado para recuperar
            if buyer_email:
                try:
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
                        abandoned_cart.recovered = True
                        abandoned_cart.recovered_at = datetime.now()
                        abandoned_cart.order_id = order_id
                        db.add(abandoned_cart)
                        
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
                except Exception as e:
                    logger.warning(f"[EDUZZ_WEBHOOK] Erro ao processar carrinho abandonado: {str(e)}", exc_info=True)
            
            # 10) Busca contato no banco pelo email
            contact = db.query(Contact).filter(Contact.email == buyer_email).first()
            
            # Se não encontrou por email, tenta buscar por themembers_user_id
            if not contact:
                try:
                    themembers_user, _ = await get_user_by_email(buyer_email)
                    if themembers_user:
                        themembers_user_id = str(themembers_user.get("id", ""))
                        contact = db.query(Contact).filter(Contact.themembers_user_id == themembers_user_id).first()
                except Exception as e:
                    logger.warning(f"[EDUZZ_WEBHOOK] Erro ao buscar usuário na The Members: {str(e)}")
            
            # 11) Regra de mapeamento de produto
            themembers_product_id = os.getenv("THEMEMBERS_DEFAULT_PRODUCT_ID", "2352153")
            
            # 12) Verifica se usuário já existe na The Members
            themembers_user_id = None
            action = "no_action"
            
            try:
                themembers_user, themembers_subscription = await get_user_by_email(buyer_email)
                
                if themembers_user:
                    themembers_user_id = str(themembers_user.get("id", ""))
                    action = "user_already_exists"
                else:
                    # Cria usuário + assinatura
                    buyer_name = payload.get("buyer_name", "Aluno")
                    buyer_last_name = payload.get("buyer_last_name", "ViaEduzz")
                    
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
                    
                    if isinstance(created_response, dict):
                        if "user" in created_response:
                            themembers_user_id = str(created_response["user"].get("id", ""))
                        elif "users" in created_response and len(created_response["users"]) > 0:
                            themembers_user_id = str(created_response["users"][0].get("id", ""))
                        elif "id" in created_response:
                            themembers_user_id = str(created_response["id"])
                    
                    themembers_user, themembers_subscription = await get_user_by_email(buyer_email)
                    if themembers_user:
                        themembers_user_id = str(themembers_user.get("id", ""))
                    
                    action = "user_created"
            except Exception as e:
                logger.error(f"[EDUZZ_WEBHOOK] Erro ao criar/buscar usuário na The Members: {str(e)}", exc_info=True)
                # Continua mesmo se falhar
            
            # 13) Atualiza ou cria contato
            try:
                if contact:
                    if not contact.email:
                        contact.email = buyer_email
                    if not contact.themembers_user_id and themembers_user_id:
                        contact.themembers_user_id = themembers_user_id
                    if not contact.name and buyer_name:
                        contact.name = buyer_name
                else:
                    from ..models import User
                    default_user = db.query(User).filter(User.email == "Admin").first()
                    user_id = default_user.id if default_user else None
                    
                    contact = Contact(
                        email=buyer_email,
                        name=buyer_name or "Cliente Eduzz",
                        phone=buyer_phone,
                        themembers_user_id=themembers_user_id,
                        user_id=user_id,
                        thread_id=None,
                    )
                    db.add(contact)
                
                db.flush()
                
                # 14) Atualiza sale_event com contact_id e themembers_user_id
                sale_event.contact_id = contact.id
                sale_event.themembers_user_id = themembers_user_id
                db.add(sale_event)
                
                # 15) Cria ou atualiza produto da Eduzz no banco
                if product_id:
                    eduzz_product = db.query(ProductExternal).filter(
                        ProductExternal.external_product_id == product_id,
                        ProductExternal.source == "eduzz"
                    ).first()
                    
                    if not eduzz_product:
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
                
                # 16) Cria ou atualiza subscription_external
                if themembers_user_id and themembers_subscription:
                    product_external = db.query(ProductExternal).filter(
                        ProductExternal.external_product_id == themembers_product_id,
                        ProductExternal.source == "themembers"
                    ).first()
                    
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
                    
                    subscription = db.query(SubscriptionExternal).filter(
                        SubscriptionExternal.themembers_user_id == themembers_user_id,
                        SubscriptionExternal.contact_id == contact.id,
                    ).first()
                    
                    subscription_data = themembers_subscription if isinstance(themembers_subscription, dict) else {}
                    
                    if subscription:
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
            except Exception as e:
                logger.error(f"[EDUZZ_WEBHOOK] Erro ao processar contato/subscription: {str(e)}", exc_info=True)
                db.rollback()
                response_data = {"received": True, "error": "Error processing contact (logged)"}
                return JSONResponse(status_code=200, content=response_data)
            
            # 17) Busca link de acesso personalizado usando resolve_first_access_link
            access_link = None
            try:
                if buyer_email:
                    from ..services.themembers_service import resolve_first_access_link
                    
                    logger.info(f"[EDUZZ_WEBHOOK] Resolvendo link de primeiro acesso para {buyer_email}...")
                    access_link = await resolve_first_access_link(
                        email=buyer_email,
                        user_id=themembers_user_id,
                        subscription_data=themembers_subscription,
                        user_data=themembers_user if isinstance(themembers_user, dict) else None,
                        transaction_key=transaction_key,
                        order_id=order_id,
                    )
                    
                    if access_link:
                        logger.info(f"[EDUZZ_WEBHOOK] ✅ Link de primeiro acesso resolvido: {access_link[:50]}...")
                    else:
                        logger.warning(f"[EDUZZ_WEBHOOK] ⚠️ Não foi possível resolver link de primeiro acesso válido para {buyer_email}")
            except Exception as e:
                logger.error(f"[EDUZZ_WEBHOOK] Erro ao resolver link de acesso: {str(e)}", exc_info=True)
            
            # 18) Envia mensagem pós-compra
            post_purchase_sent = False
            
            logger.info(f"[EDUZZ_WEBHOOK] ========== VERIFICANDO ENVIO PÓS-COMPRA ==========")
            logger.info(f"[EDUZZ_WEBHOOK] Event: {event}")
            logger.info(f"[EDUZZ_WEBHOOK] Contact existe: {contact is not None}")
            if contact:
                logger.info(f"[EDUZZ_WEBHOOK] Contact ID: {contact.id}")
                logger.info(f"[EDUZZ_WEBHOOK] Contact Thread ID: {contact.thread_id}")
                logger.info(f"[EDUZZ_WEBHOOK] Contact Email: {contact.email}")
                logger.info(f"[EDUZZ_WEBHOOK] Contact Phone: {contact.phone}")
            
            if contact:
                # Busca thread por telefone se não tiver thread_id
                if not contact.thread_id:
                    logger.warning(f"[EDUZZ_WEBHOOK] ⚠️ Contato {contact.id} não tem thread_id vinculado. Tentando buscar thread por telefone...")
                    
                    buyer_phone_for_search = buyer_phone or contact.phone
                    if buyer_phone_for_search:
                        from ..services.post_purchase import find_thread_by_phone
                        matching_thread = find_thread_by_phone(db, buyer_phone_for_search)
                        if matching_thread:
                            contact.thread_id = matching_thread.id
                            db.commit()
                            logger.info(f"[EDUZZ_WEBHOOK] ✅ Thread {matching_thread.id} vinculada ao contato {contact.id}")
                
                if contact.thread_id:
                    logger.info(f"[EDUZZ_WEBHOOK] ✅ Preparando envio de mensagem pós-compra. Contact ID: {contact.id}, Thread ID: {contact.thread_id}, Access Link: {access_link}")
                    try:
                        post_purchase_sent = send_post_purchase_message(
                            db=db,
                            contact=contact,
                            sale_event=sale_event,
                            plan_type=plan_type or "mensal",
                            access_link=access_link,
                        )
                        logger.info(f"[EDUZZ_WEBHOOK] ✅ Mensagem pós-compra enviada: {post_purchase_sent}")
                        
                        if post_purchase_sent:
                            sale_event.post_purchase_sent = True
                            db.commit()
                            logger.info(f"[EDUZZ_WEBHOOK] ✅ Flag post_purchase_sent atualizada para True")
                        else:
                            logger.warning(f"[EDUZZ_WEBHOOK] ⚠️ Mensagem pós-compra não foi enviada. Flag não atualizada.")
                    except Exception as e:
                        logger.error(f"[EDUZZ_WEBHOOK] ❌ Erro ao enviar mensagem pós-compra: {str(e)}", exc_info=True)
                else:
                    logger.warning(f"[EDUZZ_WEBHOOK] ⚠️ Contato {contact.id} ainda não tem thread_id após busca. Mensagem pós-compra não será enviada.")
            
            # Sucesso - retorna resposta final
            response_data = {
                "status": "ok",
                "action": action,
                "contact_id": contact.id if contact else None,
                "themembers_user_id": themembers_user_id,
                "subscription_created": themembers_user_id is not None,
                "plan_type": plan_type,
                "post_purchase_sent": post_purchase_sent,
            }
            
            logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Processado com sucesso. Event: {event}, Post Purchase: {post_purchase_sent}")
            return JSONResponse(status_code=200, content=response_data)
            
        except Exception as e:
            logger.error(f"[EDUZZ_WEBHOOK] Erro ao salvar evento: {str(e)}", exc_info=True)
            db.rollback()
            response_data = {"received": True, "error": "Error saving event (logged)"}
            return JSONResponse(status_code=200, content=response_data)
        
    except HTTPException as e:
        # HTTPExceptions são tratadas normalmente (401, 400, etc)
        logger.error(f"[EDUZZ_WEBHOOK] [ID: {request_id}] HTTPException: {e.status_code} - {e.detail}")
        return JSONResponse(status_code=e.status_code, content={"error": e.detail, "received": True})
        
    except Exception as e:
        # Qualquer outra exceção: loga mas retorna 200 para evitar retries
        logger.error(f"[EDUZZ_WEBHOOK] [ID: {request_id}] ❌ Erro interno não tratado: {str(e)}", exc_info=True)
        status_code = 200  # Retorna 200 mesmo em erro para evitar retries
        response_data = {
            "received": True,
            "error": "Internal error (logged)",
            "request_id": request_id
        }
        logger.info(f"[EDUZZ_WEBHOOK] [ID: {request_id}] Status: {status_code} - Erro interno")
        return JSONResponse(status_code=status_code, content=response_data)


# ==================== ENDPOINT DE TESTE ====================

class TestSaleRequest(BaseModel):
    """Payload para simular uma compra de teste"""
    buyer_email: str
    buyer_name: Optional[str] = None
    buyer_phone: Optional[str] = None
    product_id: Optional[str] = None
    value: Optional[int] = None
    order_id: Optional[str] = None
    plan_type: Optional[str] = None
    event: Optional[str] = None
    transaction_key: Optional[str] = None
    transactionkey: Optional[str] = None


@router.post("/eduzz/test")
async def test_eduzz_webhook(
    body: TestSaleRequest,
    db: Session = Depends(get_db),
    mode: Optional[str] = Query("link-only", description="Modo de teste: 'link-only' (padrão) ou 'full'"),
):
    """
    Endpoint de TESTE LOCAL para simular webhook do The Members/Eduzz.
    
    ⚠️ ATENÇÃO: Este endpoint só funciona em ambiente de desenvolvimento/teste.
    
    Modos disponíveis:
    - link-only (padrão): Apenas executa resolve_first_access_link() e envia mensagem pós-compra.
                          Não chama get_user_by_email() nem cria/busca usuário na TheMembers.
    - full: Executa o fluxo completo (busca/cria usuário na TheMembers).
            Se der 401/403, não quebra: loga e segue para fallback.
    
    Exemplo de uso (link-only):
    ```bash
    curl -X POST "http://localhost:8000/webhook/eduzz/test?mode=link-only" \
      -H "Content-Type: application/json" \
      -d '{
        "buyer_email": "teste@exemplo.com",
        "buyer_name": "Maria Silva",
        "buyer_phone": "+5561999999999",
        "product_id": "2457307",
        "value": 6990,
        "transaction_key": "abc123"
      }'
    ```
    
    Exemplo de uso (full):
    ```bash
    curl -X POST "http://localhost:8000/webhook/eduzz/test?mode=full" \
      -H "Content-Type: application/json" \
      -d '{
        "buyer_email": "teste@exemplo.com",
        "buyer_name": "Maria Silva",
        "buyer_phone": "+5561999999999"
      }'
    ```
    """
    if ENVIRONMENT == "production":
        raise HTTPException(
            status_code=403,
            detail="Este endpoint de teste não está disponível em produção"
        )
    
    is_full_mode = mode == "full"
    logger.info(f"[TEST_EDUZZ] ========== TESTE DE WEBHOOK [Email: {body.buyer_email}, Mode: {mode}] ==========")
    
    # Prepara payload simulado
    order_id = body.order_id or f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    product_id = body.product_id or "2457307"
    value = body.value or 6990
    event = body.event or "myeduzz.invoice_paid"
    
    simulated_payload = {
        "event": event,
        "event_id": f"TEST-{order_id}",
        "order_id": order_id,
        "buyer_email": body.buyer_email,
        "buyer_name": body.buyer_name or "Cliente Teste",
        "buyer_phone": body.buyer_phone,
        "phone": body.buyer_phone,
        "product_id": product_id,
        "value": value,
        "timestamp": datetime.now().isoformat(),
        "invoice_status": "paid",
        "status": "approved",
    }
    
    logger.info(f"[TEST_EDUZZ] Simulando evento: {event}, Email: {body.buyer_email}, Phone: {body.buyer_phone}")
    
    # Cria um request mock e chama a função interna
    # Por simplicidade, vamos criar um request mock básico
    class MockRequest:
        def __init__(self, payload, phone=None):
            self.payload = payload
            self.client = type('obj', (object,), {'host': 'test'})()
            self.url = type('obj', (object,), {'path': '/webhook/eduzz/test'})()
            self.method = "POST"
            self.headers = {}
            self._phone = phone
        
        async def body(self):
            return json.dumps(self.payload).encode()
        
        async def json(self):
            return self.payload
    
    mock_request = MockRequest(simulated_payload, body.buyer_phone)
    
    # Chama o webhook real mas com skip de assinatura
    # Vamos fazer um workaround: criar um request real temporário
    from starlette.requests import Request as StarletteRequest
    from starlette.datastructures import Headers
    
    # Por enquanto, vamos duplicar a lógica mas sem validação de assinatura
    # Isso não é ideal, mas funciona para teste
    try:
        # Simula chamada direta à lógica (sem validação de assinatura)
        # Por questões de tempo, vamos fazer uma versão simplificada
        
        # Extrai campos
        event = simulated_payload.get("event")
        buyer_email = simulated_payload.get("buyer_email")
        buyer_phone = simulated_payload.get("buyer_phone")
        product_id = simulated_payload.get("product_id")
        value = simulated_payload.get("value")
        order_id = simulated_payload.get("order_id")
        event_id = simulated_payload.get("event_id")
        
        # Busca ou cria thread por telefone se fornecido
        thread = None
        thread_created = False
        
        if body.buyer_phone:
            from ..services.post_purchase import find_thread_by_phone, normalize_phone
            from ..models import Thread, User
            
            normalized_phone = normalize_phone(body.buyer_phone)
            
            if normalized_phone:
                logger.info(f"[TEST_EDUZZ] Telefone normalizado: {normalized_phone}")
                
                # Busca thread existente
                thread = find_thread_by_phone(db, normalized_phone)
                
                if not thread:
                    # Cria thread automaticamente
                    logger.info(f"[TEST_EDUZZ] ⚠️ Nenhuma thread encontrada. Criando thread automaticamente...")
                    
                    default_user = db.query(User).filter(User.email == "Admin").first()
                    user_id = default_user.id if default_user else None
                    
                    thread_title = body.buyer_name or body.buyer_email or f"WhatsApp {normalized_phone[-4:]}"
                    
                    thread = Thread(
                        user_id=user_id,
                        title=thread_title,
                        external_user_phone=normalized_phone,
                        origin="test",
                        lead_stage="quente",
                    )
                    db.add(thread)
                    db.flush()
                    
                    thread_created = True
                    logger.info(f"[TEST_EDUZZ] ✅ Thread criada automaticamente: ID={thread.id}, Phone={normalized_phone}, Title={thread_title}")
                else:
                    logger.info(f"[TEST_EDUZZ] ✅ Thread encontrada: ID={thread.id}")
        
        # Busca contato
        contact = None
        if thread:
            contact = db.query(Contact).filter(Contact.thread_id == thread.id).first()
        
        if not contact:
            contact = db.query(Contact).filter(Contact.email == body.buyer_email).first()
        
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
        elif thread and not contact.thread_id:
            contact.thread_id = thread.id
            if not contact.phone:
                contact.phone = normalized_phone if normalized_phone else body.buyer_phone
            db.commit()
        
        if not contact.thread_id:
            return {
                "status": "warning",
                "message": f"Contato criado/encontrado (ID: {contact.id}), mas não foi possível criar thread. Telefone inválido ou ausente.",
                "contact_id": contact.id,
                "buyer_email": body.buyer_email,
                "buyer_phone": body.buyer_phone,
                "note": "Forneça um telefone válido para criar thread automaticamente e enviar mensagem pós-compra.",
            }
        
        # Cria SaleEvent
        plan_type = identify_plan_type(product_id, value)
        sale_event = SaleEvent(
            source="test",
            event=event,
            event_id=event_id,
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
        
        # ========== MODO LINK-ONLY (padrão) vs FULL ==========
        themembers_user_id = None
        access_link = None
        link_type = None
        
        if is_full_mode:
            # Modo FULL: Busca/cria usuário na TheMembers (com tratamento de 401/403)
            logger.info(f"[TEST_EDUZZ] Modo FULL: Buscando/criando usuário na TheMembers...")
            themembers_user = None
            themembers_subscription = None
            
            try:
                themembers_user, themembers_subscription = await get_user_by_email(body.buyer_email)
                
                if not themembers_user:
                    buyer_name = body.buyer_name or "Cliente"
                    buyer_last_name = "Teste"
                    if " " in buyer_name:
                        parts = buyer_name.split(" ", 1)
                        buyer_name = parts[0]
                        buyer_last_name = parts[1]
                    
                    await create_user_with_product(
                        email=body.buyer_email,
                        name=buyer_name,
                        last_name=buyer_last_name,
                        phone=body.buyer_phone,
                        reference_id=order_id,
                        accession_date=datetime.now().strftime("%Y-%m-%d"),
                        product_id=os.getenv("THEMEMBERS_DEFAULT_PRODUCT_ID", "2352153"),
                    )
                    
                    themembers_user, themembers_subscription = await get_user_by_email(body.buyer_email)
                
                if themembers_user:
                    themembers_user_id = str(themembers_user.get("id", ""))
                    contact.themembers_user_id = themembers_user_id
            except Exception as e:
                logger.warning(f"[TEST_EDUZZ] Erro ao criar/buscar usuário na The Members (seguindo para fallback): {str(e)}")
                # Se der 401/403, get_user_by_email já retorna None sem lançar exceção
                # Continua para fallback
                themembers_user = None
                themembers_subscription = None
                themembers_user_id = None
        else:
            # Modo LINK-ONLY (padrão): Não busca/cria usuário
            logger.info(f"[TEST_EDUZZ] Modo LINK-ONLY: Pulando busca/criação de usuário na TheMembers")
            themembers_user = None
            themembers_subscription = None
        
        # Resolve link de acesso usando resolve_first_access_link
        # IMPORTANTE: Funciona mesmo sem usuário (fallback funciona só com transaction_key)
        from ..services.themembers_service import resolve_first_access_link, _classify_access_link
        
        logger.info(f"[TEST_EDUZZ] Resolvendo link de primeiro acesso para {body.buyer_email}...")
        # Para teste, pode passar transaction_key se disponível no body
        try:
            body_dict = body.model_dump() if hasattr(body, 'model_dump') else (body.dict() if hasattr(body, 'dict') else {})
        except:
            body_dict = {}
        test_transaction_key = (
            body_dict.get('transaction_key') or 
            body_dict.get('transactionkey') or 
            getattr(body, 'transaction_key', None) or 
            getattr(body, 'transactionkey', None)
        )
        test_order_id = body_dict.get('order_id') or getattr(body, 'order_id', None)
        
        access_link = await resolve_first_access_link(
            email=body.buyer_email,
            user_id=themembers_user_id,
            subscription_data=themembers_subscription,
            user_data=themembers_user if isinstance(themembers_user, dict) else None,
            transaction_key=test_transaction_key,
            order_id=test_order_id,
        )
        
        # Classifica o tipo de link retornado
        if access_link:
            link_type = _classify_access_link(access_link)
            logger.info(f"[TEST_EDUZZ] ✅ Link de primeiro acesso resolvido (link_type={link_type}): {access_link[:50]}...")
        else:
            logger.warning(f"[TEST_EDUZZ] ⚠️ Não foi possível resolver link de primeiro acesso válido")
        
        sale_event.themembers_user_id = themembers_user_id
        db.commit()
        
        # Envia mensagem pós-compra conforme o tipo de link retornado
        post_purchase_sent = False
        if contact.thread_id:
            try:
                # Log padronizado com link_type
                if link_type:
                    logger.info(f"[POST_PURCHASE] link_type={link_type}, access_link={'...' + access_link[-30:] if access_link else 'None'}")
                
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
                logger.error(f"[TEST_EDUZZ] Erro ao enviar mensagem pós-compra: {str(e)}", exc_info=True)
        
        response_data = {
            "status": "ok",
            "message": "Compra simulada com sucesso!",
            "mode": mode,
            "contact_id": contact.id,
            "thread_id": contact.thread_id,
            "thread_created": thread.id if thread_created else None,
            "thread_found": thread.id if thread and not thread_created else None,
            "themembers_user_id": themembers_user_id,
            "plan_type": plan_type,
            "post_purchase_sent": post_purchase_sent,
            "access_link": access_link,
            "link_type": link_type,
            "order_id": order_id,
            "phone": body.buyer_phone,
        }
        
        if thread_created:
            logger.info(f"[TEST_EDUZZ] ✅ Thread criada automaticamente e mensagem pós-compra enviada")
        elif post_purchase_sent:
            logger.info(f"[TEST_EDUZZ] ✅ Mensagem pós-compra enviada com sucesso")
        
        return response_data
        
    except Exception as e:
        logger.error(f"[TEST_EDUZZ] Erro ao processar compra simulada: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar compra simulada: {str(e)}"
        )


@router.get("/debug/themembers/magiclink-from-gmail", tags=["webhooks"])
async def debug_magiclink_from_gmail(
    email: str = Query(..., description="Email do comprador para buscar link no Gmail"),
    db: Session = Depends(get_db),
):
    """
    Endpoint de DEBUG para testar busca de link de login mágico no Gmail.
    
    Retorna JSON com informações sobre o link encontrado (se houver).
    Protegido: só funciona em ambiente não-produção.
    """
    if ENVIRONMENT == "production":
        raise HTTPException(
            status_code=403,
            detail="Este endpoint de debug não está disponível em produção"
        )
    
    try:
        from ..services.gmail_magiclink_service import get_magic_link_from_gmail
        
        logger.info(f"[DEBUG_GMAIL_MAGICLINK] Buscando link para {email}...")
        
        result = await get_magic_link_from_gmail(email)
        
        if result and result.get("url"):
            # Mascara o token na URL para segurança
            url = result["url"]
            masked_url = url[:50] + "..." if len(url) > 50 else url
            
            return {
                "found": True,
                "link_type": result.get("link_type", "login_magico"),
                "source": result.get("source", "gmail"),
                "url": url,  # URL completa (endpoint de debug, pode mostrar)
                "url_masked": masked_url,  # URL mascarada para logs
                "email": email,
            }
        else:
            return {
                "found": False,
                "link_type": None,
                "source": None,
                "url": None,
                "email": email,
                "message": "Link não encontrado no Gmail após polling (60s)",
            }
            
    except Exception as e:
        logger.error(f"[DEBUG_GMAIL_MAGICLINK] Erro: {str(e)}", exc_info=True)
        return {
            "found": False,
            "error": str(e),
            "email": email,
        }
