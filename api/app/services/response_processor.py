# api/app/services/response_processor.py
"""Processa respostas do LLM e envia áudios/templates conforme necessário"""
import os
import json
import asyncio
from typing import Dict, Any, Optional, Tuple
from .template_loader import load_template, get_audio_path, get_template_by_code
from ..providers import twilio


async def process_llm_response(
    reply: Any,
    phone_number: str,
    thread_id: Optional[int] = None,
    db_session = None
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Processa a resposta do LLM e envia áudios/templates conforme necessário.
    
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
    if isinstance(reply, dict):
        print(f"[RESPONSE_PROCESSOR] 🔍 Reply é dict: {reply}")
    elif isinstance(reply, str):
        print(f"[RESPONSE_PROCESSOR] 🔍 Reply é string (primeiros 200 chars): {reply[:200]}")
    
    metadata = {}
    final_message = ""
    
    # Se reply é string, tenta extrair JSON primeiro
    if isinstance(reply, str):
        import re
        
        # Se a string contém "[Áudio enviado: ...]", tenta extrair o audio_id
        audio_match = re.search(r'\[Áudio enviado:\s*([^\]]+)\]', reply, re.IGNORECASE)
        if audio_match:
            audio_id = audio_match.group(1).strip()
            print(f"[RESPONSE_PROCESSOR] 🔍 Detectado padrão '[Áudio enviado: ...]', extraindo audio_id: {audio_id}")
            # Constrói JSON válido
            reply = {
                "response_type": "audio",
                "audio_id": audio_id,
                "message": ""
            }
            print(f"[RESPONSE_PROCESSOR] ✅ Convertido para dict: {reply}")
        else:
            # Procura por JSON que contenha "response_type" (só se ainda for string)
            json_pattern = r'\{[^{}]*"response_type"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, reply, re.DOTALL | re.IGNORECASE)
            
            # Se não encontrou, tenta padrão genérico
            if not json_matches:
                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                json_matches = re.findall(json_pattern, reply, re.DOTALL)
            
            for json_str in json_matches:
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict) and "response_type" in parsed:
                        print(f"[RESPONSE_PROCESSOR] ✅ JSON extraído da string: {parsed}")
                        reply = parsed  # Substitui reply pelo dict parseado
                        break
                except json.JSONDecodeError as e:
                    print(f"[RESPONSE_PROCESSOR] ⚠️ Erro ao parsear JSON: {e}")
                    continue
    
    # Se reply é dict (JSON response), processa
    if isinstance(reply, dict):
        response_type = reply.get("response_type", "")
        audio_id = reply.get("audio_id", "")
        template_code = reply.get("template_code", "")
        message = reply.get("message", "")
        next_stage = reply.get("next_stage", "")
        
        # Salva next_stage nos metadados e atualiza stage_id se necessário
        if next_stage:
            metadata["next_stage"] = next_stage
            # Atualiza thread se tiver db_session
            if thread_id and db_session:
                from ..models import Thread
                import json
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
                    # Se next_stage é um ID válido, atualiza stage_id
                    if next_stage and str(next_stage).isdigit():
                        current_meta["stage_id"] = next_stage
                        print(f"[RESPONSE_PROCESSOR] ✅ Atualizando stage_id para {next_stage}")
                    
                    thread.meta = current_meta
                    db_session.commit()
                    db_session.refresh(thread)
        
        # Processa response_type
        if response_type == "audio" and audio_id:
            # Envia áudio
            audio_path = get_audio_path(audio_id)
            print(f"[RESPONSE_PROCESSOR] 🎵 Processando áudio: audio_id={audio_id}, path={audio_path}")
            
            if not audio_path:
                print(f"[RESPONSE_PROCESSOR] ❌ Áudio não encontrado no mapeamento: {audio_id}")
                final_message = f"[Erro: áudio não encontrado: {audio_id}]"
                return final_message, metadata
            
            if audio_path:
                # Converte caminho relativo para URL pública
                # IMPORTANTE: Twilio precisa de URL pública acessível (não localhost)
                files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
                public_base = os.getenv("PUBLIC_BASE_URL", "")
                
                # Prioridade: PUBLIC_FILES_BASE_URL > PUBLIC_BASE_URL (ngrok) > localhost
                if files_base and "localhost" not in files_base:
                    base_url = files_base
                elif public_base and "localhost" not in public_base:
                    # Usa ngrok da API (que agora serve os arquivos também)
                    base_url = public_base
                    # Ajusta caminho para usar a rota da API
                    audio_path = audio_path.replace("/audios/", "/audios/")
                    print(f"[RESPONSE_PROCESSOR] ✅ Usando PUBLIC_BASE_URL (ngrok API) para áudio: {base_url}")
                else:
                    # Fallback: tenta usar a API local
                    base_url = "http://localhost:8000"
                    print(f"[RESPONSE_PROCESSOR] ⚠️ Usando API local para servir áudio: {base_url}")
                    print(f"[RESPONSE_PROCESSOR] ⚠️ Para produção, configure PUBLIC_BASE_URL (ngrok) no .env")
                
                audio_url = f"{base_url}{audio_path}"
                print(f"[RESPONSE_PROCESSOR] 🎵 URL final do áudio: {audio_url}")
                
                try:
                    await asyncio.to_thread(twilio.send_audio, phone_number, audio_url, "BOT")
                    print(f"[RESPONSE_PROCESSOR] ✅ Áudio enviado com sucesso: {audio_id}")
                    
                    # Envia mensagem de texto após o áudio (se houver)
                    if message and message.strip():
                        try:
                            await asyncio.to_thread(twilio.send_text, phone_number, message, "BOT")
                            print(f"[RESPONSE_PROCESSOR] ✅ Mensagem enviada após áudio: {len(message)} chars")
                            final_message = f"[Áudio enviado: {audio_id}]\n\n{message}"
                        except Exception as e2:
                            print(f"[RESPONSE_PROCESSOR] ⚠️ Erro ao enviar mensagem após áudio: {e2}")
                            final_message = f"[Áudio enviado: {audio_id}]"
                    else:
                        # Se não tem mensagem, salva apenas o registro do áudio
                        final_message = f"[Áudio enviado: {audio_id}]"
                except Exception as e:
                    import traceback
                    print(f"[RESPONSE_PROCESSOR] ❌ Erro ao enviar áudio {audio_id}: {e}")
                    print(f"[RESPONSE_PROCESSOR] Traceback: {traceback.format_exc()}")
                    final_message = message or f"[Erro ao enviar áudio: {audio_id}]"
            else:
                print(f"[RESPONSE_PROCESSOR] ⚠️ Áudio não encontrado no mapeamento: {audio_id}")
                final_message = message or f"[Áudio não encontrado: {audio_id}]"
        
        elif response_type == "checkout" or response_type == "template":
            # Carrega e envia template
            print(f"[RESPONSE_PROCESSOR] 📝 Processando template: template_code={template_code}")
            template_text = None
            if template_code:
                template_text = get_template_by_code(template_code)
            
            if template_text:
                print(f"[RESPONSE_PROCESSOR] 📝 Template carregado: {len(template_text)} chars")
                try:
                    await asyncio.to_thread(twilio.send_text, phone_number, template_text, "BOT")
                    print(f"[RESPONSE_PROCESSOR] ✅ Template enviado com sucesso: {template_code}")
                    final_message = f"[Template enviado: {template_code}]\n\n{template_text}"
                    
                    # 🎯 Se for template de planos, atualiza etapa para "aquecido"
                    if template_code in ["planos-life", "planos"] and thread_id and db_session:
                        from ..models import Thread
                        from .funnel_stage_manager import update_stage_from_event
                        import json as json_lib
                        
                        thread = db_session.get(Thread, thread_id)
                        if thread:
                            current_meta = {}
                            if thread.meta:
                                if isinstance(thread.meta, dict):
                                    current_meta = thread.meta.copy()
                                elif isinstance(thread.meta, str):
                                    try:
                                        current_meta = json_lib.loads(thread.meta)
                                    except:
                                        pass
                            
                            updated_meta = update_stage_from_event(current_meta, "IA_SENT_EXPLICACAO_PLANOS")
                            thread.meta = updated_meta
                            thread.lead_level = updated_meta.get("lead_level")
                            db_session.commit()
                            db_session.refresh(thread)
                            print(f"[RESPONSE_PROCESSOR] ✅ Etapa atualizada para 'aquecido' após envio de planos")
                except Exception as e:
                    import traceback
                    print(f"[RESPONSE_PROCESSOR] ❌ Erro ao enviar template {template_code}: {e}")
                    print(f"[RESPONSE_PROCESSOR] Traceback: {traceback.format_exc()}")
                    final_message = template_text or f"[Erro ao enviar template: {template_code}]"
            else:
                print(f"[RESPONSE_PROCESSOR] ⚠️ Template não encontrado: {template_code}")
                final_message = message or f"[Template não encontrado: {template_code}]"
        
        elif response_type == "text" or message:
            # Envia texto simples
            if message:
                try:
                    await asyncio.to_thread(twilio.send_text, phone_number, message, "BOT")
                    final_message = message
                except Exception as e:
                    print(f"⚠️ Erro ao enviar mensagem: {e}")
                    final_message = message
        
        else:
            # Fallback: converte dict para string
            final_message = json.dumps(reply, ensure_ascii=False)
    
    else:
        # Resposta é string normal, envia como texto
        reply_str = str(reply).strip()
        if reply_str:
            try:
                await asyncio.to_thread(twilio.send_text, phone_number, reply_str, "BOT")
                final_message = reply_str
            except Exception as e:
                print(f"⚠️ Erro ao enviar mensagem: {e}")
                final_message = reply_str
    
    return final_message, metadata

