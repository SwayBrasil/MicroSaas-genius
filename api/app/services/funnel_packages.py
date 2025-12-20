# api/app/services/funnel_packages.py
"""
Pacotes fixos do funil - execução determinística sem LLM.
Garante ordem, quebras e delays fixos para pontos críticos.
"""
import asyncio
import os
from typing import List, Dict, Any, Optional, Tuple

from ..providers import twilio as twilio_provider
from .assets_library import resolve_audio_url, resolve_image_url


# ==================== DELAYS FIXOS ====================
# CRÍTICO: Delays aumentados para garantir que WhatsApp processe e entregue cada mensagem
# antes de enviar a próxima. WhatsApp pode reordenar se enviarmos muito rápido.
DELAY_AUDIO = 0.0  # Áudio inicia imediatamente
DELAY_BETWEEN_IMAGES = 2.5  # Entre cada imagem (2.5s) - CRÍTICO para ordem
DELAY_AFTER_IMAGES = 5.0  # Após TODAS as imagens - espera 5s antes de enviar texto
DELAY_BETWEEN_TEXTS = 2.0  # Entre mensagens de texto
DELAY_AFTER_AUDIO = 3.0  # Após áudio antes de texto/imagem (3.0s) - CRÍTICO para ordem


# ==================== TEMPLATES FIXOS ====================

# FASE 2 - Templates de texto
FASE_2_TEXTO_CURTO = "Entendo, gata. Isso é bem comum e dá pra resolver com estratégia certa."
FASE_2_PERGUNTA = "Me conta: o que tá faltando pra tu dar esse passo?"

# FASE 3 - Templates de texto
FASE_3_INTRO = "Amo essa atitude. Vou te mandar um áudio bem rápido explicando os planos."
FASE_3_PLANOS = """✅ Plano Mensal — R$69,90/mês

• Acesso à base do LIFE: treinos, planos alimentares e aulas sobre disciplina e motivação.

• Pode cancelar quando quiser.

🔥 Plano Anual — R$598,80 (ou 12x de R$49,90)

• Acesso COMPLETO a tudo no LIFE + aulas extras com médicas, nutricionistas e psicólogas.

• Inclui o módulo exclusivo do Shape Slim.

• Pode parcelar em até 12x."""
FASE_3_PERGUNTA = "Agora me fala: qual plano faz mais sentido pra você?"


# ==================== PACOTE FASE 2 (DOR/OBJETIVO) ====================

async def execute_pacote_fase_2(
    phone_number: str,
    audio_id: str = "audio2_dor_generica",
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Executa PACOTE_FASE_2 fixo: áudio + 8 imagens + textos.
    
    Args:
        phone_number: Número do destinatário (E.164)
        audio_id: ID do áudio (padrão: audio2_dor_generica)
        db_session: Sessão do banco (opcional)
        thread_id: ID da thread (opcional)
    
    Returns:
        Tuple de (mensagens_enviadas, metadados)
    """
    messages_sent = []
    metadata = {
        "package": "PACOTE_FASE_2",
        "audio_id": audio_id,
        "images_count": 8,
        "texts_count": 1  # CORREÇÃO A: Apenas 1 texto (pergunta final)
    }
    
    # 1. Enviar áudio (delay: 0s)
    # ORDEM GARANTIDA: Sequencial com await - NUNCA paralelo
    audio_url = resolve_audio_url(audio_id)
    if audio_url:
        try:
            sid = await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
            if sid:
                messages_sent.append(f"[Áudio enviado: {audio_id}]")
                print(f"[PACOTE_FASE_2] ✅ [ORDEM 1/10] Áudio enviado: {audio_id}")
            else:
                print(f"[PACOTE_FASE_2] ⚠️ Twilio não configurado. Áudio não enviado.")
        except Exception as e:
            print(f"[PACOTE_FASE_2] ❌ Erro ao enviar áudio: {e}")
    else:
        print(f"[PACOTE_FASE_2] ❌ Áudio não encontrado: {audio_id}")
    
    # Delay após áudio - CRÍTICO para garantir ordem de entrega
    await asyncio.sleep(DELAY_AFTER_AUDIO)  # 3.0s após áudio
    print(f"[PACOTE_FASE_2] ⏳ Delay de {DELAY_AFTER_AUDIO}s após áudio aplicado (GARANTIR ORDEM DE ENTREGA)")
    
    # 2. Enviar 8 imagens de prova social SEM legenda (delay: 0.5s entre cada)
    # CORREÇÃO: Todas as imagens SEM legenda - texto vem DEPOIS como mensagem separada
    image_ids = [
        "img_resultado_01", "img_resultado_02", "img_resultado_03", "img_resultado_04",
        "img_resultado_05", "img_resultado_06", "img_resultado_07", "img_resultado_08"
    ]
    
    # CORREÇÃO: Garantir ordem sequencial - todas as imagens ANTES do texto
    # ORDEM GARANTIDA: Loop sequencial com await - NUNCA paralelo
    for i, image_id in enumerate(image_ids):
        image_url = resolve_image_url(image_id)
        if image_url:
            try:
                # Todas as imagens SEM legenda (incluindo a última)
                # ORDEM: Sequencial com await - garante ordem determinística
                sid = await asyncio.to_thread(twilio_provider.send_image, phone_number, image_url, "BOT")
                if sid:
                    messages_sent.append(f"[Imagem enviada: {image_id}]")
                    print(f"[PACOTE_FASE_2] ✅ [ORDEM {i+2}/10] Imagem {i+1}/8 enviada: {image_id}")
                else:
                    print(f"[PACOTE_FASE_2] ⚠️ Twilio não configurado. Imagem não enviada.")
            except Exception as e:
                print(f"[PACOTE_FASE_2] ❌ Erro ao enviar imagem {i+1}: {e}")
        
        # Delay entre imagens para garantir ordem no WhatsApp
        # CRÍTICO: Delay aumentado para garantir que WhatsApp processe e entregue antes da próxima
        # ORDEM GARANTIDA: Delay aplicado ANTES de próxima imagem
        if i < len(image_ids) - 1:
            await asyncio.sleep(DELAY_BETWEEN_IMAGES)  # 2.5s entre cada imagem
            print(f"[PACOTE_FASE_2] ⏳ Delay de {DELAY_BETWEEN_IMAGES}s após imagem {i+1} aplicado (GARANTIR ORDEM DE ENTREGA)")
    
    # Delay após TODAS as 8 imagens - espera 5s antes de enviar texto
    # CRÍTICO: Delay aumentado para garantir que WhatsApp processe todas as imagens antes do texto
    # ORDEM GARANTIDA: Delay aplicado ANTES do texto final
    await asyncio.sleep(DELAY_AFTER_IMAGES)  # 5.0s após última imagem
    print(f"[PACOTE_FASE_2] ⏳ Delay de {DELAY_AFTER_IMAGES}s após TODAS as 8 imagens aplicado (GARANTIR ORDEM DE ENTREGA)")
    
    # 3. Enviar texto final como MENSAGEM SEPARADA (DEPOIS de todas as 8 imagens)
    # CORREÇÃO: Texto vem DEPOIS de todas as imagens, não junto nem no meio
    # ORDEM GARANTIDA: Sequencial com await - NUNCA paralelo
    try:
        sid = await asyncio.to_thread(twilio_provider.send_text, phone_number, FASE_2_PERGUNTA, "BOT")
        if sid:
            messages_sent.append(FASE_2_PERGUNTA)
            print(f"[PACOTE_FASE_2] ✅ [ORDEM 10/10] Texto final enviado como MENSAGEM SEPARADA (DEPOIS de todas as 8 imagens, após {DELAY_AFTER_IMAGES}s)")
        else:
            print(f"[PACOTE_FASE_2] ⚠️ Twilio não configurado. Pergunta não enviada.")
    except Exception as e:
        print(f"[PACOTE_FASE_2] ❌ Erro ao enviar pergunta: {e}")
    
    # Salva mensagens no banco se tiver thread_id e db_session
    if thread_id and db_session:
        from ..models import Message
        for msg_content in messages_sent:
            msg = Message(thread_id=thread_id, role="assistant", content=msg_content)
            db_session.add(msg)
        db_session.commit()
        print(f"[PACOTE_FASE_2] ✅ {len(messages_sent)} mensagens salvas no banco")
    
    return messages_sent, metadata


# ==================== PACOTE FASE 3 (PLANOS) ====================

async def execute_pacote_fase_3(
    phone_number: str,
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Executa PACOTE_FASE_3 fixo: intro + áudio3 + planos + pergunta.
    
    Args:
        phone_number: Número do destinatário (E.164)
        db_session: Sessão do banco (opcional)
        thread_id: ID da thread (opcional)
    
    Returns:
        Tuple de (mensagens_enviadas, metadados)
    """
    messages_sent = []
    metadata = {
        "package": "PACOTE_FASE_3",
        "audio_id": "audio3_explicacao_planos",
        "texts_count": 3
    }
    
    # 1. Enviar mensagem intro curta (delay: 0s)
    # ORDEM GARANTIDA: Sequencial com await - NUNCA paralelo
    try:
        sid = await asyncio.to_thread(twilio_provider.send_text, phone_number, FASE_3_INTRO, "BOT")
        if sid:
            messages_sent.append(FASE_3_INTRO)
            print(f"[PACOTE_FASE_3] ✅ [ORDEM 1/4] Intro enviada")
        else:
            print(f"[PACOTE_FASE_3] ⚠️ Twilio não configurado. Intro não enviada.")
    except Exception as e:
        print(f"[PACOTE_FASE_3] ❌ Erro ao enviar intro: {e}")
    
    # Delay antes do áudio - CRÍTICO para garantir ordem de entrega
    await asyncio.sleep(DELAY_AFTER_AUDIO)  # 3.0s após intro
    print(f"[PACOTE_FASE_3] ⏳ Delay de {DELAY_AFTER_AUDIO}s após intro aplicado (GARANTIR ORDEM DE ENTREGA)")
    
    # 2. Enviar áudio3 (delay: 3.0s após intro)
    # CRÍTICO: Áudio SEMPRE antes do texto de planos - delay aumentado para garantir ordem
    # ORDEM GARANTIDA: Áudio SEMPRE antes do texto de planos
    audio_id = "audio3_explicacao_planos"
    audio_url = resolve_audio_url(audio_id)
    if audio_url:
        try:
            sid = await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
            if sid:
                messages_sent.append(f"[Áudio enviado: {audio_id}]")
                print(f"[PACOTE_FASE_3] ✅ [ORDEM 2/4] Áudio enviado: {audio_id}")
            else:
                print(f"[PACOTE_FASE_3] ⚠️ Twilio não configurado. Áudio não enviado.")
        except Exception as e:
            print(f"[PACOTE_FASE_3] ❌ Erro ao enviar áudio: {e}")
    else:
        print(f"[PACOTE_FASE_3] ❌ Áudio não encontrado: {audio_id}")
    
    # Delay após áudio antes do texto dos planos - CRÍTICO para garantir ordem de entrega
    await asyncio.sleep(DELAY_AFTER_AUDIO)  # 3.0s após áudio
    print(f"[PACOTE_FASE_3] ⏳ Delay de {DELAY_AFTER_AUDIO}s após áudio aplicado (GARANTIR ORDEM DE ENTREGA)")
    
    # 3. Enviar bloco de planos (delay: 0.5s após áudio - REGRA 4)
    # ORDEM GARANTIDA: Texto DEPOIS do áudio
    try:
        sid = await asyncio.to_thread(twilio_provider.send_text, phone_number, FASE_3_PLANOS, "BOT")
        if sid:
            messages_sent.append(FASE_3_PLANOS)
            print(f"[PACOTE_FASE_3] ✅ [ORDEM 3/4] Planos enviados")
        else:
            print(f"[PACOTE_FASE_3] ⚠️ Twilio não configurado. Planos não enviados.")
    except Exception as e:
        print(f"[PACOTE_FASE_3] ❌ Erro ao enviar planos: {e}")
    
    # Delay antes da pergunta (mantido 1.2s entre textos)
    await asyncio.sleep(DELAY_BETWEEN_TEXTS)
    print(f"[PACOTE_FASE_3] ⏳ Delay de {DELAY_BETWEEN_TEXTS}s após planos aplicado")
    
    # 4. Enviar pergunta final em mensagem separada (delay: 1.2s após planos)
    # ORDEM GARANTIDA: Pergunta DEPOIS do texto de planos
    try:
        sid = await asyncio.to_thread(twilio_provider.send_text, phone_number, FASE_3_PERGUNTA, "BOT")
        if sid:
            messages_sent.append(FASE_3_PERGUNTA)
            print(f"[PACOTE_FASE_3] ✅ [ORDEM 4/4] Pergunta enviada")
        else:
            print(f"[PACOTE_FASE_3] ⚠️ Twilio não configurado. Pergunta não enviada.")
    except Exception as e:
        print(f"[PACOTE_FASE_3] ❌ Erro ao enviar pergunta: {e}")
    
    # Marca que planos foram explicados
    if thread_id and db_session:
        try:
            from ..models import Thread
            from datetime import datetime
            thread = db_session.get(Thread, thread_id)
            if thread:
                meta = thread.meta or {}
                if isinstance(meta, str):
                    try:
                        import json
                        meta = json.loads(meta)
                    except:
                        meta = {}
                meta["plans_already_explained"] = True
                meta["plans_sent_at"] = datetime.now().isoformat()
                thread.meta = meta
                db_session.commit()
                print(f"[PACOTE_FASE_3] ✅ Marcado plans_already_explained=True")
        except Exception as e:
            print(f"[PACOTE_FASE_3] ⚠️ Erro ao marcar plans_already_explained: {e}")
    
    # Salva mensagens no banco se tiver thread_id e db_session
    if thread_id and db_session:
        from ..models import Message
        for msg_content in messages_sent:
            msg = Message(thread_id=thread_id, role="assistant", content=msg_content)
            db_session.add(msg)
        db_session.commit()
        print(f"[PACOTE_FASE_3] ✅ {len(messages_sent)} mensagens salvas no banco")
    
    return messages_sent, metadata

