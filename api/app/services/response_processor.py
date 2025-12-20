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
    
    # 🚨 VERIFICAÇÃO DE DUPLICAÇÃO ANTES DE PROCESSAR
    # Verifica se já enviou áudio 2 + imagens recentemente (últimas 30 minutos)
    if thread_id and db_session:
        from datetime import datetime, timedelta
        from ..models import Message
        
        recent_messages = (
            db_session.query(Message)
            .filter(
                Message.thread_id == thread_id,
                Message.role == "assistant",
                Message.created_at >= datetime.utcnow() - timedelta(minutes=30)
            )
            .order_by(Message.created_at.desc())
            .all()
        )
        
        # Verifica se a resposta atual contém áudio 2 + imagens
        has_audio2_in_reply = "[Áudio enviado: audio2" in reply_str.lower() or "[Áudio enviada: audio2" in reply_str.lower()
        has_images_in_reply = "img_resultado" in reply_str.lower()
        
        if has_audio2_in_reply and has_images_in_reply:
            # Verifica se já enviou isso recentemente
            for msg in recent_messages:
                content = msg.content or ""
                if ("[Áudio enviad" in content and "audio2" in content.lower() and 
                    "img_resultado" in content):
                    print(f"[RESPONSE_PROCESSOR] 🚨 BLOQUEIO DE DUPLICAÇÃO! Thread {thread_id} tentou enviar áudio 2 + imagens novamente. Bloqueando.")
                    # Retorna apenas texto sem as ações duplicadas
                    # Remove comandos de áudio e imagem, mantém apenas texto
                    reply_str = re.sub(r'\[Áudio enviado:.*?\]', '', reply_str, flags=re.IGNORECASE)
                    reply_str = re.sub(r'\[Áudio enviada:.*?\]', '', reply_str, flags=re.IGNORECASE)
                    reply_str = re.sub(r'\[Imagem enviada:.*?\]', '', reply_str, flags=re.IGNORECASE)
                    reply_str = re.sub(r'\[Imagens enviadas:.*?\]', '', reply_str, flags=re.IGNORECASE)
                    reply_str = reply_str.strip()
                    
                    # Se sobrou apenas texto, adiciona contexto
                    if reply_str:
                        reply_str = f"Entendi! Você já está interessada nos planos. {reply_str}"
                    else:
                        reply_str = "Entendi! Você já está interessada nos planos. Deixa eu te mostrar as opções disponíveis."
                    break
    
    # Parse da resposta em ações ordenadas
    actions = parse_multimedia_reply(reply_str)
    
    # REGRA 2: Detecção por CONTEÚDO da resposta (não por intent do usuário)
    # A decisão NÃO DEPENDE DO USUÁRIO, e sim do CONTEÚDO da resposta gerada pelo LLM
    from .content_detector import classify_response_content, is_checkout
    
    content_type = classify_response_content(reply_str)
    print(f"[RESPONSE_PROCESSOR] 🎯 Conteúdo detectado: {content_type}")
    
    # REGRA 5: Se for checkout, NUNCA injeta áudio3
    if content_type == "CHECKOUT":
        print(f"[RESPONSE_PROCESSOR] ⚠️ Conteúdo é CHECKOUT - NÃO injeta áudio3 (REGRA 5)")
    else:
        # REGRA 2: Injeta áudio3 se for explicação de planos (por conteúdo, não intent)
        actions = _inject_audio3_if_plans_detected_by_content(
            actions, reply_str, thread_id, db_session, content_type
        )
    
    # CORREÇÃO: Divide mensagem de planos em 2 partes (ANTES de mesclar textos)
    actions = _split_plans_message(actions)
    
    # CORREÇÃO OPCIONAL: Mescla textos sequenciais (DEPOIS da divisão de planos)
    actions = _merge_sequential_texts(actions)
    
    # Debug: mostra ações detectadas
    print(f"[RESPONSE_PROCESSOR] 🔍 Ações detectadas: {len(actions)}")
    for i, action in enumerate(actions):
        print(f"[RESPONSE_PROCESSOR]   [{i+1}] {action.get('type')}: {action.get('audio_id') or action.get('image_id') or action.get('message', '')[:50]}")
    
    # Valida ações
    is_valid, error_msg = validate_actions(actions)
    if not is_valid:
        print(f"[RESPONSE_PROCESSOR] ❌ Erro na validação: {error_msg}")
        print(f"[RESPONSE_PROCESSOR] 📝 Resposta original (primeiros 500 chars): {reply_str[:500]}")
        # Fallback: envia como texto simples
        try:
            sid = await asyncio.to_thread(twilio.send_text, phone_number, reply_str, "BOT")
            if not sid:
                print(f"[RESPONSE_PROCESSOR] ⚠️ Twilio não configurado. Fallback não enviado.")
            return reply_str, metadata
        except Exception as e:
            print(f"[RESPONSE_PROCESSOR] ❌ Erro ao enviar fallback: {e}")
            return reply_str, metadata
    
    print(f"[RESPONSE_PROCESSOR] ✅ {len(actions)} ação(ões) detectada(s) e validadas")
    
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
            
            # CRÍTICO: Delays aumentados para garantir ordem de entrega no WhatsApp
            # WhatsApp pode reordenar mensagens se enviarmos muito rápido
            if i < len(actions) - 1:
                next_action_type = actions[i + 1].get("type") if i + 1 < len(actions) else None
                
                # Delay após áudio - CRÍTICO para ordem
                if action_type == "audio":
                    await asyncio.sleep(3.0)  # 3.0s após áudio - garante entrega antes da próxima
                    print(f"[RESPONSE_PROCESSOR] ⏳ Delay de 3.0s após áudio aplicado (garantir ordem)")
                # Delay entre imagens - CRÍTICO para ordem
                elif action_type == "image":
                    await asyncio.sleep(2.5)  # 2.5s entre imagens - garante entrega antes da próxima
                    print(f"[RESPONSE_PROCESSOR] ⏳ Delay de 2.5s após imagem aplicado (garantir ordem)")
                # Delay após texto (antes de próximo áudio/imagem) - CRÍTICO para ordem
                elif action_type == "text" and next_action_type in ["audio", "image"]:
                    await asyncio.sleep(3.0)  # 3.0s antes de mídia - garante entrega antes da próxima
                    print(f"[RESPONSE_PROCESSOR] ⏳ Delay de 3.0s após texto aplicado (garantir ordem)")
                # Delay entre textos
                else:
                    await asyncio.sleep(2.0)  # 2.0 segundos entre textos
                
        except Exception as e:
            print(f"[RESPONSE_PROCESSOR] ❌ Erro ao processar ação {i+1} ({action_type}): {e}")
            print(f"[RESPONSE_PROCESSOR] Traceback: {traceback.format_exc()}")
            final_message_parts.append(f"[Erro ao processar {action_type}]")
    
    # Monta mensagem final para salvar no banco
    final_message = "\n\n".join(final_message_parts) if final_message_parts else reply_str
    
    # Atualiza etapa se necessário (detecta padrões na resposta)
    _detect_and_update_stage(actions, thread_id, db_session)
    
    return final_message, metadata


def _inject_audio3_if_plans_detected_by_content(
    actions: list,
    reply_str: str,
    thread_id: Optional[int],
    db_session,
    content_type: str
) -> list:
    """
    REGRA 2: Injeta áudio3 automaticamente baseado no CONTEÚDO da resposta (não intent do usuário).
    
    A decisão NÃO DEPENDE DO USUÁRIO, e sim do CONTEÚDO da resposta gerada pelo LLM.
    
    REGRA 3: Verifica flags de estado para evitar duplicação.
    REGRA 5: NUNCA injeta se for checkout.
    """
    from .content_detector import is_plan_explanation, is_checkout
    
    # REGRA 5: Se for checkout, NUNCA injeta áudio3
    if is_checkout(reply_str):
        print(f"[POST_PROCESSOR] ⚠️ Conteúdo é CHECKOUT - NÃO injeta áudio3 (REGRA 5)")
        return actions
    
    # REGRA 2: Só injeta se o CONTEÚDO da resposta contém explicação de planos
    if not is_plan_explanation(reply_str):
        print(f"[POST_PROCESSOR] ⚠️ Conteúdo NÃO contém explicação de planos - NÃO injeta áudio3")
        return actions
    
    # Verifica se já tem áudio3 nas ações
    has_audio3 = any(
        action.get("type") == "audio" and 
        ("audio3" in action.get("audio_id", "").lower() or 
         "explicacao_planos" in action.get("audio_id", "").lower())
        for action in actions
    )
    
    if has_audio3:
        print(f"[POST_PROCESSOR] ⚠️ Áudio3 já está nas ações - NÃO injeta novamente")
        return actions
    
    # REGRA 3: Verifica se planos já foram explicados (flags de estado)
    plans_already_explained = False
    if thread_id and db_session:
        try:
            from ..models import Thread
            thread = db_session.get(Thread, thread_id)
            if thread:
                meta = thread.meta or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except:
                        meta = {}
                plans_already_explained = meta.get("plans_already_explained", False) or meta.get("plans_sent_at") is not None
        except Exception as e:
            print(f"[POST_PROCESSOR] ⚠️ Erro ao verificar plans_already_explained: {e}")
    
    # REGRA 3: Se planos já foram explicados, NÃO injeta novamente
    if plans_already_explained:
        print(f"[POST_PROCESSOR] ⚠️ Planos já foram explicados (plans_already_explained=True) - NÃO injeta áudio3 (REGRA 3)")
        return actions
    
    # REGRA 2: Injeta áudio3 no início das ações (ORDEM: áudio primeiro, texto depois)
    audio_action = {
        "type": "audio",
        "audio_id": "audio3_explicacao_planos"
    }
    actions.insert(0, audio_action)
    print(f"[POST_PROCESSOR] ✅ Áudio3 injetado automaticamente (conteúdo: PLAN_EXPLANATION)")
    
    # REGRA 3: Marca que planos foram explicados (flags de estado)
    if thread_id and db_session:
        try:
            from ..models import Thread
            from datetime import datetime
            thread = db_session.get(Thread, thread_id)
            if thread:
                meta = thread.meta or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except:
                        meta = {}
                meta["plans_already_explained"] = True
                meta["plans_sent_at"] = datetime.now().isoformat()
                thread.meta = meta
                db_session.commit()
                print(f"[POST_PROCESSOR] ✅ Marcado plans_already_explained=True (REGRA 3)")
        except Exception as e:
            print(f"[POST_PROCESSOR] ⚠️ Erro ao marcar plans_already_explained: {e}")
    
    return actions


def _split_plans_message(actions: list) -> list:
    """
    Divide mensagem de planos em 4 partes separadas:
    - MSG 1: Plano Mensal (com descrição)
    - MSG 2: Plano Anual (com descrição)
    - MSG 3: Pergunta final
    """
    if not actions:
        return actions
    
    split_actions = []
    
    for action in actions:
        if action.get("type") != "text":
            split_actions.append(action)
            continue
        
        message = action.get("message", "").strip()
        message_lower = message.lower()
        
        # Detecta se contém planos
        has_plans = any(keyword in message_lower for keyword in [
            "plano mensal", "plano anual", "r$69", "r$598", "12x de r$", "r$ 69", "r$ 598"
        ])
        has_final_question = any(phrase in message_lower for phrase in [
            "qual plano faz mais sentido",
            "agora me fala, gata",
            "agora me fala"
        ])
        
        print(f"[PLANS_SPLIT] 🔍 Analisando mensagem: has_plans={has_plans}, has_final_question={has_final_question}")
        if has_plans:
            print(f"[PLANS_SPLIT] 📝 Primeiros 200 chars: {message[:200]}")
        
        # Se tem planos E pergunta final, divide em 4 mensagens
        if has_plans and has_final_question:
            # Remove texto introdutório antes dos planos (se houver)
            # Procura onde começa o primeiro plano (✅ ou 🔥)
            plan_start_patterns = [
                r'✅\s*Plano Mensal',
                r'🔥\s*Plano Anual',
                r'Plano Mensal',
                r'Plano Anual',
            ]
            
            plan_start = -1
            for pattern in plan_start_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    plan_start = match.start()
                    break
            
            if plan_start > 0:
                # Remove texto introdutório antes dos planos
                message = message[plan_start:].strip()
            
            # Procura onde começa a pergunta final
            question_patterns = [
                r'\n\s*Agora me fala[^\n]*',
                r'\n\s*qual plano faz mais sentido[^\n]*',
                r'\n\s*Agora me fala, gata[^\n]*',
                r'Agora me fala[^\n]*',
                r'qual plano faz mais sentido[^\n]*',
            ]
            
            question_start = -1
            best_match = None
            
            for pattern in question_patterns:
                match = re.search(pattern, message, re.IGNORECASE | re.MULTILINE)
                if match:
                    if best_match is None or match.start() > best_match.start():
                        best_match = match
            
            if best_match:
                question_start = best_match.start()
            
            if question_start > 0:
                # Texto dos planos (sem a pergunta final)
                plans_text = message[:question_start].strip()
                # Pergunta final
                question_text = message[question_start:].strip()
                question_text = re.sub(r'^\n+', '', question_text).strip()
                
                # Divide planos em Mensal e Anual
                # Procura onde começa o Plano Anual
                anual_patterns = [
                    r'🔥\s*Plano Anual',
                    r'\n\s*🔥\s*Plano Anual',
                    r'\n\s*Plano Anual',
                ]
                
                anual_start = -1
                for pattern in anual_patterns:
                    match = re.search(pattern, plans_text, re.IGNORECASE | re.MULTILINE)
                    if match:
                        anual_start = match.start()
                        break
                
                if anual_start > 0:
                    # MSG 1: Plano Mensal
                    msg1 = plans_text[:anual_start].strip()
                    # MSG 2: Plano Anual
                    msg2 = plans_text[anual_start:].strip()
                    msg2 = re.sub(r'^\n+', '', msg2).strip()
                    
                    # MSG 3: Pergunta final
                    msg3 = question_text
                    
                    split_actions.append({
                        "type": "text",
                        "message": msg1
                    })
                    split_actions.append({
                        "type": "text",
                        "message": msg2
                    })
                    split_actions.append({
                        "type": "text",
                        "message": msg3
                    })
                    print(f"[PLANS_SPLIT] ✅ Dividido em 3 mensagens:")
                    print(f"[PLANS_SPLIT]   MSG1 - Mensal ({len(msg1)} chars): {msg1[:80]}...")
                    print(f"[PLANS_SPLIT]   MSG2 - Anual ({len(msg2)} chars): {msg2[:80]}...")
                    print(f"[PLANS_SPLIT]   MSG3 - Pergunta ({len(msg3)} chars): {msg3[:80]}...")
                else:
                    # Não conseguiu dividir planos, divide só em 2 (planos + pergunta)
                    split_actions.append({
                        "type": "text",
                        "message": plans_text
                    })
                    split_actions.append({
                        "type": "text",
                        "message": question_text
                    })
                    print(f"[PLANS_SPLIT] ⚠️ Dividido em 2 mensagens (não conseguiu separar planos)")
            else:
                # Não conseguiu dividir, mantém original
                print(f"[PLANS_SPLIT] ⚠️ Não conseguiu dividir mensagem de planos")
                split_actions.append(action)
        else:
            # Não é mensagem de planos, mantém original
            split_actions.append(action)
    
    return split_actions


def _merge_sequential_texts(actions: list) -> list:
    """
    CORREÇÃO OPCIONAL: Mescla múltiplas ações de texto sequenciais em uma só.
    
    Se houver múltiplas actions de texto seguidas, mescla em uma única mensagem,
    a menos que contenham marcadores explícitos de multi-mensagem OU sejam mensagens de planos.
    """
    if len(actions) <= 1:
        return actions
    
    merged = []
    i = 0
    
    while i < len(actions):
        current = actions[i]
        
        # Se não é texto, adiciona direto
        if current.get("type") != "text":
            merged.append(current)
            i += 1
            continue
        
        # Verifica se é mensagem de planos (não mescla mensagens de planos)
        current_text = current.get("message", "").lower()
        is_plans_message = any(keyword in current_text for keyword in [
            "plano mensal", "plano anual", "r$69", "r$598", "12x de r$"
        ])
        
        if is_plans_message:
            # Mensagem de planos: NÃO mescla, mantém separada
            merged.append(current)
            i += 1
            continue
        
        # Coleta textos sequenciais (apenas se não forem planos)
        text_parts = [current.get("message", "").strip()]
        j = i + 1
        
        while j < len(actions) and actions[j].get("type") == "text":
            next_text = actions[j].get("message", "").strip()
            next_text_lower = next_text.lower()
            
            # Verifica se tem marcador explícito de multi-mensagem
            if re.search(r'\[MENSAGEM\s+\d+\]|\[MSG\s+\d+\]', next_text, re.IGNORECASE):
                break  # Para de mesclar se tiver marcador
            
            # Verifica se é mensagem de planos (não mescla com planos)
            is_next_plans = any(keyword in next_text_lower for keyword in [
                "plano mensal", "plano anual", "r$69", "r$598", "12x de r$"
            ])
            if is_next_plans:
                break  # Para de mesclar se próxima for planos
            
            text_parts.append(next_text)
            j += 1
        
        # Se tem mais de 1 texto, mescla
        if len(text_parts) > 1:
            merged_text = "\n\n".join(text_parts)
            merged.append({
                "type": "text",
                "message": merged_text
            })
            print(f"[TEXT_MERGE] ✅ Merged {len(text_parts)} text actions into 1")
        else:
            merged.append(current)
        
        i = j
    
    return merged


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
