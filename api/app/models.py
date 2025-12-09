# app/models.py
from __future__ import annotations

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import JSON

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    threads = relationship("Thread", back_populates="user", cascade="all, delete-orphan")


class Thread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True)
    external_thread_id = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    human_takeover = Column(Boolean, default=False, nullable=False)
    external_user_phone = Column(String(64), nullable=True)

    origin = Column(String(64), nullable=True)
    lead_level = Column(String(32), nullable=True)
    lead_score = Column(Integer, nullable=True)
    lead_stage = Column(String(64), nullable=True, index=True)  # Etapa atual do funil

    # ⚠️ Coluna real no banco: "meta"
    meta = Column(JSON, name="meta", nullable=True)

    user = relationship("User", back_populates="threads")
    messages = relationship("Message", back_populates="thread", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_human = Column(Boolean, default=False, nullable=False)  # Para mensagens enviadas por humanos

    thread = relationship("Thread", back_populates="messages")


# ================== CRM Models ==================
class Contact(Base):
    """Contato/CRM vinculado a uma thread"""
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True, index=True)  # Opcional: contatos podem vir de vendas sem conversa (unique via índice parcial)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Opcional: pode ser criado por webhook
    
    # Dados básicos
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(64), nullable=True, index=True)
    company = Column(String(255), nullable=True)
    
    # Integração The Members
    themembers_user_id = Column(String(64), nullable=True, index=True)  # ID do usuário na The Members
    
    # Métricas calculadas (cache)
    total_orders = Column(Integer, default=0, nullable=False)
    total_spent = Column(Integer, default=0, nullable=False)  # em centavos
    average_ticket = Column(Integer, nullable=True)  # em centavos
    most_bought_products = Column(JSON, nullable=True)  # [{"product": "Cartão", "count": 5}]
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_interaction_at = Column(DateTime, nullable=True)

    thread = relationship("Thread", backref="contact")
    tags = relationship("ContactTag", back_populates="contact", cascade="all, delete-orphan")
    notes = relationship("ContactNote", back_populates="contact", cascade="all, delete-orphan", order_by="ContactNote.created_at.desc()")
    reminders = relationship("ContactReminder", back_populates="contact", cascade="all, delete-orphan")


class ContactTag(Base):
    """Tags personalizadas para contatos"""
    __tablename__ = "contact_tags"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, index=True)
    tag = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    contact = relationship("Contact", back_populates="tags")


class ContactNote(Base):
    """Notas internas sobre contatos"""
    __tablename__ = "contact_notes"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    contact = relationship("Contact", back_populates="notes")


class ContactReminder(Base):
    """Lembretes de follow-up"""
    __tablename__ = "contact_reminders"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    due_date = Column(DateTime, nullable=False, index=True)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    contact = relationship("Contact", back_populates="reminders")


# ================== Billing / The Members Models ==================
class ProductExternal(Base):
    """Produtos externos (Eduzz, The Members, etc.)"""
    __tablename__ = "products_external"

    id = Column(Integer, primary_key=True)
    external_product_id = Column(String(64), unique=True, nullable=False, index=True)  # ID na plataforma externa
    title = Column(String(255), nullable=False)
    type = Column(String(32), nullable=True)  # "recurring", "one_time", "lifetime"
    status = Column(String(32), nullable=True)  # "active", "inactive", "cancelled"
    source = Column(String(32), nullable=True, index=True)  # "eduzz", "themembers", "manual"
    raw_data = Column(JSON, nullable=True)  # Dados completos da API
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    subscriptions = relationship("SubscriptionExternal", back_populates="product")


class SubscriptionExternal(Base):
    """Assinaturas da The Members vinculadas a contatos"""
    __tablename__ = "subscriptions_external"

    id = Column(Integer, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    themembers_user_id = Column(String(64), nullable=False, index=True)
    product_external_id = Column(Integer, ForeignKey("products_external.id"), nullable=True)
    
    status = Column(String(32), nullable=False)  # "active", "inactive", "canceled", "expired"
    started_at = Column(DateTime, nullable=True)
    last_payment_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    source = Column(String(32), nullable=True)  # "eduzz", "manual", etc.
    raw_data = Column(JSON, nullable=True)  # Payload completo da API
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    contact = relationship("Contact", backref="subscriptions")
    product = relationship("ProductExternal", back_populates="subscriptions")


class SaleEvent(Base):
    """Histórico de eventos de venda (Eduzz, etc)"""
    __tablename__ = "sales_events"

    id = Column(Integer, primary_key=True)
    source = Column(String(32), nullable=False, index=True)  # "eduzz", "manual", etc.
    event = Column(String(64), nullable=False, index=True)  # "sale.approved", "refund", etc.
    event_id = Column(String(128), nullable=True, index=True)  # ID do evento na plataforma
    order_id = Column(String(128), nullable=True, index=True)
    
    buyer_email = Column(String(255), nullable=False, index=True)
    buyer_name = Column(String(255), nullable=True)
    value = Column(Integer, nullable=True)  # em centavos
    product_id = Column(String(64), nullable=True)  # ID do produto na plataforma (Eduzz)
    plan_type = Column(String(16), nullable=True, index=True)  # "mensal" ou "anual"
    
    themembers_user_id = Column(String(64), nullable=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    post_purchase_sent = Column(Boolean, default=False, nullable=False)  # True se mensagem pós-compra foi enviada
    
    raw_payload = Column(JSON, nullable=True)  # Payload completo do webhook
    
    created_at = Column(DateTime, server_default=func.now(), index=True)

    contact = relationship("Contact", backref="sales_events")


class CartEvent(Base):
    """Eventos de carrinho (abandonamento e recuperação)"""
    __tablename__ = "cart_events"
    
    id = Column(Integer, primary_key=True)
    source = Column(String(64), nullable=False, index=True)  # ex: "eduzz"
    event_type = Column(String(64), nullable=False, index=True)  # "abandonment" ou "sale"
    email = Column(String(255), nullable=False, index=True)
    cart_id = Column(String(255), nullable=True, index=True)
    order_id = Column(String(255), nullable=True, index=True)  # Preenchido quando vira venda
    product_id = Column(String(255), nullable=True)
    value = Column(Integer, nullable=True)  # em centavos
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True, index=True)
    recovered = Column(Boolean, default=False, nullable=False)  # True se foi recuperado
    recovered_at = Column(DateTime, nullable=True)  # Data da recuperação
    raw_data = Column(JSON, nullable=True)  # Payload bruto do webhook
    created_at = Column(DateTime, server_default=func.now(), index=True)

    contact = relationship("Contact", backref="cart_events")
