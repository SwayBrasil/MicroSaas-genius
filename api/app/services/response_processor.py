# api/app/services/response_processor.py
"""Processa respostas do LLM e envia áudios/imagens/templates conforme necessário"""
import os
import json
import re
import asyncio
import traceback
from typing import Dict, Any, Optional, Tuple

from .multimedia_parser import parse_multimedia_reply, validate_actions
from .assets_library import resolve_audio_url, resolve_image_url
from .template_loader import load_template, get_audio_path, get_template_by_code
from ..providers import twilio


async def process_llm_response(
    reply: Any,
    phone_number: str,
    thread_id: Optional[int] = None,
    db_session = None
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Processa a resposta do LLM e envia áudios/imagens/templates conforme necessário.
    
    Suporta múltiplas ações em ordem:
    - [Áudio enviado: audio_id]
    - [Imagem enviada: image_id]
    - [Imagens enviadas: id1, id2, id3]
    - Texto normal
    
    Args:
        reply: Resposta do LLM (pode ser string ou dict com response_type)
        phone_number: Número do destinatário (formato E.164)
        thread_id: ID da thread (opcional, para salvar metadados)
        db_session: Sessão do banco (opcional, para atualizar thread)
    
    Returns:
        Tuple de (mensagem_final, metadados)
        - mensagem_final: Texto final a ser salvo no banco
        - metadados: Dict com informações adicionais (next_stage, etc.)
    """
    print(f"[RESPONSE_PROCESSOR] 🔍 Iniciando processamento. Tipo do reply: {type(reply).__name__}")
    
    metadata = {}
    final_message_parts = []
    
    # Converte reply para string se necessário
    reply_str = ""
    if isinstance(reply, dict):
        # Se for dict, tenta extrair message ou converter para string
        reply_str = reply.get("message", json.dumps(reply, ensure_ascii=False))
        # Processa metadados do dict
        if "next_stage" in reply:
            metadata["next_stage"] = reply["next_stage"]
            _update_thread_stage(thread_id, reply["next_stage"], db_session)
    else:
        reply_str = str(reply).strip()
    
    # Remove tracinhos de formatação de código (```txt, ```, etc)
    if reply_str:
        # Remove blocos de código markdown
        reply_str = re.sub(r'^```txt\s*\n?', '', reply_str, flags=re.MULTILINE)
        reply_str = re.sub(r'^```\s*\n?', '', reply_str, flags=re.MULTILINE)
        reply_str = re.sub(r'\n?```\s*$', '', reply_str, flags=re.MULTILINE)
        reply_str = reply_str.strip()
    
    if not reply_str:
        return "", metadata
    
    # Parse da resposta em ações ordenadas
    actions = parse_multimedia_reply(reply_str)
    
    # Valida ações
    is_valid, error_msg = validate_actions(actions)
    if not is_valid:
        print(f"[RESPONSE_PROCESSOR] ❌ Erro na validação: {error_msg}")
        # Fallback: envia como texto simples
        try:
            sid = await asyncio.to_thread(twilio.send_text, phone_number, reply_str, "BOT")
            if not sid:
                print(f"[RESPONSE_PROCESSOR] ⚠️ Twilio não configurado. Fallback não enviado.")
            return reply_str, metadata
        except Exception as e:
            print(f"[RESPONSE_PROCESSOR] ❌ Erro ao enviar fallback: {e}")
            return reply_str, metadata
    
    print(f"[RESPONSE_PROCESSOR] ✅ {len(actions)} ação(ões) detectada(s)")
    
    # Processa cada ação na ordem
    for i, action in enumerate(actions):
        action_type = action.get("type")
        print(f"[RESPONSE_PROCESSOR] 🔄 Processando ação {i+1}/{len(actions)}: {action_type}")
        
        try:
            if action_type == "audio":
                audio_id = action.get("audio_id", "").strip()
                if audio_id:
                    audio_url = resolve_audio_url(audio_id)
                    if audio_url:
                        try:
                            sid = await asyncio.to_thread(twilio.send_audio, phone_number, audio_url, "BOT")
                            if sid:
                                print(f"[RESPONSE_PROCESSOR] ✅ Áudio enviado: {audio_id}")
                                # NÃO adiciona ao final_message_parts - comando é processado, não aparece no texto
                            else:
                                print(f"[RESPONSE_PROCESSOR] ⚠️ Twilio não configurado. Áudio não enviado: {audio_id}")
                                # Não adiciona erro ao texto final
                        except Exception as e:
                            print(f"[RESPONSE_PROCESSOR] ❌ Erro ao enviar áudio: {e}")
                            # Não adiciona erro ao texto final
                    else:
                        print(f"[RESPONSE_PROCESSOR] ❌ Áudio não encontrado: {audio_id}")
                        # Não adiciona erro ao texto final
            
            elif action_type == "image":
                image_id = action.get("image_id", "").strip()
                if image_id:
                    image_url = resolve_image_url(image_id)
                    if image_url:
                        try:
                            sid = await asyncio.to_thread(twilio.send_image, phone_number, image_url, "BOT")
                            if sid:
                                print(f"[RESPONSE_PROCESSOR] ✅ Imagem enviada: {image_id}")
                                # NÃO adiciona ao final_message_parts - comando é processado, não aparece no texto
                            else:
                                print(f"[RESPONSE_PROCESSOR] ⚠️ Twilio não configurado. Imagem não enviada: {image_id}")
                                # Não adiciona erro ao texto final
                        except Exception as e:
                            print(f"[RESPONSE_PROCESSOR] ❌ Erro ao enviar imagem: {e}")
                            # Não adiciona erro ao texto final
                    else:
                        print(f"[RESPONSE_PROCESSOR] ❌ Imagem não encontrada: {image_id}")
                        # Não adiciona erro ao texto final
            
            elif action_type == "text":
                message = action.get("message", "").strip()
                if message:
                    try:
                        sid = await asyncio.to_thread(twilio.send_text, phone_number, message, "BOT")
                        if sid:
                            print(f"[RESPONSE_PROCESSOR] ✅ Texto enviado: {len(message)} chars")
                        else:
                            print(f"[RESPONSE_PROCESSOR] ⚠️ Twilio não configurado. Texto não enviado: {len(message)} chars")
                        final_message_parts.append(message)
                    except Exception as e:
                        print(f"[RESPONSE_PROCESSOR] ❌ Erro ao enviar texto: {e}")
                        final_message_parts.append(message)  # Ainda salva no banco mesmo se não enviar
            
            # Delay entre ações para garantir ordem no WhatsApp e evitar spam
            if i < len(actions) - 1:
                # Delay maior para mídia (áudio/imagem) para garantir que termine antes da próxima
                if action_type in ["audio", "image"]:
                    await asyncio.sleep(3.0)  # 3 segundos entre mídias
                else:
                    await asyncio.sleep(2.0)  # 2 segundos entre textos
                
        except Exception as e:
            print(f"[RESPONSE_PROCESSOR] ❌ Erro ao processar ação {i+1} ({action_type}): {e}")
            print(f"[RESPONSE_PROCESSOR] Traceback: {traceback.format_exc()}")
            final_message_parts.append(f"[Erro ao processar {action_type}]")
    
    # Monta mensagem final para salvar no banco
    final_message = "\n\n".join(final_message_parts) if final_message_parts else reply_str
    
    # Atualiza etapa se necessário (detecta padrões na resposta)
    _detect_and_update_stage(actions, thread_id, db_session)
    
    return final_message, metadata


def _update_thread_stage(thread_id: Optional[int], next_stage: str, db_session):
    """Atualiza stage_id da thread se tiver db_session"""
    if not thread_id or not db_session or not next_stage:
        return
    
    try:
        from ..models import Thread
        thread = db_session.get(Thread, thread_id)
        if thread:
            current_meta = {}
            if thread.meta:
                if isinstance(thread.meta, dict):
                    current_meta = thread.meta.copy()
                elif isinstance(thread.meta, str):
                    try:
                        current_meta = json.loads(thread.meta)
                    except:
                        pass
            
            current_meta["next_stage"] = next_stage
            if next_stage and str(next_stage).isdigit():
                current_meta["stage_id"] = next_stage
                print(f"[RESPONSE_PROCESSOR] ✅ Atualizando stage_id para {next_stage}")
            
            thread.meta = current_meta
            db_session.commit()
            db_session.refresh(thread)
    except Exception as e:
        print(f"[RESPONSE_PROCESSOR] ⚠️ Erro ao atualizar stage: {e}")


def _detect_and_update_stage(actions: list, thread_id: Optional[int], db_session):
    """Detecta padrões nas ações e atualiza etapa do funil"""
    if not thread_id or not db_session:
        return
    
    try:
        from ..models import Thread
        from .funnel_stage_manager import update_stage_from_event
        
        thread = db_session.get(Thread, thread_id)
        if not thread:
            return
        
        # Detecta se enviou áudio de planos
        for action in actions:
            if action.get("type") == "audio":
                audio_id = action.get("audio_id", "").lower()
                if "explicacao_planos" in audio_id or "audio3" in audio_id:
                    current_meta = {}
                    if thread.meta:
                        if isinstance(thread.meta, dict):
                            current_meta = thread.meta.copy()
                        elif isinstance(thread.meta, str):
                            try:
                                current_meta = json.loads(thread.meta)
                            except:
                                pass
                    
                    updated_meta = update_stage_from_event(current_meta, "IA_SENT_EXPLICACAO_PLANOS")
                    thread.meta = updated_meta
                    thread.lead_level = updated_meta.get("lead_level")
                    db_session.commit()
                    db_session.refresh(thread)
                    print(f"[RESPONSE_PROCESSOR] ✅ Etapa atualizada para 'aquecido' após envio de planos")
                    break
    except Exception as e:
        print(f"[RESPONSE_PROCESSOR] ⚠️ Erro ao detectar stage: {e}")
