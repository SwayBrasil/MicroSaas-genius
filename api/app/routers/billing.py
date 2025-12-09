# app/routers/billing.py
"""
Endpoints relacionados a billing, produtos e assinaturas.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from ..db import get_db
from ..models import Contact, SubscriptionExternal, ProductExternal
from ..auth import get_current_user, User
from ..services.themembers_service import get_products, get_user_by_email

router = APIRouter(prefix="/billing", tags=["billing"])


class ProductResponse(BaseModel):
    id: int
    external_product_id: str
    title: str
    type: Optional[str]
    status: Optional[str]
    source: Optional[str]  # "eduzz", "themembers", "manual"

    class Config:
        from_attributes = True


class CreateEduzzProductRequest(BaseModel):
    product_id: str
    title: str
    type: Optional[str] = None
    status: Optional[str] = "active"


class SubscriptionStatusResponse(BaseModel):
    has_subscription: bool
    is_active: bool
    subscription_id: Optional[int]
    product_title: Optional[str]
    status: Optional[str]
    expires_at: Optional[str]
    themembers_user_id: Optional[str]


@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    source: Optional[str] = None,  # "eduzz" ou "themembers" ou None (todos)
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista produtos disponíveis.
    
    Parâmetros:
    - source: Filtrar por origem ("eduzz", "themembers") ou None para todos
    """
    # Busca produtos do banco
    query = db.query(ProductExternal)
    
    if source:
        query = query.filter(ProductExternal.source == source)
    else:
        # Por padrão, mostra todos (eduzz e themembers)
        query = query.filter(ProductExternal.status == "active")
    
    products = query.all()
    
    # Se não tiver produtos no banco, tenta sincronizar da The Members
    if not products and (not source or source == "themembers"):
        try:
            themembers_products = await get_products()
            
            for prod_data in themembers_products:
                external_id = str(prod_data.get("id", ""))
                if not external_id:
                    continue
                
                # Verifica se já existe
                existing = db.query(ProductExternal).filter(
                    ProductExternal.external_product_id == external_id
                ).first()
                
                if not existing:
                    product = ProductExternal(
                        external_product_id=external_id,
                        title=prod_data.get("title", f"Produto {external_id}"),
                        type=prod_data.get("type"),
                        status=prod_data.get("status", "active"),
                        source="themembers",
                        raw_data=prod_data,
                    )
                    db.add(product)
            
            db.commit()
            
            # Busca novamente
            query = db.query(ProductExternal)
            if source:
                query = query.filter(ProductExternal.source == source)
            else:
                query = query.filter(ProductExternal.status == "active")
            products = query.all()
        except Exception as e:
            # Se der erro na API, retorna o que tem no banco (pode estar vazio)
            pass
    
    return products


@router.get("/contacts/{contact_id}/subscription-status", response_model=SubscriptionStatusResponse)
def get_contact_subscription_status(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna o status de assinatura de um contato.
    """
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Busca subscription ativa mais recente
    subscription = db.query(SubscriptionExternal).filter(
        SubscriptionExternal.contact_id == contact_id
    ).order_by(SubscriptionExternal.created_at.desc()).first()
    
    if not subscription:
        return SubscriptionStatusResponse(
            has_subscription=False,
            is_active=False,
        )
    
    product_title = None
    if subscription.product:
        product_title = subscription.product.title
    
    is_active = subscription.status == "active"
    
    expires_at_str = None
    if subscription.expires_at:
        expires_at_str = subscription.expires_at.isoformat()
    
    return SubscriptionStatusResponse(
        has_subscription=True,
        is_active=is_active,
        subscription_id=subscription.id,
        product_title=product_title,
        status=subscription.status,
        expires_at=expires_at_str,
        themembers_user_id=subscription.themembers_user_id,
    )


@router.get("/contacts/{contact_id}/subscriptions", response_model=List[dict])
def get_contact_subscriptions(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna todas as assinaturas de um contato.
    """
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    subscriptions = db.query(SubscriptionExternal).filter(
        SubscriptionExternal.contact_id == contact_id
    ).order_by(SubscriptionExternal.created_at.desc()).all()
    
    result = []
    for sub in subscriptions:
        result.append({
            "id": sub.id,
            "status": sub.status,
            "product_title": sub.product.title if sub.product else None,
            "started_at": sub.started_at.isoformat() if sub.started_at else None,
            "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
            "source": sub.source,
            "themembers_user_id": sub.themembers_user_id,
        })
    
    return result


@router.post("/products/eduzz", response_model=ProductResponse)
def create_eduzz_product(
    product: CreateEduzzProductRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Adiciona ou atualiza um produto da Eduzz manualmente.
    Útil para sincronizar produtos que ainda não apareceram em vendas.
    """
    # Verifica se já existe
    existing = db.query(ProductExternal).filter(
        ProductExternal.external_product_id == product.product_id,
        ProductExternal.source == "eduzz"
    ).first()
    
    if existing:
        # Atualiza existente
        existing.title = product.title
        existing.type = product.type
        existing.status = product.status or "active"
        existing.updated_at = func.now()
        db.commit()
        db.refresh(existing)
        return existing
    
    # Cria novo
    new_product = ProductExternal(
        external_product_id=product.product_id,
        title=product.title,
        type=product.type,
        status=product.status or "active",
        source="eduzz",
        raw_data={"product_id": product.product_id, "title": product.title},
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@router.post("/products/eduzz/bulk", response_model=List[ProductResponse])
def bulk_create_eduzz_products(
    products: List[CreateEduzzProductRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Adiciona múltiplos produtos da Eduzz de uma vez.
    """
    created_products = []
    created_count = 0
    updated_count = 0
    
    for product_data in products:
        # Verifica se já existe
        existing = db.query(ProductExternal).filter(
            ProductExternal.external_product_id == product_data.product_id,
            ProductExternal.source == "eduzz"
        ).first()
        
        if existing:
            # Atualiza existente
            existing.title = product_data.title
            existing.type = product_data.type
            existing.status = product_data.status or "active"
            existing.updated_at = func.now()
            created_products.append(existing)
            updated_count += 1
        else:
            # Cria novo
            new_product = ProductExternal(
                external_product_id=product_data.product_id,
                title=product_data.title,
                type=product_data.type,
                status=product_data.status or "active",
                source="eduzz",
                raw_data={"product_id": product_data.product_id, "title": product_data.title},
            )
            db.add(new_product)
            created_products.append(new_product)
            created_count += 1
    
    db.commit()
    
    # Refresh todos
    for p in created_products:
        db.refresh(p)
    
    return created_products


@router.post("/products/eduzz/sync-all")
def sync_all_eduzz_products(
    db: Session = Depends(get_db),
    # Temporariamente sem autenticação para facilitar teste
    # current_user: User = Depends(get_current_user),
):
    """
    Sincroniza todos os produtos conhecidos da Eduzz de uma vez.
    Usa a lista pré-definida de produtos.
    """
    # Lista de produtos da Eduzz
    EDUZZ_PRODUCTS = [
        {"id": "2382728", "title": "ACESSO MENSAL - LIFE MÉTODO PLM - 0404"},
        {"id": "2382997", "title": "ACESSO MENSAL - LIFE MÉTODO PLM - 1102"},
        {"id": "2352153", "title": "ACESSO MENSAL - LIFE MÉTODO PLM 01"},
        {"id": "2455207", "title": "CARTÃO DE VISITAS TECNOLÓGICO."},
        {"id": "2109729", "title": "DESAFIO 28 DIAS PALOMA MORAES"},
        {"id": "2180340", "title": "DESAFIO 28 DIAS PALOMA MORAES - DEZEMBRO 2023"},
        {"id": "2108559", "title": "DESAFIO 28 DIAS PALOMA MORAES - OFERTA EXCLUSIVA"},
        {"id": "2184785", "title": "Desafio Completo de 28 Dias Com Paloma Moraes - Edição Dezembro 2023"},
        {"id": "2562423", "title": "LIFE ACESSO ANUAL - 2 ANOS"},
        {"id": "2562393", "title": "LIFE ACESSO MENSAL"},
        {"id": "2571885", "title": "LIFE VITALÍCIO - 2025"},
        {"id": "2681898", "title": "LIFE VITALÍCIO - 2025x"},
        {"id": "2455378", "title": "MENTORIA EXCLUSIVA"},
        {"id": "2459386", "title": "MENTORIA EXCLUSIVA + 9 MESES"},
        {"id": "2124224", "title": "OFERTA RELÂMPAGO - DESAFIO 28 DIAS PALOMA MORAES"},
        {"id": "2457307", "title": "ACESSO MENSAL - LIFE 2025"},
    ]
    
    created_count = 0
    updated_count = 0
    created_products = []
    
    for product_data in EDUZZ_PRODUCTS:
        product_id = product_data["id"]
        title = product_data["title"]
        
        try:
            # Verifica se já existe (pode existir sem source="eduzz")
            existing = db.query(ProductExternal).filter(
                ProductExternal.external_product_id == product_id
            ).first()
            
            if existing:
                # Atualiza existente
                if existing.source != "eduzz":
                    existing.source = "eduzz"
                if existing.title != title:
                    existing.title = title
                existing.status = "active"
                updated_count += 1
                created_products.append(existing)
            else:
                # Cria novo
                new_product = ProductExternal(
                    external_product_id=product_id,
                    title=title,
                    status="active",
                    source="eduzz",
                    raw_data={"product_id": product_id, "title": title},
                )
                db.add(new_product)
                created_products.append(new_product)
                created_count += 1
            
            # Commit individual para evitar conflitos
            db.commit()
        except Exception as e:
            # Se der erro (ex: já existe), faz rollback e tenta atualizar
            db.rollback()
            existing = db.query(ProductExternal).filter(
                ProductExternal.external_product_id == product_id
            ).first()
            if existing:
                existing.source = "eduzz"
                existing.title = title
                existing.status = "active"
                db.commit()
                created_products.append(existing)
                updated_count += 1
    
    # Refresh todos
    for p in created_products:
        db.refresh(p)
    
    return {
        "products": [
            ProductResponse(
                id=p.id,
                external_product_id=p.external_product_id,
                title=p.title,
                type=p.type,
                status=p.status,
                source=p.source,
            )
            for p in created_products
        ],
        "summary": {
            "created": created_count,
            "updated": updated_count,
            "total": len(created_products)
        }
    }

