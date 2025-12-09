# app/routers/analytics.py
"""
Endpoints de analytics e métricas de vendas/conversões.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from pydantic import BaseModel

from ..db import get_db
from ..models import Thread, Contact, SaleEvent, SubscriptionExternal, Message, CartEvent
from ..auth import get_current_user, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsSummary(BaseModel):
    total_threads: int
    total_contacts: int
    total_sales: int
    total_revenue: int  # em centavos
    sales_with_conversation: int
    sales_without_conversation: int
    total_subscriptions: int
    active_subscriptions: int


class SalesByDay(BaseModel):
    date: str
    qtd_vendas: int
    valor_total: int  # em centavos


@router.get("/summary", response_model=AnalyticsSummary)
def get_analytics_summary(
    start_date: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna resumo geral de analytics: conversas, vendas, receita.
    Filtros de período opcionais.
    """
    # Parse dates
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "start_date deve estar no formato YYYY-MM-DD")
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            # Inclui o dia inteiro
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            raise HTTPException(400, "end_date deve estar no formato YYYY-MM-DD")
    
    # Build filters
    thread_filter = []
    sale_filter = []
    contact_filter = []
    
    if start_dt:
        thread_filter.append(Thread.created_at >= start_dt)
        sale_filter.append(SaleEvent.created_at >= start_dt)
        contact_filter.append(Contact.created_at >= start_dt)
    if end_dt:
        thread_filter.append(Thread.created_at <= end_dt)
        sale_filter.append(SaleEvent.created_at <= end_dt)
        contact_filter.append(Contact.created_at <= end_dt)
    
    # Total de threads (conversas)
    query_threads = db.query(func.count(Thread.id))
    if thread_filter:
        query_threads = query_threads.filter(and_(*thread_filter))
    total_threads = query_threads.scalar() or 0
    
    # Total de contatos
    query_contacts = db.query(func.count(Contact.id))
    if contact_filter:
        query_contacts = query_contacts.filter(and_(*contact_filter))
    total_contacts = query_contacts.scalar() or 0
    
    # Total de vendas (sales_events)
    query_sales = db.query(func.count(SaleEvent.id))
    if sale_filter:
        query_sales = query_sales.filter(and_(*sale_filter))
    total_sales = query_sales.scalar() or 0
    
    # Total de receita (soma de value)
    query_revenue = db.query(func.coalesce(func.sum(SaleEvent.value), 0))
    if sale_filter:
        query_revenue = query_revenue.filter(and_(*sale_filter))
    total_revenue = query_revenue.scalar() or 0
    
    # Vendas com conversa (tem contact_id vinculado)
    sales_with_conv_filter = sale_filter + [SaleEvent.contact_id.isnot(None)]
    sales_with_conversation = (
        db.query(func.count(SaleEvent.id))
        .filter(and_(*sales_with_conv_filter))
        .scalar()
    ) or 0
    
    # Vendas sem conversa (sem contact_id)
    sales_without_conversation = total_sales - sales_with_conversation
    
    # Total de assinaturas
    sub_filter = []
    if start_dt:
        sub_filter.append(SubscriptionExternal.created_at >= start_dt)
    if end_dt:
        sub_filter.append(SubscriptionExternal.created_at <= end_dt)
    
    query_subs = db.query(func.count(SubscriptionExternal.id))
    if sub_filter:
        query_subs = query_subs.filter(and_(*sub_filter))
    total_subscriptions = query_subs.scalar() or 0
    
    # Assinaturas ativas
    active_subs_filter = [SubscriptionExternal.status == "active"] + sub_filter
    active_subscriptions = (
        db.query(func.count(SubscriptionExternal.id))
        .filter(and_(*active_subs_filter))
        .scalar()
    ) or 0
    
    return AnalyticsSummary(
        total_threads=total_threads,
        total_contacts=total_contacts,
        total_sales=total_sales,
        total_revenue=int(total_revenue),
        sales_with_conversation=sales_with_conversation,
        sales_without_conversation=sales_without_conversation,
        total_subscriptions=total_subscriptions,
        active_subscriptions=active_subscriptions,
    )


@router.get("/sales-by-day", response_model=list[SalesByDay])
def get_sales_by_day(
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD) - sobrescreve days"),
    end_date: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna vendas agrupadas por dia.
    """
    # Parse dates
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "start_date deve estar no formato YYYY-MM-DD")
    else:
        start_dt = datetime.now() - timedelta(days=days)
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            raise HTTPException(400, "end_date deve estar no formato YYYY-MM-DD")
    
    query = db.query(
        func.date_trunc("day", SaleEvent.created_at).label("day"),
        func.count(SaleEvent.id).label("qtd"),
        func.coalesce(func.sum(SaleEvent.value), 0).label("valor"),
    )
    
    filters = []
    if start_dt:
        filters.append(SaleEvent.created_at >= start_dt)
    if end_dt:
        filters.append(SaleEvent.created_at <= end_dt)
    
    if filters:
        query = query.filter(and_(*filters))
    
    results = (
        query
        .group_by(func.date_trunc("day", SaleEvent.created_at))
        .order_by(func.date_trunc("day", SaleEvent.created_at).asc())
        .all()
    )
    
    return [
        SalesByDay(
            date=r.day.date().isoformat() if hasattr(r.day, "date") else str(r.day)[:10],
            qtd_vendas=int(r.qtd or 0),
            valor_total=int(r.valor or 0),
        )
        for r in results
    ]


@router.get("/contacts/{contact_id}/purchase-status")
def get_contact_purchase_status(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna status de compra do contato:
    - Se fechou o plano
    - Com qual email fechou
    - Qual plano pegou (Mensal/Anual)
    - Data da compra
    - Status da assinatura
    """
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Busca última venda aprovada
    last_sale = (
        db.query(SaleEvent)
        .filter(
            SaleEvent.contact_id == contact_id,
            SaleEvent.event == "sale.approved"
        )
        .order_by(SaleEvent.created_at.desc())
        .first()
    )
    
    # Busca assinatura ativa
    active_subscription = (
        db.query(SubscriptionExternal)
        .filter(
            SubscriptionExternal.contact_id == contact_id,
            SubscriptionExternal.status == "active"
        )
        .order_by(SubscriptionExternal.started_at.desc())
        .first()
    )
    
    return {
        "contact_id": contact_id,
        "contact_email": contact.email,
        "contact_name": contact.name,
        "has_purchased": last_sale is not None,
        "purchase_email": last_sale.buyer_email if last_sale else None,
        "plan_type": last_sale.plan_type if last_sale else None,  # "mensal" ou "anual"
        "purchase_date": last_sale.created_at.isoformat() if last_sale else None,
        "purchase_value": last_sale.value if last_sale else None,  # em centavos
        "order_id": last_sale.order_id if last_sale else None,
        "subscription_active": active_subscription is not None,
        "subscription_status": active_subscription.status if active_subscription else None,
        "subscription_expires_at": active_subscription.expires_at.isoformat() if active_subscription and active_subscription.expires_at else None,
        "post_purchase_message_sent": last_sale.post_purchase_sent if last_sale else False,
    }


@router.get("/contacts/{contact_id}/sales")
def get_contact_sales(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna todas as vendas e assinaturas de um contato.
    """
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Vendas do contato
    sales = (
        db.query(SaleEvent)
        .filter(SaleEvent.contact_id == contact_id)
        .order_by(SaleEvent.created_at.desc())
        .all()
    )
    
    # Assinaturas do contato
    subscriptions = (
        db.query(SubscriptionExternal)
        .filter(SubscriptionExternal.contact_id == contact_id)
        .order_by(SubscriptionExternal.created_at.desc())
        .all()
    )
    
    return {
        "contact_id": contact_id,
        "contact_name": contact.name,
        "contact_email": contact.email,
        "sales": [
            {
                "id": s.id,
                "source": s.source,
                "event": s.event,
                "order_id": s.order_id,
                "value": s.value,
                "plan_type": s.plan_type,  # "mensal" ou "anual"
                "buyer_email": s.buyer_email,
                "product_id": s.product_id,
                "created_at": s.created_at.isoformat(),
                "themembers_user_id": s.themembers_user_id,
                "post_purchase_sent": s.post_purchase_sent,
            }
            for s in sales
        ],
        "subscriptions": [
            {
                "id": sub.id,
                "status": sub.status,
                "product_title": sub.product.title if sub.product else None,
                "started_at": sub.started_at.isoformat() if sub.started_at else None,
                "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
                "source": sub.source,
                "themembers_user_id": sub.themembers_user_id,
            }
            for sub in subscriptions
        ],
        "total_sales": len(sales),
        "total_revenue": sum(s.value or 0 for s in sales),
        "total_subscriptions": len(subscriptions),
        "active_subscriptions": sum(1 for sub in subscriptions if sub.status == "active"),
    }


@router.get("/conversions")
def get_conversions(
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD) - sobrescreve days"),
    end_date: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    max_days_after_last_message: int = Query(30, ge=1, le=365, description="Dias máximos entre última mensagem e venda para contar como conversão"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna métricas de conversão: conversas que viraram vendas.
    
    REGRA DE ATRIBUIÇÃO DE CONVERSÃO:
    - Uma conversa (thread) conta como convertida se:
      1. O contato tem email detectado/informado ANTES da primeira compra
      2. A compra aconteceu até X dias depois da última mensagem da thread
      3. O contato está vinculado à thread (thread_id)
    """
    # Parse dates
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "start_date deve estar no formato YYYY-MM-DD")
    else:
        start_dt = datetime.now() - timedelta(days=days)
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            raise HTTPException(400, "end_date deve estar no formato YYYY-MM-DD")
    
    # Threads criadas no período
    thread_filters = [Thread.created_at >= start_dt]
    if end_dt:
        thread_filters.append(Thread.created_at <= end_dt)
    
    threads_created = (
        db.query(func.count(Thread.id))
        .filter(and_(*thread_filters))
        .scalar()
    ) or 0
    
    # Vendas no período
    sale_filters = [SaleEvent.created_at >= start_dt]
    if end_dt:
        sale_filters.append(SaleEvent.created_at <= end_dt)
    
    sales_in_period = (
        db.query(func.count(SaleEvent.id))
        .filter(and_(*sale_filters))
        .scalar()
    ) or 0
    
    # REGRA DE ATRIBUIÇÃO: Vendas que contam como conversão
    # 1. Venda tem contact_id vinculado
    # 2. Contact tem thread_id
    # 3. Contact tem email ANTES da venda
    # 4. Última mensagem da thread foi até X dias antes da venda
    
    converted_threads = set()
    converted_sales = []
    
    # Busca todas as vendas com contato no período
    sales_with_contact = (
        db.query(SaleEvent)
        .filter(
            and_(
                *sale_filters,
                SaleEvent.contact_id.isnot(None)
            )
        )
        .all()
    )
    
    for sale in sales_with_contact:
        if not sale.contact or not sale.contact.thread_id:
            continue
        
        thread = db.get(Thread, sale.contact.thread_id)
        if not thread:
            continue
        
        # Verifica se contato tem email ANTES da venda
        if not sale.contact.email:
            continue
        
        # Verifica última mensagem da thread
        last_message = (
            db.query(Message)
            .filter(Message.thread_id == thread.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        
        if not last_message:
            continue
        
        # Calcula dias entre última mensagem e venda
        days_between = (sale.created_at - last_message.created_at).days
        
        # Se está dentro do limite, conta como conversão
        if days_between >= 0 and days_between <= max_days_after_last_message:
            converted_threads.add(thread.id)
            converted_sales.append(sale.id)
    
    # Vendas com conversa (simples: tem contact_id)
    sales_with_conversation = (
        db.query(func.count(SaleEvent.id))
        .filter(
            and_(
                *sale_filters,
                SaleEvent.contact_id.isnot(None)
            )
        )
        .scalar()
    ) or 0
    
    # Conversão: threads convertidas / threads criadas
    conversion_rate = (len(converted_threads) / threads_created * 100) if threads_created > 0 else 0
    
    # Por origem
    threads_by_origin = (
        db.query(
            Thread.origin,
            func.count(Thread.id).label("count")
        )
        .filter(and_(*thread_filters))
        .group_by(Thread.origin)
        .all()
    )
    
    # Vendas por origem (via contact -> thread -> origin)
    sales_by_origin = {}
    for sale in sales_with_contact:
        if sale.contact and sale.contact.thread_id:
            thread = db.get(Thread, sale.contact.thread_id)
            if thread and thread.origin:
                origin = thread.origin
                sales_by_origin[origin] = sales_by_origin.get(origin, 0) + 1
    
    return {
        "period_days": days if not start_date else None,
        "start_date": start_dt.isoformat() if start_dt else None,
        "end_date": end_dt.isoformat() if end_dt else None,
        "max_days_after_last_message": max_days_after_last_message,
        "threads_created": threads_created,
        "sales_total": sales_in_period,
        "sales_with_conversation": sales_with_conversation,
        "sales_without_conversation": sales_in_period - sales_with_conversation,
        "converted_threads_count": len(converted_threads),
        "converted_sales_count": len(converted_sales),
        "conversion_rate": round(conversion_rate, 2),
        "threads_by_origin": [
            {"origin": origin or "sem_origem", "count": count}
            for origin, count in threads_by_origin
        ],
        "sales_by_origin": [
            {"origin": origin, "count": count}
            for origin, count in sales_by_origin.items()
        ],
    }


@router.get("/cart-recovery")
def get_cart_recovery(
    days: int = Query(30, ge=1, le=365),
    start_date: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD) - sobrescreve days"),
    end_date: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    recovery_window_days: int = Query(7, ge=1, le=30, description="Janela de dias para considerar recuperação"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna métricas de carrinho abandonado e recuperado.
    
    REGRA DE RECUPERAÇÃO:
    - Carrinho é considerado recuperado se:
      1. Houve evento de abandonment para aquele email/produto
      2. Depois houve sale.approved para o mesmo email/produto
      3. Dentro de X dias (recovery_window_days)
    """
    # Parse dates
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "start_date deve estar no formato YYYY-MM-DD")
    else:
        start_dt = datetime.now() - timedelta(days=days)
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            raise HTTPException(400, "end_date deve estar no formato YYYY-MM-DD")
    
    # Filtros
    cart_filters = [CartEvent.created_at >= start_dt]
    if end_dt:
        cart_filters.append(CartEvent.created_at <= end_dt)
    
    # Carrinhos abandonados
    abandoned = (
        db.query(CartEvent)
        .filter(
            and_(
                *cart_filters,
                CartEvent.event_type == "abandonment"
            )
        )
        .all()
    )
    
    # Carrinhos recuperados (já marcados)
    recovered = (
        db.query(CartEvent)
        .filter(
            and_(
                *cart_filters,
                CartEvent.recovered == True
            )
        )
        .all()
    )
    
    # Processa recuperações: busca abandonments que viraram vendas
    recovered_count = 0
    recovered_value = 0
    
    for abandonment in abandoned:
        # Busca se houve venda para o mesmo email/produto depois
        sale = (
            db.query(SaleEvent)
            .filter(
                SaleEvent.buyer_email == abandonment.email,
                SaleEvent.created_at > abandonment.created_at,
                SaleEvent.created_at <= abandonment.created_at + timedelta(days=recovery_window_days)
            )
            .first()
        )
        
        if sale:
            # Marca como recuperado se ainda não estiver
            if not abandonment.recovered:
                abandonment.recovered = True
                abandonment.recovered_at = sale.created_at
                abandonment.order_id = sale.order_id
                db.add(abandonment)
            
            recovered_count += 1
            recovered_value += sale.value or 0
    
    db.commit()
    
    # Total de abandonados
    total_abandoned = len(abandoned)
    
    # Taxa de recuperação
    recovery_rate = (recovered_count / total_abandoned * 100) if total_abandoned > 0 else 0
    
    return {
        "period_days": days if not start_date else None,
        "start_date": start_dt.isoformat() if start_dt else None,
        "end_date": end_dt.isoformat() if end_dt else None,
        "recovery_window_days": recovery_window_days,
        "total_abandoned": total_abandoned,
        "total_recovered": recovered_count,
        "recovery_rate": round(recovery_rate, 2),
        "recovered_value": recovered_value,  # em centavos
        "abandoned_value": sum(c.value or 0 for c in abandoned),  # em centavos
    }

