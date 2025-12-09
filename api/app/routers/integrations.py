# app/routers/integrations.py
"""
Endpoints para gerenciar e verificar status de integrações.
"""
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, Dict, Any

from ..db import get_db
from ..models import SaleEvent, SubscriptionExternal, Contact, ProductExternal, CartEvent
from ..auth import get_current_user, User

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationStatus(BaseModel):
    name: str
    enabled: bool
    configured: bool
    status: str  # "active", "inactive", "error"
    last_event_at: Optional[str]
    total_events: int
    config: Dict[str, Any]


@router.get("/status")
def get_integrations_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna o status de todas as integrações configuradas.
    """
    integrations = []

    # 1. Eduzz
    # Verifica se o secret está configurado (mesmo que seja o padrão do código)
    eduzz_secret = os.getenv("EDUZZ_SECRET", "edzwgp_3eg5UCwaCxwoiFCn07FoIVGcxFFMHk7pCXYwvIyyIqwUl4lri")
    eduzz_configured = bool(eduzz_secret and eduzz_secret != "")
    
    # Busca último evento e total
    last_eduzz_event = (
        db.query(SaleEvent.created_at)
        .filter(SaleEvent.source == "eduzz")
        .order_by(SaleEvent.created_at.desc())
        .first()
    )
    
    total_eduzz_events = (
        db.query(func.count(SaleEvent.id))
        .filter(SaleEvent.source == "eduzz")
        .scalar()
    ) or 0
    
    # Estatísticas de vendas
    total_sales = (
        db.query(func.count(SaleEvent.id))
        .filter(SaleEvent.source == "eduzz", SaleEvent.event == "sale.approved")
        .scalar()
    ) or 0
    
    total_revenue = (
        db.query(func.coalesce(func.sum(SaleEvent.value), 0))
        .filter(SaleEvent.source == "eduzz", SaleEvent.event == "sale.approved")
        .scalar()
    ) or 0
    
    # Produtos sincronizados da Eduzz
    eduzz_products_count = (
        db.query(func.count(ProductExternal.id))
        .filter(ProductExternal.source == "eduzz")
        .scalar()
    ) or 0
    
    # Carrinhos recuperados
    recovered_carts = (
        db.query(func.count(CartEvent.id))
        .filter(CartEvent.source == "eduzz", CartEvent.recovered == True)
        .scalar()
    ) or 0

    # Determina URL do webhook (prioriza domínio de produção, senão usa ngrok, senão localhost)
    # Se tiver PRODUCTION_WEBHOOK_URL configurado, usa ele; senão usa PUBLIC_BASE_URL (ngrok) ou localhost
    production_url = os.getenv("PRODUCTION_WEBHOOK_URL") or os.getenv("WEBHOOK_BASE_URL")
    webhook_base = production_url or os.getenv("PUBLIC_BASE_URL") or "http://localhost:8000"
    
    integrations.append({
        "name": "Eduzz",
        "enabled": eduzz_configured,
        "configured": eduzz_configured,
        "status": "active" if eduzz_configured else "inactive",
        "last_event_at": last_eduzz_event[0].isoformat() if last_eduzz_event else None,
        "total_events": total_eduzz_events,
        "config": {
            "webhook_url": f"{webhook_base}/webhook/eduzz",
            "secret_configured": eduzz_configured,
            "description": "Integração com plataforma de vendas Eduzz. Recebe webhooks de vendas aprovadas e cria assinaturas automaticamente na The Members.",
            "total_sales": total_sales,
            "total_revenue": total_revenue,
            "products_synced": eduzz_products_count,
            "recovered_carts": recovered_carts,
        },
    })

    # 2. The Members
    # Verifica se os tokens estão configurados (mesmo que sejam os padrões do código)
    themembers_dev_token = os.getenv("THEMEMBERS_DEV_TOKEN") or os.getenv("THEMEMBERS_TOKEN_DEV")
    themembers_platform_token = os.getenv("THEMEMBERS_PLATFORM_TOKEN") or os.getenv("THEMEMBERS_TOKEN_PLATFORM")
    # Se não tiver nas env vars, usa os padrões do código
    if not themembers_dev_token:
        themembers_dev_token = "93c911d3-4580-4de7-a02b-db67fd9af8fe"
    if not themembers_platform_token:
        themembers_platform_token = "1644d350-82d5-4004-a52a-56bff805126e"
    themembers_configured = bool(
        themembers_dev_token
        and themembers_platform_token
        and themembers_dev_token != ""
        and themembers_platform_token != ""
    )

    # Busca total de assinaturas criadas
    total_subscriptions = (
        db.query(func.count(SubscriptionExternal.id))
        .filter(SubscriptionExternal.source == "eduzz")
        .scalar()
    ) or 0
    
    # Assinaturas ativas
    active_subscriptions = (
        db.query(func.count(SubscriptionExternal.id))
        .filter(SubscriptionExternal.source == "eduzz", SubscriptionExternal.status == "active")
        .scalar()
    ) or 0

    # Busca último contato com themembers_user_id
    last_subscription = (
        db.query(Contact.updated_at)
        .filter(Contact.themembers_user_id.isnot(None))
        .order_by(Contact.updated_at.desc())
        .first()
    )
    
    # Produtos sincronizados da The Members
    themembers_products_count = (
        db.query(func.count(ProductExternal.id))
        .filter(ProductExternal.source == "themembers")
        .scalar()
    ) or 0

    integrations.append({
        "name": "The Members",
        "enabled": themembers_configured,
        "configured": themembers_configured,
        "status": "active" if themembers_configured else "inactive",
        "last_event_at": last_subscription[0].isoformat() if last_subscription else None,
        "total_events": total_subscriptions,
        "config": {
            "base_url": os.getenv("THEMEMBERS_BASE_URL", "https://registration.themembers.dev.br/api"),
            "dev_token_configured": bool(themembers_dev_token),
            "platform_token_configured": bool(themembers_platform_token),
            "default_product_id": os.getenv("THEMEMBERS_DEFAULT_PRODUCT_ID", "2352153"),
            "description": "Plataforma de gestão de assinaturas. Cria e gerencia usuários e produtos automaticamente.",
            "active_subscriptions": active_subscriptions,
            "products_synced": themembers_products_count,
        },
    })


    return {
        "integrations": integrations,
        "summary": {
            "total": len(integrations),
            "active": sum(1 for i in integrations if i["status"] == "active"),
            "configured": sum(1 for i in integrations if i["configured"]),
        },
    }


@router.get("/events/recent")
def get_recent_events(
    limit: int = 20,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna eventos recentes de integrações.
    """
    query = db.query(SaleEvent).order_by(SaleEvent.created_at.desc())
    
    if source:
        query = query.filter(SaleEvent.source == source)
    
    events = query.limit(limit).all()
    
    return [
        {
            "id": e.id,
            "source": e.source,
            "event": e.event,
            "order_id": e.order_id,
            "buyer_email": e.buyer_email,
            "value": e.value,
            "created_at": e.created_at.isoformat(),
            "contact_id": e.contact_id,
        }
        for e in events
    ]

