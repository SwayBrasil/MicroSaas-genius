# app/routers/takeover.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import asyncio
from app.db import get_db
from app.models import Thread, Message, User
from app.schemas import TakeoverToggle, HumanReplyBody
from app.auth import get_current_user

# ✅ provider Twilio
from app.providers import twilio as twilio_provider
from app.services.assets_library import resolve_audio_url

router = APIRouter(prefix="/threads", tags=["takeover"])

class SendAudioRequest(BaseModel):
    audio_id: str  # ID do áudio (ex: "audio1_boas_vindas")

@router.post("/{thread_id}/takeover")
def set_takeover(thread_id: int, body: TakeoverToggle,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(404, "Thread not found")
    t.human_takeover = bool(body.active)
    db.add(t); db.commit(); db.refresh(t)
    return {"ok": True, "human_takeover": t.human_takeover}

@router.post("/{thread_id}/human-reply")
def human_reply(thread_id: int, body: HumanReplyBody,
                user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(404, "Thread not found")

    # 1) salva no histórico (marcado como mensagem humana)
    msg = Message(thread_id=t.id, role="assistant", content=body.content, is_human=True)
    db.add(msg); db.commit(); db.refresh(msg)

    # 2) envia para o cliente via Twilio
    phone = (t.external_user_phone or "").strip()
    if not phone:
        print(f"[HUMAN-REPLY] thread {t.id} sem external_user_phone; nada enviado")
        return {"ok": True, "message_id": msg.id, "sent": False}

    try:
        sid = twilio_provider.send_text(phone, body.content)  # <- síncrono, sem await
        if sid:
            print(f"[HUMAN-REPLY][TWILIO] thread={t.id} to={phone} sid={sid}")
            sent = True
        else:
            print(f"[HUMAN-REPLY][TWILIO] ⚠️ Twilio não configurado. Mensagem não enviada.")
            sent = False
    except Exception as e:
        print(f"[HUMAN-REPLY][TWILIO][ERROR] thread={t.id} to={phone} err={e}")
        sent = False

    return {"ok": True, "message_id": msg.id, "sent": sent}

@router.post("/{thread_id}/send-audio")
async def send_audio(thread_id: int, body: SendAudioRequest,
                     user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """
    Dispara um áudio manualmente para o contato da thread.
    """
    t = db.get(Thread, thread_id)
    if not t:
        raise HTTPException(404, "Thread not found")

    phone = (t.external_user_phone or "").strip()
    if not phone:
        raise HTTPException(400, "Thread sem número de telefone")

    # Resolve URL do áudio
    audio_url = resolve_audio_url(body.audio_id)
    if not audio_url:
        raise HTTPException(404, f"Áudio não encontrado: {body.audio_id}")

    try:
        # Envia áudio via Twilio
        sid = await asyncio.to_thread(twilio_provider.send_audio, phone, audio_url, "HUMANO")
        if not sid:
            raise HTTPException(500, "Twilio não configurado ou erro ao enviar áudio")

        # Salva mensagem no histórico marcando como enviada manualmente
        msg_content = f"[Áudio enviado manualmente: {body.audio_id}]"
        msg = Message(thread_id=t.id, role="assistant", content=msg_content, is_human=True)
        db.add(msg)
        db.commit()
        db.refresh(msg)

        return {"ok": True, "message_id": msg.id, "audio_id": body.audio_id, "sent": True, "sid": sid}
    except Exception as e:
        print(f"[SEND-AUDIO][ERROR] thread={t.id} audio_id={body.audio_id} err={e}")
        raise HTTPException(500, f"Erro ao enviar áudio: {str(e)}")
