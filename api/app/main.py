# app/main.py
import os
import json
import jwt
import asyncio
import logging
from typing import Dict, Set, Optional, List

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Query,
    WebSocket,
    WebSocketDisconnect,
    Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pathlib import Path
from typing import Optional
from fastapi.exception_handlers import http_exception_handler
from starlette.status import HTTP_401_UNAUTHORIZED

from sqlalchemy import func, case, select, text
from sqlalchemy.orm import Session

from pydantic import BaseModel

from .db import get_db, engine, SessionLocal
from .models import (
    Base, User, Thread, Message, Contact, ContactTag, ContactNote, ContactReminder,
    ProductExternal, SubscriptionExternal, SaleEvent
)
from .schemas import (
    LoginRequest,
    LoginResponse,
    MessageCreate,
    MessageRead,
    ThreadCreate,
    ThreadUpdate,
)
from .auth import create_token, verify_password, hash_password, get_current_user

from .services.llm_service import run_llm
from .services.response_processor import process_llm_response
from .providers import twilio as twilio_provider
from .providers import meta as meta_provider
from .realtime import hub

# -----------------------------
# App & CORS
# -----------------------------
Base.metadata.create_all(bind=engine)
app = FastAPI(title=os.getenv("APP_NAME", "MVP Chat"))

_raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.getLogger("uvicorn.error").info(f"[BOOT] CORS allow_origins = {ALLOWED_ORIGINS}")

@app.get("/debug/cors")
def debug_cors():
    return {"ok": True, "origins": ALLOWED_ORIGINS}

# -----------------------------
# Servir arquivos estáticos (áudios, templates, imagens)
# -----------------------------
# Caminho relativo ao diretório do projeto (não ao container)
FRONTEND_PUBLIC = Path(__file__).parent.parent.parent.parent / "frontend" / "public"

# Fallback: tenta caminhos alternativos (incluindo volume montado no Docker)
FALLBACK_PATHS = [
    Path("/app/public"),  # Volume montado no Docker (prioridade) - frontend/public -> /app/public
    Path("/app/frontend/public"),  # Alternativa
    FRONTEND_PUBLIC,  # Caminho relativo local
    Path("/app/../frontend/public"),  # Docker alternativo
    Path.cwd() / "frontend" / "public",  # Caminho atual
]

def _find_file(relative_path: str) -> Optional[Path]:
    """Encontra arquivo em múltiplos caminhos possíveis"""
    for base in FALLBACK_PATHS:
        file_path = base / relative_path
        if file_path.exists() and file_path.is_file():
            return file_path
    return None

@app.get("/audios/{path:path}")
async def serve_audio(path: str):
    """Serve arquivos de áudio do frontend/public/audios/"""
    audio_file = _find_file(f"audios/{path}")
    if audio_file:
        print(f"[SERVE_AUDIO] ✅ Servindo: {audio_file}")
        # Detecta tipo MIME correto baseado na extensão
        mime_type = "audio/ogg"  # Padrão para OGG/OPUS
        if audio_file.suffix.lower() == ".opus":
            mime_type = "audio/ogg"  # OPUS usa container OGG
        elif audio_file.suffix.lower() == ".ogg":
            mime_type = "audio/ogg"
        elif audio_file.suffix.lower() == ".mp3":
            mime_type = "audio/mpeg"
        elif audio_file.suffix.lower() == ".wav":
            mime_type = "audio/wav"
        
        return FileResponse(
            audio_file,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{audio_file.name}"',
                "Access-Control-Allow-Origin": "*",  # Permite CORS para Twilio
                "Content-Type": mime_type,  # Garante content-type explícito
            }
        )
    print(f"[SERVE_AUDIO] ❌ Arquivo não encontrado: audios/{path}")
    print(f"[SERVE_AUDIO] Tentou caminhos: {[str(p / f'audios/{path}') for p in FALLBACK_PATHS]}")
    raise HTTPException(404, f"Audio file not found: {path}")

@app.get("/images/{path:path}")
async def serve_image(path: str):
    """Serve arquivos de imagem do frontend/public/images/"""
    image_file = _find_file(f"images/{path}")
    if image_file:
        # Detecta tipo MIME
        mime_type = "image/jpeg"
        if image_file.suffix.lower() in [".png"]:
            mime_type = "image/png"
        elif image_file.suffix.lower() in [".webp"]:
            mime_type = "image/webp"
        return FileResponse(
            image_file,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{image_file.name}"',
                "Access-Control-Allow-Origin": "*",  # Permite CORS para Twilio
            }
        )
    raise HTTPException(404, f"Image file not found: {path}")

# -----------------------------
# Exception Handlers
# -----------------------------
from fastapi import HTTPException as FastHTTPException

@app.exception_handler(FastHTTPException)
async def http_exc_handler(request: Request, exc: FastHTTPException):
    response = await http_exception_handler(request, exc)
    # Adiciona CORS headers mesmo em caso de erro HTTP
    origin = request.headers.get("origin")
    if origin and origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    import traceback
    logging.getLogger("uvicorn.error").exception(f"[ERROR] Unhandled exception: {exc}")
    traceback.print_exc()
    # Retorna resposta com CORS headers mesmo em caso de erro
    origin = request.headers.get("origin")
    if origin and origin in ALLOWED_ORIGINS:
        cors_origin = origin
    else:
        cors_origin = ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*"
    
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if os.getenv("DEBUG") else "internal_error"},
        headers={
            "Access-Control-Allow-Origin": cors_origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.get("/health")
def health():
    return {"ok": True}

# ------- Routers extras -------
from app.routers import takeover
from app.routers import tasks
from app.routers import crm
from app.routers import eduzz
from app.routers import billing
from app.routers import integrations
from app.routers import analytics
app.include_router(takeover.router)
app.include_router(tasks.router)
app.include_router(crm.router)
app.include_router(eduzz.router)
app.include_router(billing.router)
app.include_router(integrations.router)
app.include_router(analytics.router)
# ---------------------------------------------

# -----------------------------
# Seed mínimo + migração leve
# -----------------------------
def _fix_threads_meta(db: Session) -> None:
    """
    Garante a coluna threads.meta (JSONB) e migra de 'metadata' -> 'meta' se existir.
    Idempotente: pode rodar várias vezes.
    """
    # 1) cria coluna meta
    db.execute(text("ALTER TABLE threads ADD COLUMN IF NOT EXISTS meta JSONB;"))

    # 2) migra de metadata -> meta (se existir)
    db.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'threads' AND column_name = 'metadata'
            ) THEN
                UPDATE threads SET meta = COALESCE(meta, metadata);
            END IF;
        END $$;
    """))

    # 3) remove a antiga 'metadata' (opcional/seguro)
    db.execute(text("ALTER TABLE threads DROP COLUMN IF EXISTS metadata;"))
    db.commit()

def _fix_messages_is_human(db: Session) -> None:
    """
    Garante a coluna messages.is_human (Boolean) com default False.
    Idempotente: pode rodar várias vezes.
    """
    # 1) cria coluna se não existir
    db.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'messages' AND column_name = 'is_human'
            ) THEN
                ALTER TABLE messages ADD COLUMN is_human BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END $$;
    """))
    
    # 2) atualiza registros existentes que possam ter NULL
    db.execute(text("UPDATE messages SET is_human = FALSE WHERE is_human IS NULL;"))
    
    # 3) garante que a coluna seja NOT NULL (se ainda não for)
    db.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'messages' 
                AND column_name = 'is_human' 
                AND is_nullable = 'YES'
            ) THEN
                ALTER TABLE messages ALTER COLUMN is_human SET NOT NULL;
                ALTER TABLE messages ALTER COLUMN is_human SET DEFAULT FALSE;
            END IF;
        END $$;
    """))
    db.commit()

def _fix_threads_lead_stage(db: Session) -> None:
    """
    Garante a coluna threads.lead_stage (String) para armazenar etapa do funil.
    Idempotente: pode rodar várias vezes.
    """
    db.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'threads' AND column_name = 'lead_stage'
            ) THEN
                ALTER TABLE threads ADD COLUMN lead_stage VARCHAR(64);
                CREATE INDEX IF NOT EXISTS ix_threads_lead_stage ON threads(lead_stage);
            END IF;
        END $$;
    """))
    db.commit()

def _fix_contacts_themembers_fields(db: Session) -> None:
    """
    Garante que a tabela contacts tenha os campos themembers_user_id.
    Idempotente: pode rodar várias vezes.
    """
    db.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'themembers_user_id'
            ) THEN
                ALTER TABLE contacts ADD COLUMN themembers_user_id VARCHAR(64);
                CREATE INDEX IF NOT EXISTS ix_contacts_themembers_user_id ON contacts(themembers_user_id);
            END IF;
        END $$;
    """))
    db.commit()

def _create_billing_tables(db: Session) -> None:
    """Cria tabelas de billing (products_external, subscriptions_external, sales_events, cart_events)"""
    """
    Cria tabelas de billing (products_external, subscriptions_external, sales_events).
    Idempotente: pode rodar várias vezes.
    """
    # products_external
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS products_external (
            id SERIAL PRIMARY KEY,
            external_product_id VARCHAR(64) UNIQUE NOT NULL,
            title VARCHAR(255) NOT NULL,
            type VARCHAR(32),
            status VARCHAR(32),
            source VARCHAR(32),
            raw_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_products_external_external_id ON products_external(external_product_id);"))
    
    # Migração: adiciona campo source se não existir (ANTES de criar índice)
    try:
        db.execute(text("ALTER TABLE products_external ADD COLUMN IF NOT EXISTS source VARCHAR(32);"))
        db.commit()
        # Cria índice após adicionar a coluna
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_products_external_source ON products_external(source);"))
        db.commit()
    except Exception as e:
        # Se der erro, tenta criar o índice mesmo assim (pode já existir)
        try:
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_products_external_source ON products_external(source);"))
            db.commit()
        except:
            pass
    
    # subscriptions_external
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS subscriptions_external (
            id SERIAL PRIMARY KEY,
            contact_id INTEGER REFERENCES contacts(id),
            themembers_user_id VARCHAR(64) NOT NULL,
            product_external_id INTEGER REFERENCES products_external(id),
            status VARCHAR(32) NOT NULL,
            started_at TIMESTAMP,
            last_payment_at TIMESTAMP,
            expires_at TIMESTAMP,
            source VARCHAR(32),
            raw_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_subscriptions_external_contact_id ON subscriptions_external(contact_id);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_subscriptions_external_user_id ON subscriptions_external(themembers_user_id);"))
    
    # sales_events
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS sales_events (
            id SERIAL PRIMARY KEY,
            source VARCHAR(32) NOT NULL,
            event VARCHAR(64) NOT NULL,
            event_id VARCHAR(128),
            order_id VARCHAR(128),
            buyer_email VARCHAR(255) NOT NULL,
            buyer_name VARCHAR(255),
            value INTEGER,
            product_id VARCHAR(64),
            plan_type VARCHAR(16),
            themembers_user_id VARCHAR(64),
            contact_id INTEGER REFERENCES contacts(id),
            post_purchase_sent BOOLEAN DEFAULT FALSE NOT NULL,
            raw_payload JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_events_source ON sales_events(source);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_events_event ON sales_events(event);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_events_buyer_email ON sales_events(buyer_email);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_events_contact_id ON sales_events(contact_id);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_events_created_at ON sales_events(created_at);"))
    
    # Migração: adiciona campos novos se não existirem (ANTES de criar índices)
    try:
        db.execute(text("ALTER TABLE sales_events ADD COLUMN IF NOT EXISTS plan_type VARCHAR(16);"))
        db.execute(text("ALTER TABLE sales_events ADD COLUMN IF NOT EXISTS post_purchase_sent BOOLEAN DEFAULT FALSE NOT NULL;"))
        db.commit()
        # Cria índice após adicionar a coluna
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_sales_events_plan_type ON sales_events(plan_type);"))
        db.commit()
    except Exception as e:
        # Ignora erro se as colunas já existirem
        pass
    
    # cart_events
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS cart_events (
            id SERIAL PRIMARY KEY,
            source VARCHAR(64) NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            email VARCHAR(255) NOT NULL,
            cart_id VARCHAR(255),
            order_id VARCHAR(255),
            product_id VARCHAR(255),
            value INTEGER,
            contact_id INTEGER REFERENCES contacts(id),
            recovered BOOLEAN DEFAULT FALSE NOT NULL,
            recovered_at TIMESTAMP,
            raw_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_cart_events_source ON cart_events(source);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_cart_events_event_type ON cart_events(event_type);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_cart_events_email ON cart_events(email);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_cart_events_cart_id ON cart_events(cart_id);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_cart_events_contact_id ON cart_events(contact_id);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_cart_events_created_at ON cart_events(created_at);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_cart_events_recovered ON cart_events(recovered);"))
    
    db.commit()

def _fix_contacts_table(db: Session) -> None:
    """
    Garante que a tabela contacts tenha todas as colunas necessárias.
    Idempotente: pode rodar várias vezes.
    """
    # Verifica se a tabela contacts existe
    table_exists = db.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'contacts'
        );
    """)).scalar()
    
    if not table_exists:
        # Se a tabela não existe, cria via SQLAlchemy primeiro
        from .models import Base, Contact
        from .db import engine
        # Cria a tabela se não existir
        Contact.__table__.create(engine, checkfirst=True)
        db.commit()
        # Agora continua para adicionar as colunas que podem estar faltando
        return
    
    # Torna thread_id e user_id nullable (contatos podem vir de vendas sem conversa)
    db.execute(text("""
        DO $$
        BEGIN
            -- Remove constraint unique de thread_id se existir (permite múltiplos NULLs)
            IF EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'contacts_thread_id_key'
            ) THEN
                ALTER TABLE contacts DROP CONSTRAINT contacts_thread_id_key;
            END IF;
            
            -- Torna thread_id nullable se não for
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' 
                  AND table_name = 'contacts' 
                  AND column_name = 'thread_id'
                  AND is_nullable = 'NO'
            ) THEN
                ALTER TABLE contacts ALTER COLUMN thread_id DROP NOT NULL;
            END IF;
            
            -- Torna user_id nullable se não for
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' 
                  AND table_name = 'contacts' 
                  AND column_name = 'user_id'
                  AND is_nullable = 'NO'
            ) THEN
                ALTER TABLE contacts ALTER COLUMN user_id DROP NOT NULL;
            END IF;
            
            -- Cria índice parcial único apenas para thread_id não-nulo
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'ix_contacts_thread_id_unique'
            ) THEN
                CREATE UNIQUE INDEX ix_contacts_thread_id_unique 
                ON contacts(thread_id) 
                WHERE thread_id IS NOT NULL;
            END IF;
        END $$;
    """))
    db.commit()
    
    # Verifica se existe a coluna owner_user_id (antiga) e a remove ou mapeia para user_id
    owner_user_id_exists = db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'contacts' AND column_name = 'owner_user_id'
        );
    """)).scalar()
    
    if owner_user_id_exists:
        # Se owner_user_id existe, migra os dados para user_id e remove owner_user_id
        db.execute(text("""
            DO $$
            BEGIN
                -- Se user_id não existe, cria
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'contacts' AND column_name = 'user_id'
                ) THEN
                    ALTER TABLE contacts ADD COLUMN user_id INTEGER;
                END IF;
                
                -- Copia dados de owner_user_id para user_id onde user_id é NULL
                UPDATE contacts SET user_id = owner_user_id WHERE user_id IS NULL AND owner_user_id IS NOT NULL;
                
                -- Remove a coluna owner_user_id
                ALTER TABLE contacts DROP COLUMN IF EXISTS owner_user_id;
            END $$;
        """))
        db.commit()
    
    # Remove constraints NOT NULL de colunas antigas que não usamos mais
    # (stage, heat, owner_user_id, etc) e adiciona valores padrão se necessário
    db.execute(text("""
        DO $$
        DECLARE
            col_record RECORD;
        BEGIN
            -- Lista de colunas que devem ser nullable (não estão no modelo atual)
            FOR col_record IN 
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' 
                  AND table_name = 'contacts'
                  AND column_name NOT IN (
                    'id', 'thread_id', 'user_id', 'name', 'email', 'phone', 'company',
                    'total_orders', 'total_spent', 'average_ticket', 'most_bought_products',
                    'created_at', 'updated_at', 'last_interaction_at', 'themembers_user_id'
                  )
                  AND is_nullable = 'NO'
            LOOP
                BEGIN
                    -- Torna a coluna nullable
                    EXECUTE format('ALTER TABLE contacts ALTER COLUMN %I DROP NOT NULL', col_record.column_name);
                EXCEPTION WHEN OTHERS THEN
                    -- Se der erro, ignora e continua
                    NULL;
                END;
            END LOOP;
        END $$;
    """))
    db.commit()
    
    # 1) Garante que thread_id existe
    db.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'thread_id'
            ) THEN
                ALTER TABLE contacts ADD COLUMN thread_id INTEGER;
                -- Adiciona foreign key se possível
                BEGIN
                    ALTER TABLE contacts ADD CONSTRAINT contacts_thread_id_fkey 
                    FOREIGN KEY (thread_id) REFERENCES threads(id);
                EXCEPTION WHEN OTHERS THEN
                    -- Se der erro (ex: constraint já existe), ignora
                    NULL;
                END;
                -- Adiciona índice
                CREATE INDEX IF NOT EXISTS ix_contacts_thread_id ON contacts(thread_id);
            END IF;
        END $$;
    """))
    
    # 2) Garante outras colunas importantes se não existirem
    db.execute(text("""
        DO $$
        BEGIN
            -- user_id
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'user_id'
            ) THEN
                ALTER TABLE contacts ADD COLUMN user_id INTEGER;
                CREATE INDEX IF NOT EXISTS ix_contacts_user_id ON contacts(user_id);
            END IF;
            
            -- name
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'name'
            ) THEN
                ALTER TABLE contacts ADD COLUMN name VARCHAR(255);
            END IF;
            
            -- email
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'email'
            ) THEN
                ALTER TABLE contacts ADD COLUMN email VARCHAR(255);
                CREATE INDEX IF NOT EXISTS ix_contacts_email ON contacts(email);
            END IF;
            
            -- phone
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'phone'
            ) THEN
                ALTER TABLE contacts ADD COLUMN phone VARCHAR(64);
                CREATE INDEX IF NOT EXISTS ix_contacts_phone ON contacts(phone);
            END IF;
            
            -- company
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'company'
            ) THEN
                ALTER TABLE contacts ADD COLUMN company VARCHAR(255);
            END IF;
            
            -- total_orders
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'total_orders'
            ) THEN
                ALTER TABLE contacts ADD COLUMN total_orders INTEGER NOT NULL DEFAULT 0;
            END IF;
            
            -- total_spent
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'total_spent'
            ) THEN
                ALTER TABLE contacts ADD COLUMN total_spent INTEGER NOT NULL DEFAULT 0;
            END IF;
            
            -- created_at
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'created_at'
            ) THEN
                ALTER TABLE contacts ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            END IF;
            
            -- updated_at
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'updated_at'
            ) THEN
                ALTER TABLE contacts ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            END IF;
            
            -- average_ticket
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'average_ticket'
            ) THEN
                ALTER TABLE contacts ADD COLUMN average_ticket INTEGER;
            END IF;
            
            -- most_bought_products
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'most_bought_products'
            ) THEN
                ALTER TABLE contacts ADD COLUMN most_bought_products JSONB;
            END IF;
            
            -- last_interaction_at
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'contacts' AND column_name = 'last_interaction_at'
            ) THEN
                ALTER TABLE contacts ADD COLUMN last_interaction_at TIMESTAMP;
            END IF;
        END $$;
    """))
    
    db.commit()

def _update_existing_contacts(db: Session) -> None:
    """
    Atualiza contatos existentes que têm nomes genéricos (ex: "WhatsApp 1114")
    ou que não têm nome, tentando extrair um nome melhor do thread.
    Também cria contatos para threads que ainda não têm.
    """
    from .models import Contact, Thread
    
    # Primeiro, cria contatos para threads que não têm
    # Busca todos os threads
    all_threads = db.query(Thread).all()
    # Busca todos os thread_ids que já têm contato
    existing_contact_thread_ids = {c.thread_id for c in db.query(Contact.thread_id).all()}
    # Filtra threads sem contato
    threads_without_contacts = [t for t in all_threads if t.id not in existing_contact_thread_ids]
    created_count = 0
    for thread in threads_without_contacts:
        name = None
        
        # Tenta extrair do metadata
        if hasattr(thread, 'meta') and thread.meta:
            if isinstance(thread.meta, dict):
                name = thread.meta.get('name') or thread.meta.get('profile_name') or thread.meta.get('display_name')
            elif isinstance(thread.meta, str):
                try:
                    import json
                    meta_dict = json.loads(thread.meta)
                    name = meta_dict.get('name') or meta_dict.get('profile_name') or meta_dict.get('display_name')
                except:
                    pass
        
        # Se não encontrou no metadata, tenta do título
        if not name and thread.title and not thread.title.startswith("WhatsApp"):
            name = thread.title
        
        # Se ainda não tem nome, usa o número do telefone
        if not name and thread.external_user_phone:
            phone_clean = thread.external_user_phone.replace("whatsapp:", "").replace("+", "").strip()
            if phone_clean:
                name = f"Contato {phone_clean[-4:]}"
        
        contact = Contact(
            thread_id=thread.id,
            user_id=thread.user_id,
            phone=thread.external_user_phone,
            name=name or f"Contato {thread.id}",
        )
        db.add(contact)
        created_count += 1
    
    if created_count > 0:
        db.commit()
        print(f"✅ Criados {created_count} contatos para threads sem contato")
    
    # Agora atualiza contatos existentes que têm nomes genéricos
    contacts = db.query(Contact).all()
    updated_count = 0
    for contact in contacts:
        thread = db.get(Thread, contact.thread_id)
        if not thread:
            continue
        
        # Verifica se o nome precisa ser atualizado
        needs_update = False
        new_name = None
        
        # Se o contato não tem nome ou tem um nome genérico
        if not contact.name or contact.name.startswith("WhatsApp") or (contact.name.startswith("Contato ") and len(contact.name) < 15):
            needs_update = True
        
        if needs_update:
            # Tenta extrair do metadata
            if hasattr(thread, 'meta') and thread.meta:
                if isinstance(thread.meta, dict):
                    new_name = thread.meta.get('name') or thread.meta.get('profile_name') or thread.meta.get('display_name')
                elif isinstance(thread.meta, str):
                    try:
                        import json
                        meta_dict = json.loads(thread.meta)
                        new_name = meta_dict.get('name') or meta_dict.get('profile_name') or meta_dict.get('display_name')
                    except:
                        pass
            
            # Se não encontrou no metadata, tenta do título
            if not new_name and thread.title:
                if not thread.title.startswith("WhatsApp"):
                    new_name = thread.title
            
            # Se ainda não tem nome, usa o número do telefone de forma mais amigável
            if not new_name and thread.external_user_phone:
                phone_clean = thread.external_user_phone.replace("whatsapp:", "").replace("+", "").strip()
                if phone_clean:
                    # Formata o telefone de forma mais amigável (ex: +55 11 98765-4321)
                    if len(phone_clean) >= 10:
                        # Tenta formatar como telefone brasileiro
                        if phone_clean.startswith("55") and len(phone_clean) == 13:
                            # +55 DDD NNNNN-NNNN
                            ddd = phone_clean[2:4]
                            num = phone_clean[4:]
                            if len(num) == 9:
                                new_name = f"+55 {ddd} {num[:5]}-{num[5:]}"
                            else:
                                new_name = f"+55 {ddd} {num}"
                        else:
                            new_name = f"Contato {phone_clean[-4:]}"
                    else:
                        new_name = f"Contato {phone_clean[-4:]}"
            
            # Atualiza o contato se encontrou um nome melhor
            if new_name and new_name != contact.name:
                contact.name = new_name
                updated_count += 1
    
    if updated_count > 0:
        db.commit()
        print(f"✅ Atualizados {updated_count} contatos com nomes melhores")

@app.on_event("startup")
def seed_user_and_migrate():
    db = SessionLocal()
    try:
        # Migrações
        _fix_threads_meta(db)
        _fix_messages_is_human(db)
        _fix_threads_lead_stage(db)  # Garante coluna lead_stage
        _fix_contacts_table(db)  # Garante que contacts tenha todas as colunas
        _fix_contacts_themembers_fields(db)  # Adiciona themembers_user_id em contacts
        _create_billing_tables(db)  # Cria tabelas de billing
        _update_existing_contacts(db)  # Atualiza contatos existentes
        
        # seed - cria usuário Admin se não existir
        admin_user = db.execute(
            select(User).where(User.email == "Admin")
        ).scalar_one_or_none()
        if not admin_user:
            admin_user = User(email="Admin", password_hash=hash_password("Admin"))
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
        
        # Migra threads do usuário antigo (dev@local.com) para Admin
        old_user = db.execute(
            select(User).where(User.email == "dev@local.com")
        ).scalar_one_or_none()
        
        if old_user and old_user.id != admin_user.id:
            # Migra threads
            threads_to_migrate = db.query(Thread).filter(Thread.user_id == old_user.id).all()
            if threads_to_migrate:
                for thread in threads_to_migrate:
                    thread.user_id = admin_user.id
                db.commit()
                print(f"✅ Migradas {len(threads_to_migrate)} threads de {old_user.email} para Admin")
            
            # Migra contacts
            contacts_to_migrate = db.query(Contact).filter(Contact.user_id == old_user.id).all()
            if contacts_to_migrate:
                for contact in contacts_to_migrate:
                    contact.user_id = admin_user.id
                db.commit()
                print(f"✅ Migrados {len(contacts_to_migrate)} contatos de {old_user.email} para Admin")
        
        # migração leve
        _fix_threads_meta(db)
    finally:
        db.close()

# Endpoint manual caso queira rodar o fix on-demand
@app.get("/debug/fix-threads-meta")
def debug_fix_threads_meta(db: Session = Depends(get_db)):
    try:
        _fix_threads_meta(db)
        return {"ok": True, "fixed": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"fix_failed: {e}")

@app.get("/debug/fix-contacts-table")
def debug_fix_contacts_table(db: Session = Depends(get_db)):
    """Endpoint para executar migração de contacts manualmente"""
    try:
        _fix_contacts_table(db)
        return {"ok": True, "fixed": True, "message": "Tabela contacts migrada com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"fix_failed: {e}")

@app.get("/debug/update-contacts-names")
def debug_update_contacts_names(db: Session = Depends(get_db)):
    """Endpoint para atualizar nomes de contatos existentes manualmente"""
    try:
        _update_existing_contacts(db)
        return {"ok": True, "message": "Contatos atualizados com sucesso"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"update_failed: {e}")

# -----------------------------
# Auth
# -----------------------------
@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    u = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return LoginResponse(token=create_token(u.id))

class MeOut(BaseModel):
    id: int
    email: str

@app.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(id=user.id, email=user.email)

# -----------------------------
# SSE infra (tempo real)
# -----------------------------
SUBS: Dict[int, Set[asyncio.Queue]] = {}
SUBS_LOCK = asyncio.Lock()

async def _subscribe(thread_id: int) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    async with SUBS_LOCK:
        SUBS.setdefault(thread_id, set()).add(q)
    return q

async def _unsubscribe(thread_id: int, q: asyncio.Queue):
    async with SUBS_LOCK:
        if thread_id in SUBS and q in SUBS[thread_id]:
            SUBS[thread_id].remove(q)
            if not SUBS[thread_id]:
                SUBS.pop(thread_id, None)

async def _broadcast(thread_id: int, payload: dict):
    async with SUBS_LOCK:
        queues = list(SUBS.get(thread_id, set()))
    for q in queues:
        try:
            await q.put(payload)
        except Exception:
            pass
    try:
        await hub.broadcast(str(thread_id), payload)
    except Exception:
        pass

# tenta usar decode_token se existir; senão, fallback
def _decode_token_fallback(token: str) -> dict:
    # Use the same JWT_SECRET as auth.py for consistency
    secret = os.getenv("JWT_SECRET", "trocar")
    return jwt.decode(token, secret, algorithms=["HS256"])

try:
    from .auth import decode_token as _decode_token
except Exception:
    _decode_token = _decode_token_fallback  # type: ignore

def _user_from_query_token(db: Session, token: str) -> User:
    if not token:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "missing token")
    try:
        payload = _decode_token(token)
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "invalid token")
    u = db.get(User, uid)
    if not u:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "invalid user")
    return u

# -----------------------------
# Helpers de serialização
# -----------------------------
def _iso(dt):
    try:
        return dt.isoformat() if dt else None
    except Exception:
        return None

def _serialize_thread(t: Thread, db: Session = None) -> dict:
    # Busca o contato associado à thread (se existir)
    # Se não existir, cria automaticamente
    contact_name = None
    try:
        # Tenta acessar o relacionamento (pode estar carregado via joinedload)
        if hasattr(t, "contact") and t.contact is not None:
            contact_name = t.contact.name
        elif db is not None:
            # Se não estiver carregado e tivermos acesso ao db, busca diretamente
            from .models import Contact
            contact = db.query(Contact).filter(Contact.thread_id == t.id).first()
            if not contact:
                # Cria o contato automaticamente se não existir
                # Tenta extrair um nome melhor do metadata ou título
                name = None
                
                # Primeiro, tenta pegar do metadata (pode vir do WhatsApp)
                if hasattr(t, 'meta') and t.meta:
                    if isinstance(t.meta, dict):
                        name = t.meta.get('name') or t.meta.get('profile_name') or t.meta.get('display_name')
                    elif isinstance(t.meta, str):
                        try:
                            import json
                            meta_dict = json.loads(t.meta)
                            name = meta_dict.get('name') or meta_dict.get('profile_name') or meta_dict.get('display_name')
                        except:
                            pass
                
                # Se não encontrou no metadata, tenta do título
                if not name and t.title:
                    # Se o título contém "WhatsApp" seguido de números, não usa como nome
                    # Caso contrário, usa o título completo (pode ser um nome real)
                    if not t.title.startswith("WhatsApp"):
                        # Se não começa com "WhatsApp", provavelmente é um nome real
                        name = t.title
                
                # Se ainda não tem nome, usa o número do telefone como fallback
                if not name and t.external_user_phone:
                    # Extrai os últimos 4 dígitos
                    phone_clean = t.external_user_phone.replace("whatsapp:", "").replace("+", "").strip()
                    if phone_clean:
                        name = f"Contato {phone_clean[-4:]}"
                
                contact = Contact(
                    thread_id=t.id,
                    user_id=t.user_id,
                    phone=t.external_user_phone,
                    name=name or f"Contato {t.id}",  # Fallback final
                )
                db.add(contact)
                db.commit()
                db.refresh(contact)
            
            if contact:
                contact_name = contact.name
                
                # Se o contato tem um nome genérico, tenta atualizar
                if contact_name and (contact_name.startswith("WhatsApp") or contact_name.startswith("Contato ")):
                    # Tenta atualizar o nome do contato
                    new_name = None
                    
                    # Tenta do metadata
                    if hasattr(t, 'meta') and t.meta:
                        if isinstance(t.meta, dict):
                            new_name = t.meta.get('name') or t.meta.get('profile_name') or t.meta.get('display_name')
                        elif isinstance(t.meta, str):
                            try:
                                import json
                                meta_dict = json.loads(t.meta)
                                new_name = meta_dict.get('name') or meta_dict.get('profile_name') or meta_dict.get('display_name')
                            except:
                                pass
                    
                    # Se não encontrou no metadata, tenta do título
                    if not new_name and t.title and not t.title.startswith("WhatsApp"):
                        new_name = t.title
                    
                    # Se encontrou um nome melhor, atualiza
                    if new_name and new_name != contact.name:
                        contact.name = new_name
                        db.commit()
                        db.refresh(contact)
                        contact_name = contact.name
    except Exception:
        # Se houver qualquer erro, ignora e continua sem o nome
        pass
    
    # Busca a última mensagem da thread (para preview na sidebar)
    last_message = None
    last_message_at = None
    try:
        if db is not None:
            from .models import Message
            last_msg = (
                db.query(Message)
                .filter(Message.thread_id == t.id)
                .order_by(Message.id.desc())
                .first()
            )
            if last_msg:
                last_message = last_msg.content[:100]  # Primeiros 100 caracteres
                last_message_at = _iso(last_msg.created_at)
    except Exception:
        pass
    
    # Extrai campos do metadata para facilitar acesso no frontend
    meta = getattr(t, "meta", None)
    meta_dict = {}
    if meta:
        if isinstance(meta, dict):
            meta_dict = meta
        elif isinstance(meta, str):
            try:
                import json
                meta_dict = json.loads(meta)
            except:
                pass
    
    return {
        "id": t.id,
        "user_id": getattr(t, "user_id", None),
        "title": getattr(t, "title", None),
        "human_takeover": bool(getattr(t, "human_takeover", False)),
        "origin": getattr(t, "origin", None),
        "lead_level": getattr(t, "lead_level", None),
        "lead_score": getattr(t, "lead_score", None),
        "lead_stage": getattr(t, "lead_stage", None),  # Etapa atual do funil (frio, aquecimento, aquecido, quente, etc.)
        "metadata": meta_dict,  # meta -> metadata (sempre dict)
        "external_user_phone": getattr(t, "external_user_phone", None),
        "created_at": _iso(getattr(t, "created_at", None)),
        "contact_name": contact_name,  # Nome do contato associado
        "last_message": last_message,  # Preview da última mensagem
        "last_message_at": last_message_at,  # Data da última mensagem
        # Campos achatados do metadata para facilitar acesso
        "funnel_id": meta_dict.get("funnel_id") if meta_dict else None,
        "stage_id": meta_dict.get("stage_id") if meta_dict else None,
        "product_id": meta_dict.get("product_id") if meta_dict else None,
        "source": meta_dict.get("source") if meta_dict else None,
        "tags": meta_dict.get("tags") if meta_dict else None,
    }

# -----------------------------
# SSE stream
# -----------------------------
@app.get("/threads/{thread_id}/stream")
async def stream_thread(
    thread_id: int,
    request: Request,
    token: Optional[str] = Query(None, description="JWT de acesso (ou use Authorization: Bearer)"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if not token and authorization:
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "missing token")

    user = _user_from_query_token(db, token)
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(404, "Thread not found")

    q = await _subscribe(thread_id)

    async def event_gen():
        try:
            yield "event: ping\ndata: ok\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=30)
                    data = json.dumps(payload, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield "event: keepalive\ndata: {}\n\n"
        finally:
            await _unsubscribe(thread_id, q)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)

# -----------------------------
# Threads (sem response_model)
# -----------------------------
@app.get("/threads")
def list_threads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy.orm import joinedload
    # Retorna todas as conversas para todos os usuários (compartilhadas)
    rows = (
        db.query(Thread)
        .options(joinedload(Thread.contact))  # Carrega o contato junto
        .order_by(Thread.id.desc())
        .all()
    )
    # Serializa threads (inclui última mensagem)
    return [_serialize_thread(t, db) for t in rows]

@app.get("/threads/{thread_id}")
def get_thread(
    thread_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy.orm import joinedload
    # Permite acesso a qualquer thread (compartilhada)
    t = (
        db.query(Thread)
        .options(joinedload(Thread.contact))
        .filter(Thread.id == thread_id)
        .first()
    )
    if not t:
        raise HTTPException(404, "Thread not found")
    return _serialize_thread(t, db)

@app.post("/threads")
def create_thread(
    body: ThreadCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = Thread(user_id=user.id, title=body.title or "Nova conversa")
    db.add(t)
    db.commit()
    db.refresh(t)
    return _serialize_thread(t, db)

@app.patch("/threads/{thread_id}")
def update_thread_endpoint(
    thread_id: int,
    body: ThreadUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy.orm import joinedload
    # Permite acesso a qualquer thread (compartilhada)
    t = (
        db.query(Thread)
        .options(joinedload(Thread.contact))
        .filter(Thread.id == thread_id)
        .first()
    )
    if not t:
        raise HTTPException(404, "Thread not found")

    if body.title is not None:
        t.title = body.title
    if body.human_takeover is not None:
        t.human_takeover = bool(body.human_takeover)
    if body.origin is not None:
        t.origin = body.origin or None
    if body.lead_level is not None:
        t.lead_level = body.lead_level or None
    if body.lead_score is not None:
        t.lead_score = int(body.lead_score) if body.lead_score is not None else None
    if body.metadata is not None:
        # Se metadata é um dict, mescla com o existente (não sobrescreve tudo)
        if isinstance(body.metadata, dict) and isinstance(t.meta, dict):
            t.meta = {**(t.meta or {}), **body.metadata}
        else:
            t.meta = body.metadata
    
    # Atualiza campos específicos se vierem no metadata
    if body.metadata and isinstance(body.metadata, dict):
        # Permite atualizar funnel_id, stage_id, product_id, source, tags via metadata
        # Esses campos podem vir direto no body ou dentro de metadata
        pass  # Já foi tratado acima

    db.add(t)
    db.commit()
    db.refresh(t)
    return _serialize_thread(t, db)

@app.delete("/threads/{thread_id}", status_code=204)
def delete_thread(
    thread_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(404, "Thread not found")
    db.query(Message).filter(Message.thread_id == thread_id).delete()
    db.delete(t)
    db.commit()
    return

# -----------------------------
# Messages
# -----------------------------
@app.get("/threads/{thread_id}/messages", response_model=List[MessageRead])
def get_messages(
    thread_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(404, "Thread not found")
    msgs = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.id.asc())
        .all()
    )
    return [
        MessageRead(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in msgs
    ]

@app.post("/threads/{thread_id}/messages", response_model=MessageRead)
async def send_message(
    thread_id: int,
    body: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(404, "Thread not found")

    m_user = Message(thread_id=thread_id, role="user", content=body.content)
    db.add(m_user)
    db.commit()
    db.refresh(m_user)
    
    # 📧 DETECÇÃO AUTOMÁTICA DE EMAIL - Atualiza contato se encontrar email
    from .services.email_detector import should_update_contact_email
    from .models import Contact
    
    contact = db.query(Contact).filter(Contact.thread_id == thread_id).first()
    if contact:
        detected_email = should_update_contact_email(body.content, contact.email)
        if detected_email:
            contact.email = detected_email
            db.commit()
            print(f"[MESSAGE] ✅ Email detectado e atualizado no contato {contact.id}: {detected_email}")

    await _broadcast(
        thread_id,
        {
            "type": "message.created",
            "message": {
                "id": m_user.id,
                "role": m_user.role,
                "content": m_user.content,
                "created_at": m_user.created_at.isoformat(),
            },
        },
    )

    if getattr(t, "human_takeover", False):
        return MessageRead(
            id=m_user.id,
            role=m_user.role,
            content=m_user.content,
            created_at=m_user.created_at,
        )

    # 🔍 DETECÇÃO DE SUPORTE - Aciona takeover automático
    from .services.support_detector import should_trigger_takeover
    should_takeover, takeover_reason = should_trigger_takeover(body.content, t.meta)
    
    if should_takeover:
        # Ativa takeover
        t.human_takeover = True
        db.commit()
        db.refresh(t)
        
        # Envia mensagem de encaminhamento
        takeover_msg = "Perfeita! 💖 Vou te passar com o time que cuida disso, tá bem? Um minutinho…"
        try:
            import asyncio
            from .providers import twilio as twilio_provider
            phone = (t.external_user_phone or "").strip()
            if phone:
                await asyncio.to_thread(twilio_provider.send_text, phone, takeover_msg, "BOT")
        except Exception as e:
            print(f"[MESSAGE] Erro ao enviar mensagem de takeover: {e}")
        
        return MessageRead(
            id=m_user.id,
            role=m_user.role,
            content=body.content,
            created_at=m_user.created_at,
        )

    hist = [
        {"role": m.role, "content": m.content}
        for m in db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.id.asc())
        .all()
    ]

    # 🎯 ATUALIZAÇÃO AUTOMÁTICA DE ETAPA DO FUNIL
    from .services.funnel_stage_manager import detect_stage_from_message, update_stage_from_event
    import json as json_lib
    
    is_first_message = len(hist) == 0
    current_meta = {}
    if t.meta:
        if isinstance(t.meta, dict):
            current_meta = t.meta.copy()
        elif isinstance(t.meta, str):
            try:
                current_meta = json_lib.loads(t.meta)
            except:
                pass
    
    event = detect_stage_from_message(body.content, current_meta, is_first_message)
    if event:
        updated_meta = update_stage_from_event(current_meta, event)
        t.meta = updated_meta
        t.lead_level = updated_meta.get("lead_level")
        db.commit()
        db.refresh(t)

    await _broadcast(thread_id, {"type": "assistant.typing.start"})
    reply = await run_llm(body.content, thread_history=hist, takeover=False)
    await _broadcast(thread_id, {"type": "assistant.typing.stop"})

    if not reply:
        return MessageRead(
            id=m_user.id,
            role=m_user.role,
            content=m_user.content,
            created_at=m_user.created_at,
        )

    m_assist = Message(thread_id=thread_id, role="assistant", content=reply)
    db.add(m_assist)
    db.commit()
    db.refresh(m_assist)

    await _broadcast(
        thread_id,
        {
            "type": "message.created",
            "message": {
                "id": m_assist.id,
                "role": m_assist.role,
                "content": m_assist.content,
                "created_at": m_assist.created_at.isoformat(),
            },
        },
    )

    return MessageRead(
        id=m_assist.id,
        role=m_assist.role,
        content=m_assist.content,
        created_at=m_assist.created_at,
    )

# -----------------------------
# Webhooks WhatsApp - Meta
# -----------------------------
@app.get("/webhooks/meta")
def meta_verify(
    hub_mode: str | None = None,
    hub_challenge: str | None = None,
    hub_verify_token: str | None = None,
):
    expected = os.getenv("META_VERIFY_TOKEN")
    if hub_verify_token == expected:
        try:
            return int(hub_challenge or 0)
        except Exception:
            return hub_challenge or "OK"
    raise HTTPException(403, "Invalid verify token")

@app.post("/webhooks/meta")
async def meta_webhook(req: Request, db: Session = Depends(get_db)):
    data = await req.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
        if not messages:
            return {"status": "ignored"}
        
        changes = messages[0]
        from_ = changes["from"]  # wa_id
        text_in = (changes.get("text", {}) or {}).get("body", "") or ""
        
        # Tenta capturar o nome do perfil do WhatsApp
        profile_name = None
        contacts = value.get("contacts", [])
        if contacts:
            # O primeiro contato geralmente é o remetente
            contact_info = contacts[0]
            profile_name = contact_info.get("profile", {}).get("name") or contact_info.get("name")
    except Exception:
        return {"status": "ignored"}

    owner_email = os.getenv("INBOX_OWNER_EMAIL", "Admin")
    owner = db.query(User).filter(User.email == owner_email).first()
    if not owner:
        owner = User(email=owner_email, password_hash=hash_password("Admin"))
        db.add(owner)
        db.commit()
        db.refresh(owner)

    # Normaliza o número do Meta também
    from_ = _normalize_phone(from_)
    
    # Busca thread existente - normaliza o número do banco também para comparação
    t = (
        db.query(Thread)
        .filter(Thread.user_id == owner.id, Thread.external_user_phone == from_)
        .order_by(Thread.id.desc())
        .first()
    )
    
    # Se não encontrou, tenta buscar normalizando os números do banco
    if not t:
        all_threads = (
            db.query(Thread)
            .filter(Thread.user_id == owner.id)
            .all()
        )
        for thread in all_threads:
            if thread.external_user_phone and _normalize_phone(thread.external_user_phone) == from_:
                t = thread
                # Atualiza o número no banco para o formato normalizado
                if thread.external_user_phone != from_:
                    thread.external_user_phone = from_
                    db.commit()
                    db.refresh(thread)
                break
    
    # Prepara o metadata com o nome do perfil se disponível
    meta_data = {}
    if profile_name:
        meta_data["name"] = profile_name
        meta_data["profile_name"] = profile_name
    if from_:
        meta_data["wa_id"] = from_
    
    if not t:
        # Usa o nome do perfil se disponível, senão usa o padrão
        title = profile_name if profile_name else f"WhatsApp {from_[-4:]}"
        t = Thread(
            user_id=owner.id, 
            title=title, 
            external_user_phone=from_,
            meta=meta_data if meta_data else None
        )
        db.add(t)
        db.commit()
        db.refresh(t)
    else:
        # Atualiza o metadata e título se tiver nome do perfil
        if profile_name:
            import json
            current_meta = {}
            if t.meta:
                if isinstance(t.meta, dict):
                    current_meta = t.meta.copy()
                elif isinstance(t.meta, str):
                    try:
                        current_meta = json.loads(t.meta)
                    except:
                        pass
            
            current_meta.update(meta_data)
            t.meta = current_meta
            
            # Atualiza o título se ainda for genérico
            if t.title.startswith("WhatsApp"):
                t.title = profile_name
            
            db.commit()
            db.refresh(t)
    
    # Atualiza ou cria o contato com o nome do perfil
    from .models import Contact
    contact = db.query(Contact).filter(Contact.thread_id == t.id).first()
    if contact:
        if profile_name and (not contact.name or contact.name.startswith("WhatsApp") or contact.name.startswith("Contato ")):
            contact.name = profile_name
            db.commit()
    elif profile_name:
        # Cria o contato com o nome do perfil
        contact = Contact(
            thread_id=t.id,
            user_id=owner.id,
            phone=from_,
            name=profile_name,
        )
        db.add(contact)
        db.commit()

    m_user = Message(thread_id=t.id, role="user", content=text_in)
    db.add(m_user)
    db.commit()
    db.refresh(m_user)

    await _broadcast(
        t.id,
        {"type": "message.created", "message": {"id": m_user.id, "role": "user", "content": text_in}},
    )

    if getattr(t, "human_takeover", False):
        return {"status": "ok", "skipped_llm": True}

    hist = [
        {"role": m.role, "content": m.content}
        for m in db.query(Message).filter(Message.thread_id == t.id).order_by(Message.id.asc()).all()
    ]

    await _broadcast(t.id, {"type": "assistant.typing.start"})
    reply = await run_llm(text_in, thread_history=hist, takeover=False)
    await _broadcast(t.id, {"type": "assistant.typing.stop"})

    m_assist = Message(thread_id=t.id, role="assistant", content=reply)
    db.add(m_assist)
    db.commit()
    db.refresh(m_assist)

    await _broadcast(
        t.id,
        {"type": "message.created", "message": {"id": m_assist.id, "role": "assistant", "content": reply}},
    )

    await meta_provider.send_text(from_, reply)
    return {"status": "ok"}

# -----------------------------
# Webhooks WhatsApp - Twilio
# -----------------------------
def _normalize_phone(phone: str) -> str:
    """
    Normaliza número de telefone para formato E.164 consistente.
    Remove 'whatsapp:', espaços, e garante que comece com '+'.
    Exemplos:
    - 'whatsapp:+556184081114' -> '+556184081114'
    - '+556184081114' -> '+556184081114'
    - '556184081114' -> '+556184081114'
    """
    if not phone:
        return ""
    # Remove 'whatsapp:' prefix
    normalized = str(phone).replace("whatsapp:", "").strip()
    # Remove espaços e caracteres especiais (exceto +)
    normalized = normalized.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    # Garante que comece com +
    if normalized and not normalized.startswith("+"):
        normalized = "+" + normalized
    return normalized

# 🚨 SISTEMA DE DEBOUNCE/BATCHING - Agrupa mensagens enviadas em sequência
# Dicionário para rastrear threads que estão aguardando processamento
_thread_processing_locks: Dict[int, asyncio.Lock] = {}
_thread_pending_messages: Dict[int, List[Dict]] = {}
_thread_processing_tasks: Dict[int, asyncio.Task] = {}

async def _process_batched_messages(thread_id: int, phone_number: str, db: Session):
    """Processa mensagens agrupadas após um delay - executa todo o processamento LLM"""
    await asyncio.sleep(3)  # Aguarda 3 segundos para agrupar mensagens
    
    # Remove do dicionário de tarefas
    if thread_id in _thread_processing_tasks:
        del _thread_processing_tasks[thread_id]
    
    # Limpa a fila de pendentes (já foram salvas no banco)
    pending_count = len(_thread_pending_messages.get(thread_id, []))
    if thread_id in _thread_pending_messages:
        del _thread_pending_messages[thread_id]
    
    logger = logging.getLogger(__name__)
    logger.info(f"[WEBHOOK-TWILIO][BATCH] Processando mensagens agrupadas para thread {thread_id} (total: {pending_count})")
    
    # Cria nova sessão do banco para esta tarefa assíncrona
    from .db import SessionLocal
    async_db = SessionLocal()
    
    try:
        from .models import Thread, Message
        t = async_db.query(Thread).filter(Thread.id == thread_id).first()
        if not t:
            logger.error(f"[WEBHOOK-TWILIO][BATCH] Thread {thread_id} não encontrada")
            return
        
        # Busca histórico completo (todas as mensagens já salvas)
        hist = [
            {"role": m.role, "content": m.content}
            for m in async_db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.id.asc()).all()
        ]
        
        # Pega a última mensagem do usuário (que contém o contexto completo)
        last_user_msg = (
            async_db.query(Message)
            .filter(Message.thread_id == thread_id, Message.role == "user")
            .order_by(Message.id.desc())
            .first()
        )
        
        if not last_user_msg:
            logger.warning(f"[WEBHOOK-TWILIO][BATCH] Nenhuma mensagem do usuário encontrada para thread {thread_id}")
            return
        
        full_content = last_user_msg.content
        logger.info(f"[WEBHOOK-TWILIO][BATCH] Processando com histórico completo ({len(hist)} mensagens). Última: '{full_content[:100]}'")
        
        # Continua com todo o processamento (código que estava após salvar m_user)
        # ... (copiar todo o código de processamento aqui)
        # Por enquanto, vou chamar uma função auxiliar que contém a lógica
        
        # TODO: Extrair a lógica de processamento para uma função reutilizável
        # Por enquanto, vou duplicar o código essencial aqui
        
    except Exception as e:
        logger.error(f"[WEBHOOK-TWILIO][BATCH] Erro ao processar mensagens agrupadas: {e}", exc_info=True)
    finally:
        async_db.close()
        # Libera o lock
        if thread_id in _thread_processing_locks:
            del _thread_processing_locks[thread_id]

async def _process_webhook_message(
    thread_id: int,
    from_: str,
    body: str,
    profile_name: Optional[str],
    db: Session
):
    """Processa uma mensagem do webhook (lógica extraída para reutilização)"""
    # Esta função contém toda a lógica de processamento que estava no twilio_webhook
    # Será implementada movendo o código atual
    pass

@app.post("/webhooks/twilio")
async def twilio_webhook(req: Request, db: Session = Depends(get_db)):
    import logging
    logger = logging.getLogger(__name__)
    logger.info("[WEBHOOK-TWILIO] Received POST request")
    
    try:
        form = await req.form()
        from_raw = str(form.get("From", ""))
        from_ = _normalize_phone(from_raw)  # Normaliza o número
        body = form.get("Body", "") or ""
        
        # Detecta mídia (Twilio envia NumMedia quando há anexos)
        num_media = int(form.get("NumMedia", "0") or "0")
        has_media = num_media > 0
        
        logger.info(f"[WEBHOOK-TWILIO] Message from {from_}: {body[:100]}, Media: {num_media}")
        
        # Tenta capturar o nome do perfil do WhatsApp (Twilio pode enviar ProfileName)
        profile_name = form.get("ProfileName") or form.get("Profile Name") or None
        if profile_name:
            logger.info(f"[WEBHOOK-TWILIO] Profile name: {profile_name}")
    except Exception as e:
        logger.error(f"[WEBHOOK-TWILIO] Error parsing webhook: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

    owner_email = os.getenv("INBOX_OWNER_EMAIL", "Admin")
    owner = db.query(User).filter(User.email == owner_email).first()
    if not owner:
        owner = User(email=owner_email, password_hash=hash_password("Admin"))
        db.add(owner)
        db.commit()
        db.refresh(owner)

    # Busca thread existente - SEMPRE normaliza os números do banco para comparação
    # Busca por número exato primeiro (caso já esteja normalizado)
    t = (
        db.query(Thread)
        .filter(Thread.user_id == owner.id, Thread.external_user_phone == from_)
        .order_by(Thread.id.desc())
        .first()
    )
    
    # Se não encontrou, busca normalizando TODOS os números do banco
    if not t:
        logger.info(f"[WEBHOOK-TWILIO] Buscando thread para número normalizado: '{from_}' (original: '{from_raw}')")
        all_threads = (
            db.query(Thread)
            .filter(Thread.user_id == owner.id, Thread.external_user_phone.isnot(None))
            .all()
        )
        logger.info(f"[WEBHOOK-TWILIO] Encontradas {len(all_threads)} threads do usuário {owner.id} com telefone")
        
        for thread in all_threads:
            if not thread.external_user_phone:
                continue
            normalized_db_phone = _normalize_phone(thread.external_user_phone)
            logger.debug(f"[WEBHOOK-TWILIO] Comparando: DB='{thread.external_user_phone}' (normalizado: '{normalized_db_phone}') vs incoming='{from_}'")
            
            if normalized_db_phone == from_:
                logger.info(f"[WEBHOOK-TWILIO] ✅ Thread encontrada! ID={thread.id}, número DB='{thread.external_user_phone}' (normalizado: '{normalized_db_phone}')")
                t = thread
                # Atualiza o número no banco para o formato normalizado (se diferente)
                if thread.external_user_phone != from_:
                    logger.info(f"[WEBHOOK-TWILIO] Atualizando número no banco de '{thread.external_user_phone}' para '{from_}'")
                    thread.external_user_phone = from_
                    db.commit()
                    db.refresh(thread)
                break
        
        if not t:
            logger.info(f"[WEBHOOK-TWILIO] Nenhuma thread encontrada para número '{from_}' (normalizado de '{from_raw}'), criando nova thread.")
            # Última tentativa: busca em TODAS as threads (caso tenha havido migração de usuário)
            logger.info(f"[WEBHOOK-TWILIO] Buscando em TODAS as threads (última tentativa)...")
            all_threads_global = (
                db.query(Thread)
                .filter(Thread.external_user_phone.isnot(None))
                .all()
            )
            # Coleta todas as threads com o mesmo número (pode haver duplicatas)
            matching_threads = []
            for thread in all_threads_global:
                if thread.external_user_phone and _normalize_phone(thread.external_user_phone) == from_:
                    matching_threads.append(thread)
            
            if matching_threads:
                # Se houver múltiplas, usa a mais recente (maior ID)
                matching_threads.sort(key=lambda x: x.id, reverse=True)
                t = matching_threads[0]
                
                # Migra para o usuário correto se necessário
                if t.user_id != owner.id:
                    logger.info(f"[WEBHOOK-TWILIO] Thread encontrada em outro usuário (ID={t.id}, user_id={t.user_id}), migrando para user_id={owner.id}")
                    t.user_id = owner.id
                
                # Normaliza o número se necessário
                if t.external_user_phone != from_:
                    logger.info(f"[WEBHOOK-TWILIO] Atualizando número no banco de '{t.external_user_phone}' para '{from_}'")
                    t.external_user_phone = from_
                
                # Se houver threads duplicadas, marca as outras para possível limpeza futura
                if len(matching_threads) > 1:
                    logger.info(f"[WEBHOOK-TWILIO] Encontradas {len(matching_threads)} threads duplicadas para número '{from_}'. Usando thread ID={t.id} (mais recente).")
                    for dup_thread in matching_threads[1:]:
                        logger.debug(f"[WEBHOOK-TWILIO] Thread duplicada ID={dup_thread.id} será ignorada (mensagens devem ir para thread {t.id})")
                
                db.commit()
                db.refresh(t)
    else:
        logger.info(f"[WEBHOOK-TWILIO] ✅ Thread encontrada por busca exata: ID={t.id}, número='{from_}'")
    
    # Prepara o metadata com o nome do perfil se disponível
    meta_data = {}
    if profile_name:
        meta_data["name"] = profile_name
        meta_data["profile_name"] = profile_name
    if from_:
        meta_data["wa_id"] = from_
        meta_data["phone"] = from_
    
    if not t:
        # Usa o nome do perfil se disponível, senão usa o padrão
        title = profile_name if profile_name else f"WhatsApp {from_[-4:]}"
        logger.warning(f"[WEBHOOK-TWILIO] ⚠️⚠️⚠️ Criando NOVA thread: título='{title}', número='{from_}' (normalizado de '{from_raw}')")
        
        # Detecta funil/etapa automaticamente para nova thread
        from .services.funnel_detector import detect_funnel_and_stage
        funnel_data = detect_funnel_and_stage(
            message=body,
            thread_meta=None,
            is_first_message=True
        )
        
        # Mescla metadata com dados do funil
        if funnel_data:
            meta_data.update(funnel_data)
            logger.info(f"[WEBHOOK-TWILIO] 🎯 Funil detectado automaticamente: funnel_id={funnel_data.get('funnel_id')}, stage_id={funnel_data.get('stage_id')}, source={funnel_data.get('source')}")
        
        t = Thread(
            user_id=owner.id, 
            title=title, 
            external_user_phone=from_,
            meta=meta_data if meta_data else None
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        logger.warning(f"[WEBHOOK-TWILIO] ⚠️⚠️⚠️ Nova thread criada: ID={t.id}")
    else:
        # Atualiza o metadata e título se tiver nome do perfil
        if profile_name:
            import json
            current_meta = {}
            if t.meta:
                if isinstance(t.meta, dict):
                    current_meta = t.meta.copy()
                elif isinstance(t.meta, str):
                    try:
                        current_meta = json.loads(t.meta)
                    except:
                        pass
            
            current_meta.update(meta_data)
            t.meta = current_meta
            
            # Atualiza o título se ainda for genérico
            if t.title.startswith("WhatsApp"):
                t.title = profile_name
            
            db.commit()
            db.refresh(t)
    
    # Atualiza ou cria o contato com o nome do perfil
    from .models import Contact
    contact = db.query(Contact).filter(Contact.thread_id == t.id).first()
    if contact:
        if profile_name and (not contact.name or contact.name.startswith("WhatsApp") or contact.name.startswith("Contato ")):
            contact.name = profile_name
            db.commit()
    elif profile_name:
        # Cria o contato com o nome do perfil
        contact = Contact(
            thread_id=t.id,
            user_id=owner.id,
            phone=from_,
            name=profile_name,
        )
        db.add(contact)
        db.commit()

    # Processa mídia se houver
    media_context = ""
    if has_media:
        # Envia resposta imediata "Estou processando..."
        processing_msg = "📎 Recebi sua mídia. Estou analisando, um minuto..."
        try:
            await asyncio.to_thread(twilio_provider.send_text, from_, processing_msg, "BOT")
            logger.info(f"[WEBHOOK-TWILIO] Sent processing message to {from_}")
        except Exception as e:
            logger.error(f"[WEBHOOK-TWILIO] Error sending processing message: {str(e)}")
        
        # Processa cada mídia recebida
        from .services import media_processor
        
        for i in range(num_media):
            media_url = form.get(f"MediaUrl{i}")
            content_type = form.get(f"MediaContentType{i}")
            
            if not media_url:
                continue
            
            logger.info(f"[WEBHOOK-TWILIO] Processing media {i+1}/{num_media}: {content_type}")
            
            # Determina tipo de mídia
            if content_type and content_type.startswith("audio/"):
                media_type = "audio"
            elif content_type and content_type.startswith("image/"):
                media_type = "image"
            else:
                media_type = "document"
            
            # Processa mídia
            result = await media_processor.process_media(
                media_url=media_url,
                media_type=media_type,
                filename=form.get(f"MediaFilename{i}"),
                mime_type=content_type
            )
            
            if result["success"]:
                if media_type == "audio":
                    # Formato que a IA entenderá como transcrição direta
                    media_context += f"\n[Áudio transcrito]: {result['content']}\n"
                elif media_type == "image":
                    # Formato que a IA entenderá como descrição visual direta
                    media_context += f"\n[Descrição da imagem]: {result['content']}\n"
                else:
                    # Formato que a IA entenderá como conteúdo do documento
                    media_context += f"\n[Conteúdo do documento]: {result['content']}\n"
            else:
                media_context += f"\n[Erro ao processar mídia {i+1}]: {result.get('error', 'Erro desconhecido')}\n"
                logger.error(f"[WEBHOOK-TWILIO] Error processing media: {result.get('error')}")
    
    # Combina texto da mensagem com contexto da mídia
    full_content = body
    if media_context:
        full_content = f"{body}\n{media_context}".strip()
        if not body:
            full_content = media_context.strip()
    
    # Se é a primeira mensagem e ainda não tem funil definido, detecta automaticamente
    from .models import Message as MessageModel
    message_count = db.query(MessageModel).filter(MessageModel.thread_id == t.id).count()
    is_first_message = message_count == 0
    
    if is_first_message or (t.meta and not (isinstance(t.meta, dict) and t.meta.get("funnel_id"))):
        from .services.funnel_detector import detect_funnel_and_stage
        import json
        
        current_meta = {}
        if t.meta:
            if isinstance(t.meta, dict):
                current_meta = t.meta.copy()
            elif isinstance(t.meta, str):
                try:
                    current_meta = json.loads(t.meta)
                except:
                    pass
        
        funnel_data = detect_funnel_and_stage(
            message=full_content,
            thread_meta=current_meta,
            is_first_message=is_first_message
        )
        
        if funnel_data:
            current_meta.update(funnel_data)
            t.meta = current_meta
            db.commit()
            db.refresh(t)
            logger.info(f"[WEBHOOK-TWILIO] 🎯 Funil atualizado: funnel_id={funnel_data.get('funnel_id')}, stage_id={funnel_data.get('stage_id')}")
    
    m_user = Message(thread_id=t.id, role="user", content=full_content)
    db.add(m_user)
    db.commit()
    db.refresh(m_user)
    
    # 🚨 SISTEMA DE DEBOUNCE - Aguarda 5s após última mensagem antes de processar
    # Se chegar nova mensagem durante a espera, cancela e reinicia o timer
    if t.id in _thread_processing_tasks:
        task = _thread_processing_tasks[t.id]
        if not task.done():
            logger.info(f"[WEBHOOK-TWILIO][DEBOUNCE] Cancelando processamento anterior para thread {t.id} (nova mensagem chegou)")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        del _thread_processing_tasks[t.id]
    
    # Cria nova tarefa que aguarda 5 segundos antes de processar
    async def _process_after_debounce(thread_id: int, phone: str):
        """Aguarda 5 segundos e então processa todas as mensagens agrupadas"""
        logger.info(f"[WEBHOOK-TWILIO][DEBOUNCE] Tarefa iniciada para thread {thread_id}, aguardando 5s...")
        try:
            await asyncio.sleep(5)  # Aguarda 5 segundos
            
            # Remove da lista de tarefas
            if thread_id in _thread_processing_tasks:
                del _thread_processing_tasks[thread_id]
            
            logger.info(f"[WEBHOOK-TWILIO][DEBOUNCE] ✅ Timer de 5s expirado. Processando mensagens para thread {thread_id}")
            
            # Cria nova sessão do banco para processar
            from .db import SessionLocal
            async_db = SessionLocal()
            try:
                # Busca thread e processa
                t_async = async_db.query(Thread).filter(Thread.id == thread_id).first()
                if not t_async:
                    logger.error(f"[WEBHOOK-TWILIO][DEBOUNCE] Thread {thread_id} não encontrada")
                    return
                
                # Busca histórico completo (todas as mensagens já salvas)
                hist = [
                    {"role": m.role, "content": m.content}
                    for m in async_db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.id.asc()).all()
                ]
                
                # Pega a última mensagem do usuário
                last_user_msg = (
                    async_db.query(Message)
                    .filter(Message.thread_id == thread_id, Message.role == "user")
                    .order_by(Message.id.desc())
                    .first()
                )
                
                if not last_user_msg:
                    logger.warning(f"[WEBHOOK-TWILIO][DEBOUNCE] Nenhuma mensagem do usuário encontrada")
                    return
                
                full_content = last_user_msg.content
                logger.info(f"[WEBHOOK-TWILIO][DEBOUNCE] Processando com histórico completo ({len(hist)} mensagens). Última msg: '{full_content[:100]}'")
                
                # Continua com o processamento normal (chama a função que processa)
                logger.info(f"[WEBHOOK-TWILIO][DEBOUNCE] Chamando _process_message_for_llm...")
                await _process_message_for_llm(t_async, phone, full_content, hist, async_db)
                logger.info(f"[WEBHOOK-TWILIO][DEBOUNCE] ✅ Processamento concluído para thread {thread_id}")
                
            except Exception as e:
                logger.error(f"[WEBHOOK-TWILIO][DEBOUNCE] Erro ao processar: {e}", exc_info=True)
            finally:
                async_db.close()
        except asyncio.CancelledError:
            logger.info(f"[WEBHOOK-TWILIO][DEBOUNCE] Processamento cancelado (nova mensagem chegou)")
        except Exception as e:
            logger.error(f"[WEBHOOK-TWILIO][DEBOUNCE] Erro na tarefa: {e}", exc_info=True)
    
    # Inicia a tarefa de debounce
    task = asyncio.create_task(_process_after_debounce(t.id, from_))
    _thread_processing_tasks[t.id] = task
    
    logger.info(f"[WEBHOOK-TWILIO][DEBOUNCE] Mensagem salva. Aguardando 5s antes de processar (timer reiniciável se nova msg chegar)")
    
    # Retorna imediatamente (não bloqueia o webhook)
    return {"status": "ok", "queued": True, "debounce_active": True}


async def _process_message_for_llm(t: Thread, phone_to_send: str, full_content: str, hist: List[Dict], db: Session):
    """Processa mensagem para LLM - função reutilizável chamada após debounce"""
    logger = logging.getLogger(__name__)
    logger.info(f"[WEBHOOK-TWILIO][_process_message_for_llm] Iniciando processamento para thread {t.id}")
    
    if getattr(t, "human_takeover", False):
        logger.info(f"[WEBHOOK-TWILIO] Thread {t.id} in human takeover, skipping LLM")
        return

    # 🔍 DETECÇÃO DE SUPORTE - Aciona takeover automático
    from .services.support_detector import should_trigger_takeover
    should_takeover, takeover_reason = should_trigger_takeover(full_content, t.meta)
    
    if should_takeover:
        logger.warning(f"[WEBHOOK-TWILIO] 🚨 SUPORTE DETECTADO! Thread {t.id}: {takeover_reason}")
        
        # Ativa takeover
        t.human_takeover = True
        db.commit()
        db.refresh(t)
        
        # Envia mensagem de encaminhamento
        takeover_msg = "Perfeita! 💖 Vou te passar com o time que cuida disso, tá bem? Um minutinho…"
        try:
            await asyncio.to_thread(twilio_provider.send_text, phone_to_send, takeover_msg, "BOT")
            logger.info(f"[WEBHOOK-TWILIO] ✅ Takeover ativado e mensagem enviada para thread {t.id}")
        except Exception as e:
            logger.error(f"[WEBHOOK-TWILIO] Erro ao enviar mensagem de takeover: {e}")
        
        return
    
    # Usa o histórico passado como parâmetro (já contém todas as mensagens)
    logger.info(f"[WEBHOOK-TWILIO] Processing LLM for thread {t.id}, history length: {len(hist)}")

    # 🎯 ENGINE DE AUTOMAÇÕES - Processa triggers e executa ações ANTES DO LLM
    from .services.automation_engine import process_automation
    import json as json_lib
    
    # 🚨 DETECÇÃO DE MENSAGENS DUPLICADAS/JANELA DE TEMPO
    # Verifica se há mensagem do assistente nos últimos 10 segundos (janela menor para evitar duplicatas)
    # MAS: não bloqueia se a última mensagem foi apenas um áudio (Fase 1) - permite resposta na Fase 2
    from datetime import datetime, timedelta
    recent_assistant_msg = (
        db.query(Message)
        .filter(
            Message.thread_id == t.id,
            Message.role == "assistant",
            Message.created_at >= datetime.utcnow() - timedelta(seconds=10)
        )
        .order_by(Message.created_at.desc())
        .first()
    )
    
    if recent_assistant_msg:
        # Verifica se a última mensagem foi apenas áudio (Fase 1) - se sim, permite resposta
        last_content = recent_assistant_msg.content or ""
        is_only_audio = "[Áudio enviado:" in last_content and len(last_content.strip()) < 100
        
        if not is_only_audio:
            logger.info(f"[WEBHOOK-TWILIO] ⏱️ Mensagem duplicada detectada (última resposta há {(datetime.utcnow() - recent_assistant_msg.created_at).total_seconds():.1f}s). Ignorando.")
            return {"status": "ok", "duplicate_detected": True, "reason": "recent_response"}
        else:
            logger.info(f"[WEBHOOK-TWILIO] ⏱️ Última mensagem foi apenas áudio (Fase 1), permitindo resposta para Fase 2")
    
    # Prepara thread_meta com lead_stage
    current_meta = {}
    if t.meta:
        if isinstance(t.meta, dict):
            current_meta = t.meta.copy()
        elif isinstance(t.meta, str):
            try:
                current_meta = json_lib.loads(t.meta)
            except:
                pass
    
    # Adiciona lead_stage ao meta se não estiver
    if "lead_stage" not in current_meta:
        current_meta["lead_stage"] = t.lead_stage
    
    # Processa automação (ANTES de chamar LLM)
    logger.info(f"[WEBHOOK-TWILIO] 🔍 Processando automação para mensagem: '{full_content[:100]}'")
    new_lead_stage, automation_metadata, should_skip_llm = await process_automation(
        message=full_content,
        phone_number=phone_to_send,
        thread_meta=current_meta,
        db_session=db,
        thread_id=t.id
    )
    logger.info(f"[WEBHOOK-TWILIO] 🔍 Resultado automação: new_stage={new_lead_stage}, should_skip={should_skip_llm}, metadata={automation_metadata}")
    
    # Se detectou suporte, para aqui
    if should_skip_llm and automation_metadata.get("support_detected"):
        # Ativa takeover
        t.human_takeover = True
        if automation_metadata.get("need_human"):
            current_meta["need_human"] = True
        t.meta = current_meta
        db.commit()
        db.refresh(t)
        logger.warning(f"[WEBHOOK-TWILIO] 🚨 Automação parada por suporte detectado")
        return {"status": "ok", "automation_stopped": True, "reason": "support_detected"}
    
    # Atualiza lead_stage se mudou
    if new_lead_stage:
        t.lead_stage = new_lead_stage
        current_meta["lead_stage"] = new_lead_stage
        current_meta.update(automation_metadata)
        t.meta = current_meta
        db.commit()
        db.refresh(t)
        logger.info(f"[WEBHOOK-TWILIO] ✅ Lead stage atualizado: {new_lead_stage}")
    
    # Se executou automação (gatilho detectado), NÃO chama LLM
    # EXCEÇÕES: Fase 1 e Fase 2 - automação envia apenas áudio, LLM responde depois
    automation_trigger = automation_metadata.get("event", "")
    if should_skip_llm:
        logger.info(f"[WEBHOOK-TWILIO] ✅ Automação executada, pulando LLM. Gatilho: {automation_trigger}")
        
        # Salva mensagem de registro da automação no banco
        automation_msg = f"[Automação executada: {automation_trigger}]"
        m_automation = Message(thread_id=t.id, role="system", content=automation_msg)
        db.add(m_automation)
        db.commit()
        
        return {"status": "ok", "automation_executed": True, "lead_stage": new_lead_stage}
    
    # 🚨 VERIFICAÇÃO GLOBAL DE DUPLICAÇÃO - SEMPRE verifica se já enviou áudio 2 + imagens
    # Esta verificação deve acontecer ANTES de qualquer processamento LLM
    from datetime import datetime, timedelta
    recent_assistant_messages = (
        db.query(Message)
        .filter(
            Message.thread_id == t.id,
            Message.role == "assistant",
            Message.created_at >= datetime.utcnow() - timedelta(minutes=30)  # Últimas 30 minutos
        )
        .order_by(Message.created_at.desc())
        .all()
    )
    
    # Verifica se já enviou áudio 2 + imagens recentemente
    has_recent_audio2 = False
    has_recent_images = False
    for msg in recent_assistant_messages:
        content = msg.content or ""
        # Verifica se tem áudio 2
        if "[Áudio enviad" in content and "audio2" in content.lower():
            has_recent_audio2 = True
        # Verifica se tem as imagens img_resultado
        if "[Imagem enviad" in content and "img_resultado" in content:
            has_recent_images = True
    
    if has_recent_audio2 and has_recent_images:
        # 🚨 BLOQUEIO CRÍTICO: Já enviou Fase 2 recentemente, NÃO deve repetir
        logger.warning(f"[WEBHOOK-TWILIO] 🚨🚨🚨 DUPLICAÇÃO CRÍTICA DETECTADA! Thread {t.id} já enviou áudio 2 + imagens recentemente. BLOQUEANDO COMPLETAMENTE o envio duplicado.")
        
        # Adiciona contexto MUITO FORTE para a LLM não repetir
        hist.append({
            "role": "system",
            "content": "[CONTEXTO CRÍTICO - BLOQUEIO ABSOLUTO] Você JÁ enviou áudio 2 + 8 imagens img_resultado + pergunta 'o que tá faltando' RECENTEMENTE nesta conversa (há menos de 30 minutos). A lead está respondendo essa pergunta. Você DEVE interpretar como interesse em planos e enviar APENAS: [Áudio enviado: audio3_explicacao_planos] + texto dos planos (Mensal + Anual). É PROIBIDO repetir áudio 2 ou qualquer imagem img_resultado. Se você tentar repetir, o sistema irá bloquear."
        })
    
    # Se foi Fase 2, automação não enviou nada, LLM ainda precisa responder
    if automation_trigger == "DOR_DETECTADA":
        logger.info(f"[WEBHOOK-TWILIO] ✅ Automação processou gatilho {automation_trigger}, LLM vai responder agora")
        
        if not (has_recent_audio2 and has_recent_images):
            # Primeira vez na Fase 2, LLM deve enviar áudio 2 + 8 imagens + texto final
            hist.append({
                "role": "system",
                "content": "[CONTEXTO AUTOMAÇÃO] Fase 2 detectada (dor). Você DEVE enviar: [Áudio enviado: audio2_*] + [Imagem enviada: img_resultado_01] até [img_resultado_08] + texto final 'Me conta aqui, gata, o que tá faltando pra tu dar esse passo? 👯‍♀️✨'"
            })
    
    # Se foi INTERESSE_PLANO, automação já enviou áudio 3 + planos, LLM não precisa fazer nada
    if automation_trigger == "INTERESSE_PLANO":
        logger.info(f"[WEBHOOK-TWILIO] ✅ Automação processou gatilho {automation_trigger}, LLM não precisa responder")
        # Automação já enviou tudo, não chama LLM
        return {"status": "ok", "automation_executed": True, "lead_stage": new_lead_stage}

    # 🚨 VERIFICAÇÃO: Não repetir áudios já enviados
    # Verifica se áudio 3 já foi enviado antes
    has_audio3 = any("[Áudio enviado: audio3" in msg.get("content", "") or "audio3_explicacao_planos" in str(msg.get("content", "")).lower() for msg in hist)
    if has_audio3:
        hist.append({
            "role": "system",
            "content": "[CONTEXTO HISTÓRICO] O áudio 3 (audio3_explicacao_planos) JÁ foi enviado antes nesta conversa. Você NÃO deve enviar o áudio 3 novamente. Responda apenas com texto explicando como funciona."
        })
    
    # Verifica se áudio 1 já foi enviado
    has_audio1 = any("[Áudio enviado: audio1" in msg.get("content", "") or "audio1_boas_vindas" in str(msg.get("content", "")).lower() for msg in hist)
    if has_audio1:
        hist.append({
            "role": "system",
            "content": "[CONTEXTO HISTÓRICO] O áudio 1 (audio1_boas_vindas) JÁ foi enviado antes nesta conversa. Você NÃO deve enviar o áudio 1 novamente."
        })
    
    # Verifica se áudio 2 já foi enviado
    has_audio2 = any("[Áudio enviado: audio2" in msg.get("content", "") for msg in hist)
    if has_audio2:
        hist.append({
            "role": "system",
            "content": "[CONTEXTO HISTÓRICO] O áudio 2 JÁ foi enviado antes nesta conversa. Você NÃO deve enviar o áudio 2 novamente."
        })
    
    # 🛒 VERIFICAÇÃO DE COMPRA CONFIRMADA - Adiciona informação sobre compras no contexto da IA
    contact = db.query(Contact).filter(Contact.thread_id == t.id).first()
    if contact:
        # Busca compras aprovadas vinculadas ao contato
        approved_sales = db.query(SaleEvent).filter(
            SaleEvent.contact_id == contact.id,
            SaleEvent.event == "sale.approved"
        ).order_by(SaleEvent.created_at.desc()).all()
        
        if approved_sales:
            # Pega a compra mais recente
            latest_sale = approved_sales[0]
            plan_type = latest_sale.plan_type or "mensal"
            value_formatted = f"R${latest_sale.value / 100:.2f}" if latest_sale.value else "confirmado"
            sale_date = latest_sale.created_at.strftime("%d/%m/%Y") if latest_sale.created_at else "recentemente"
            
            purchase_info = f"[STATUS DA COMPRA] ✅ COMPRA CONFIRMADA: O cliente JÁ realizou o pagamento e a compra foi confirmada pela plataforma (Eduzz). Plano: {plan_type}, Valor: {value_formatted}, Data: {sale_date}. A mensagem pós-compra com links de acesso já foi enviada automaticamente pelo sistema. Quando o cliente mencionar que já comprou ou perguntar sobre acesso, confirme que a compra foi confirmada e que os acessos já foram enviados."
            
            hist.append({
                "role": "system",
                "content": purchase_info
            })
            
            logger.info(f"[WEBHOOK-TWILIO] ✅ Compra confirmada detectada para thread {t.id}: {plan_type}, {value_formatted}")

    await _broadcast(t.id, {"type": "assistant.typing.start"})
    try:
        reply = await run_llm(full_content, thread_history=hist, takeover=False)
        logger.info(f"[WEBHOOK-TWILIO] LLM reply generated: {type(reply).__name__}")
        if isinstance(reply, dict):
            logger.info(f"[WEBHOOK-TWILIO] LLM reply (dict): {reply}")
        elif isinstance(reply, str):
            logger.info(f"[WEBHOOK-TWILIO] LLM reply (str, first 200 chars): {reply[:200]}")
        
        # 🛡️ VALIDAÇÃO DE RESPOSTA DO LLM
        from .services.response_validator import validate_response_for_stage
        reply_str = str(reply) if not isinstance(reply, dict) else reply.get("message", str(reply))
        stage_id = current_meta.get("stage_id") if current_meta else None
        phase = current_meta.get("phase") if current_meta else None
        
        # CORREÇÃO D: Passa mensagem do usuário para detectar intent (ASK_PLANS vs CHOOSE_PLAN)
        user_message = full_content  # full_content contém a mensagem do usuário
        
        is_valid, error_reason, corrected_response = validate_response_for_stage(
            reply_str, 
            stage_id=stage_id, 
            phase=phase, 
            thread_meta=current_meta,
            user_message=user_message
        )
        
        if not is_valid and error_reason:
            logger.warning(f"[WEBHOOK-TWILIO] ⚠️ Resposta do LLM inválida: {error_reason}")
            if corrected_response:
                logger.info(f"[WEBHOOK-TWILIO] ✅ Aplicando correção automática")
                reply = corrected_response
            else:
                logger.error(f"[WEBHOOK-TWILIO] ❌ Não foi possível corrigir resposta. Erro: {error_reason}")
        
    except Exception as e:
        logger.error(f"[WEBHOOK-TWILIO] Error generating LLM reply: {str(e)}", exc_info=True)
        reply = "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."
    await _broadcast(t.id, {"type": "assistant.typing.stop"})

    # 🚨 VERIFICAÇÃO FINAL CRÍTICA - Bloqueia duplicação de áudio 2 + imagens ANTES DE PROCESSAR
    reply_str = str(reply) if not isinstance(reply, dict) else reply.get("message", str(reply))
    
    # Verifica se a resposta contém áudio 2 + imagens
    has_audio2_in_reply = "[Áudio enviado: audio2" in reply_str.lower() or "[Áudio enviada: audio2" in reply_str.lower()
    has_images_in_reply = "img_resultado" in reply_str.lower()
    
    if has_audio2_in_reply and has_images_in_reply:
        # Verifica novamente se já enviou recentemente (double check usando variáveis já calculadas)
        if has_recent_audio2 and has_recent_images:
            logger.error(f"[WEBHOOK-TWILIO] 🚨🚨🚨 BLOQUEIO CRÍTICO DE DUPLICAÇÃO! LLM tentou enviar áudio 2 + imagens novamente. Thread {t.id}. Resposta BLOQUEADA e substituída.")
            
            # Substitui COMPLETAMENTE a resposta por uma que não repete
            reply = "[Áudio enviado: audio3_explicacao_planos]\n\nEntendi! Você já está interessada nos planos. Deixa eu te mostrar as opções:\n\n📦 **PLANO MENSAL**\n- Acesso completo\n- Suporte prioritário\n\n📦 **PLANO ANUAL**\n- Acesso completo\n- Suporte prioritário\n- Melhor custo-benefício\n\nQual faz mais sentido pra você?"

    # 🚨 VERIFICAÇÃO FINAL CRÍTICA - Bloqueia duplicação de áudio 2 + imagens ANTES DE PROCESSAR
    reply_str = str(reply) if not isinstance(reply, dict) else reply.get("message", str(reply))
    
    # Verifica se a resposta contém áudio 2 + imagens
    has_audio2_in_reply = "[Áudio enviado: audio2" in reply_str.lower() or "[Áudio enviada: audio2" in reply_str.lower()
    has_images_in_reply = "img_resultado" in reply_str.lower()
    
    if has_audio2_in_reply and has_images_in_reply:
        # Verifica novamente se já enviou recentemente (usa variáveis já calculadas acima)
        if has_recent_audio2 and has_recent_images:
            logger.error(f"[WEBHOOK-TWILIO] 🚨🚨🚨 BLOQUEIO CRÍTICO DE DUPLICAÇÃO! LLM tentou enviar áudio 2 + imagens novamente. Thread {t.id}. Resposta BLOQUEADA e substituída.")
            
            # Substitui COMPLETAMENTE a resposta por uma que não repete
            reply = "[Áudio enviado: audio3_explicacao_planos]\n\nEntendi! Você já está interessada nos planos. Deixa eu te mostrar as opções:\n\n📦 **PLANO MENSAL**\n- Acesso completo\n- Suporte prioritário\n\n📦 **PLANO ANUAL**\n- Acesso completo\n- Suporte prioritário\n- Melhor custo-benefício\n\nQual faz mais sentido pra você?"
    
    # Processa resposta (pode enviar áudio, template ou texto)
    try:
        final_message, metadata = await process_llm_response(
            reply=reply,
            phone_number=phone_to_send,
            thread_id=t.id,
            db_session=db
        )
        
        # Salva mensagem no banco
        m_assist = Message(thread_id=t.id, role="assistant", content=final_message)
        db.add(m_assist)
        db.commit()
        db.refresh(m_assist)

        await _broadcast(
            t.id,
            {"type": "message.created", "message": {"id": m_assist.id, "role": "assistant", "content": final_message}},
        )
        
        logger.info(f"[WEBHOOK-TWILIO] ✅ Response processed and sent. Metadata: {metadata}")
            
    except Exception as e:
        logger.error(f"[WEBHOOK-TWILIO] ❌ Error processing response: {str(e)}", exc_info=True)
        # Tenta enviar mensagem de erro
        try:
            error_msg = "Desculpe, houve um problema técnico. Nossa equipe foi notificada."
            await asyncio.to_thread(twilio_provider.send_text, phone_to_send, error_msg, "BOT")
        except:
            logger.error(f"[WEBHOOK-TWILIO] Failed to send error message too")
    
    return {"status": "ok"}

# -----------------------------
# Stats (dashboard)
# -----------------------------
from datetime import timezone, datetime

@app.get("/stats")
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Total de threads (todas, compartilhadas)
    threads_count = (
        db.query(func.count(Thread.id))
        .scalar()
    ) or 0

    # Contagem de mensagens por role (todas)
    q_msgs = (
        db.query(
            func.sum(case((Message.role == "user", 1), else_=0)),
            func.sum(case((Message.role == "assistant", 1), else_=0)),
            func.count(Message.id),
        )
        .join(Thread, Thread.id == Message.thread_id)
    )
    user_msgs, assistant_msgs, total_msgs = q_msgs.one() if q_msgs else (0, 0, 0)
    user_msgs = int(user_msgs or 0)
    assistant_msgs = int(assistant_msgs or 0)
    total_msgs = int(total_msgs or 0)

    # Última atividade real (todas)
    last_msg = (
        db.query(Message.created_at)
        .join(Thread, Thread.id == Message.thread_id)
        .order_by(Message.id.desc())
        .first()
    )
    last_activity = last_msg[0] if last_msg else None

    # ------- Mensagens por dia (reais) -------
    # agrupa created_at por dia, separando user x assistant (todas)
    rows_day = (
        db.query(
            func.date_trunc("day", Message.created_at).label("day"),
            func.sum(case((Message.role == "user", 1), else_=0)).label("user"),
            func.sum(case((Message.role == "assistant", 1), else_=0)).label("assistant"),
        )
        .join(Thread, Thread.id == Message.thread_id)
        .group_by(func.date_trunc("day", Message.created_at))
        .order_by(func.date_trunc("day", Message.created_at).asc())
        .all()
    )
    messages_by_day = []
    for r in rows_day:
        day = r[0]
        # normaliza pra YYYY-MM-DD (sem timezone)
        if hasattr(day, "date"):
            date_str = day.date().isoformat()
        else:
            date_str = str(day)[:10]
        messages_by_day.append({
            "date": date_str,
            "user": int(r.user or 0),
            "assistant": int(r.assistant or 0),
        })

    # ------- Tempo médio de resposta da IA (em ms) -------
    # percorre mensagens por thread e mede delta entre a última user e a próxima assistant
    # Obs.: isso é O(n) em cima do histórico do usuário.
    msgs_all = (
        db.query(Message.thread_id, Message.role, Message.created_at)
        .join(Thread, Thread.id == Message.thread_id)
        .order_by(Message.thread_id.asc(), Message.id.asc())
        .all()
    )
    last_user_ts_by_thread: dict[int, datetime] = {}
    deltas_ms: list[int] = []
    for thread_id, role, created_at in msgs_all:
        if role == "user":
            last_user_ts_by_thread[thread_id] = created_at
        elif role == "assistant":
            ts_user = last_user_ts_by_thread.get(thread_id)
            if ts_user and created_at and created_at >= ts_user:
                delta = (created_at - ts_user).total_seconds() * 1000.0
                # limita outliers absurdos, se quiser
                if 0 <= delta < (7 * 24 * 60 * 60 * 1000):  # < 7 dias
                    deltas_ms.append(int(delta))

    avg_assistant_response_ms = int(sum(deltas_ms) / len(deltas_ms)) if deltas_ms else None

    # ------- Distribuição de leads por temperatura -------
    lead_levels = (
        db.query(
            Thread.lead_level,
            func.count(Thread.id).label("count")
        )
        .group_by(Thread.lead_level)
        .all()
    )
    lead_distribution = {"quente": 0, "morno": 0, "frio": 0, "desconhecido": 0}
    for level, count in lead_levels:
        if level in lead_distribution:
            lead_distribution[level] = int(count or 0)
        else:
            # Leads sem classificação
            lead_distribution["desconhecido"] += int(count or 0)
    
    # Se não tiver nenhum lead classificado, conta os que não têm lead_level
    if sum(lead_distribution.values()) < threads_count:
        lead_distribution["desconhecido"] = threads_count - sum([lead_distribution["quente"], lead_distribution["morno"], lead_distribution["frio"]])

    # ------- Mensagens por hora do dia (0-23) -------
    rows_hour = (
        db.query(
            func.extract("hour", Message.created_at).label("hour"),
            func.count(Message.id).label("count")
        )
        .join(Thread, Thread.id == Message.thread_id)
        .group_by(func.extract("hour", Message.created_at))
        .order_by(func.extract("hour", Message.created_at).asc())
        .all()
    )
    messages_by_hour = [0] * 24
    for hour, count in rows_hour:
        h = int(hour or 0)
        if 0 <= h < 24:
            messages_by_hour[h] = int(count or 0)

    # ------- Threads criadas por dia (últimos 30 dias) -------
    from datetime import timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    threads_by_day = (
        db.query(
            func.date_trunc("day", Thread.created_at).label("day"),
            func.count(Thread.id).label("count")
        )
        .filter(Thread.created_at >= thirty_days_ago)
        .group_by(func.date_trunc("day", Thread.created_at))
        .order_by(func.date_trunc("day", Thread.created_at).asc())
        .all()
    )
    threads_growth = []
    for r in threads_by_day:
        day = r[0]
        if hasattr(day, "date"):
            date_str = day.date().isoformat()
        else:
            date_str = str(day)[:10]
        threads_growth.append({
            "date": date_str,
            "count": int(r.count or 0)
        })

    # ------- Distribuição por origem -------
    origins = (
        db.query(
            Thread.origin,
            func.count(Thread.id).label("count")
        )
        .group_by(Thread.origin)
        .all()
    )
    origin_distribution = []
    for origin, count in origins:
        origin_name = origin or "sem_origem"
        origin_distribution.append({
            "origin": origin_name.replace("_", " ").title(),
            "count": int(count or 0)
        })

    # ------- Taxa de resposta (threads com pelo menos 1 resposta do assistente) -------
    threads_with_response = (
        db.query(func.count(func.distinct(Message.thread_id)))
        .filter(Message.role == "assistant")
        .scalar()
    ) or 0
    response_rate = (threads_with_response / threads_count * 100) if threads_count > 0 else 0

    return {
        "threads": threads_count,
        "user_messages": user_msgs,
        "assistant_messages": assistant_msgs,
        "total_messages": total_msgs,
        "last_activity": last_activity,
        "messages_by_day": messages_by_day,
        "avg_assistant_response_ms": avg_assistant_response_ms,
        "lead_levels": lead_distribution,  # ✅ distribuição de leads
        "messages_by_hour": messages_by_hour,  # ✅ mensagens por hora (24 posições)
        "threads_growth": threads_growth,  # ✅ crescimento de conversas
        "origin_distribution": origin_distribution,  # ✅ distribuição por origem
        "response_rate": round(response_rate, 1),  # ✅ taxa de resposta (%)
    }


# -----------------------------
# WebSocket por thread (tempo real)
# -----------------------------
@app.websocket("/ws/threads/{thread_id}")
async def ws_thread(
    websocket: WebSocket,
    thread_id: str,
    token: Optional[str] = Query(None),
):
    # Authenticate before accepting connection
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return
    
    # Get database session manually (can't use Depends in WebSocket)
    db = SessionLocal()
    try:
        user = _user_from_query_token(db, token)
        # Verify thread belongs to user
        t = db.get(Thread, int(thread_id))
        if not t:
            await websocket.close(code=1008, reason="Thread not found")
            return
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return
    finally:
        db.close()
    
    await hub.connect(thread_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(thread_id, websocket)


# -----------------------------
# Webhook para atualização de dados WooCommerce
# -----------------------------
@app.post("/webhooks/wc-update")
async def wc_update_webhook(
    request: Request,
    x_wc_webhook_source: Optional[str] = Header(None, alias="X-WC-Webhook-Source"),
):
    """
    Endpoint para receber webhooks do WooCommerce quando produtos são atualizados.
    Pode ser configurado no WooCommerce: Configurações > Avançado > Webhooks
    """
    import subprocess
    import os
    
    # Verifica se é um webhook válido (opcional: adicionar validação de assinatura)
    # Por enquanto, aceita qualquer requisição POST
    
    try:
        # Executa o script de atualização em background
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "collect_wc_data.py")
        
        # Executa o script Python
        process = subprocess.Popen(
            ["python3", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(script_path)
        )
        
        # Não espera o processo terminar (executa em background)
        # O processo continuará rodando mesmo após a resposta
        
        return {
            "status": "accepted",
            "message": "Atualização de dados iniciada em background"
        }
    except Exception as e:
        logging.error(f"Erro ao processar webhook WooCommerce: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/admin/update-wc-data")
async def manual_update_wc_data(
    current_user: User = Depends(get_current_user),
):
    """
    Endpoint manual para atualizar dados do WooCommerce (requer autenticação)
    """
    import subprocess
    import os
    
    try:
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "collect_wc_data.py")
        
        # Executa o script e captura a saída
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(script_path),
            timeout=300  # 5 minutos de timeout
        )
        
        if result.returncode == 0:
            return {
                "status": "success",
                "message": "Dados atualizados com sucesso",
                "output": result.stdout
            }
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": "Erro ao atualizar dados",
                    "error": result.stderr
                }
            )
    except subprocess.TimeoutExpired:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Timeout ao atualizar dados"}
        )
    except Exception as e:
        logging.error(f"Erro ao atualizar dados WooCommerce: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
