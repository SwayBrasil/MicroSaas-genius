# api/app/services/automation_engine.py
"""Engine completa de automações - processa triggers e executa ações"""
import os
import asyncio
import json
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta

from ..providers import twilio as twilio_provider
from .template_loader import load_template, get_audio_path, get_template_by_code
from .support_detector import detect_support


# ==================== CONSTANTES DE ETAPAS ====================

# Funil Longo
FUNIL_LONGO_FASE_1_FRIO = "frio"
FUNIL_LONGO_FASE_2_AQUECIMENTO = "aquecimento"
FUNIL_LONGO_FASE_3_AQUECIDO = "aquecido"
FUNIL_LONGO_FASE_4_QUENTE = "quente"
FUNIL_LONGO_POS_COMPRA = "pos_compra"
FUNIL_LONGO_FATURA_PENDENTE = "fatura_pendente"
FUNIL_LONGO_RECUPERACAO = "recuperacao"

# Mini Funil BF
BF_AQUECIDO = "bf_aquecido"
BF_QUENTE = "bf_quente"
BF_FOLLOWUP_ENVIADO = "bf_followup_enviado"

# Recuperação 50%
RECUP_50_OFERTA_ENVIADA = "recup_50_oferta_enviada"
RECUP_50_SEM_RESPOSTA_1 = "recup_50_sem_resposta_1"
RECUP_50_SEM_RESPOSTA_2 = "recup_50_sem_resposta_2"

# Lista completa de estágios válidos
VALID_STAGES = [
    FUNIL_LONGO_FASE_1_FRIO,
    FUNIL_LONGO_FASE_2_AQUECIMENTO,
    FUNIL_LONGO_FASE_3_AQUECIDO,
    FUNIL_LONGO_FASE_4_QUENTE,
    FUNIL_LONGO_POS_COMPRA,
    FUNIL_LONGO_FATURA_PENDENTE,
    FUNIL_LONGO_RECUPERACAO,
    BF_AQUECIDO,
    BF_QUENTE,
    BF_FOLLOWUP_ENVIADO,
    RECUP_50_OFERTA_ENVIADA,
    RECUP_50_SEM_RESPOSTA_1,
    RECUP_50_SEM_RESPOSTA_2,
]


# ==================== MAPEAMENTO DE EVENTOS PARA ESTÁGIOS ====================

EVENT_TO_STAGE_MAP = {
    # Funil Longo
    "USER_SENT_FIRST_MESSAGE": FUNIL_LONGO_FASE_1_FRIO,
    "IA_SENT_AUDIO_DOR": FUNIL_LONGO_FASE_2_AQUECIMENTO,
    "IA_SENT_EXPLICACAO_PLANOS": FUNIL_LONGO_FASE_3_AQUECIDO,
    "USER_ESCOLHEU_PLANO": FUNIL_LONGO_FASE_4_QUENTE,
    "EDUZZ_WEBHOOK_APROVADA": FUNIL_LONGO_POS_COMPRA,
    "EDUZZ_WEBHOOK_PENDENTE": FUNIL_LONGO_FATURA_PENDENTE,
    "TEMPO_LIMITE_PASSOU": FUNIL_LONGO_RECUPERACAO,
    
    # Mini Funil BF
    "BF_ENTRADA": BF_AQUECIDO,
    "BF_CLICOU_REAGIU": BF_QUENTE,
    
    # Recuperação 50%
    "RECUP_50_DISPARADO": RECUP_50_OFERTA_ENVIADA,
    "RECUP_50_FOLLOWUP_1": RECUP_50_SEM_RESPOSTA_1,
    "RECUP_50_FOLLOWUP_2": RECUP_50_SEM_RESPOSTA_2,
}


# ==================== GATILHOS DO FUNIL LONGO ====================

def detect_funil_longo_trigger(message: str, thread_meta: Optional[Dict] = None) -> Optional[str]:
    """
    Detecta gatilhos de entrada do funil longo.
    
    Returns:
        Nome do gatilho ou None
    """
    message_lower = message.lower().strip()
    current_stage = thread_meta.get("lead_stage") if thread_meta else None
    
    # Gatilho de entrada (primeira mensagem ou sem stage definido)
    if not current_stage or current_stage == FUNIL_LONGO_FASE_1_FRIO:
        entry_keywords = [
            "quero saber do life",
            "como funciona o life",
            "quero ser gostosa",
            "quero emagrecer",
            "quero transformar",
            "life",
            "como funciona",
            "quero saber",
        ]
        
        # Verifica se é entrada (palavras-chave de entrada)
        if any(keyword in message_lower for keyword in entry_keywords):
            # Se já está em FRIO, pode ser que já enviou áudio 1, então não dispara novamente
            # Mas se não tem stage, dispara
            if not current_stage:
                return "ENTRY_FUNIL_LONGO"
            # Se está em FRIO mas não mencionou dor ainda, pode ser entrada repetida
            # Vamos permitir que avance para dor se mencionar objetivo
            pass
    
    # Gatilho de dor (está na etapa 1 - FRIO)
    if current_stage == FUNIL_LONGO_FASE_1_FRIO or not current_stage:
        dor_keywords = [
            "dor", "problema", "incomoda", "quero emagrecer", "quero perder peso",
            "barriga", "flacidez", "celulite", "autoestima", "vergonha",
            "não gosto", "me incomoda", "me derruba", "travamento", "objetivo",
            "quero definir", "quero ganhar massa", "pochete", "papada"
        ]
        if any(keyword in message_lower for keyword in dor_keywords):
            return "DOR_DETECTADA"
    
    # Gatilho de interesse em plano (está em AQUECIMENTO ou AQUECIDO)
    if current_stage in [FUNIL_LONGO_FASE_2_AQUECIMENTO, FUNIL_LONGO_FASE_3_AQUECIDO, None]:
        plano_keywords = [
            "quero saber os planos",
            "quero saber sobre os planos",
            "como funciona o pagamento",
            "quanto custa",
            "preço",
            "planos",
            "quais são os planos",
            "me fala dos planos"
        ]
        if any(keyword in message_lower for keyword in plano_keywords):
            return "INTERESSE_PLANO"
    
    # Gatilho de escolha de plano (está em AQUECIDO)
    if current_stage == FUNIL_LONGO_FASE_3_AQUECIDO:
        escolha_keywords = [
            "quero o mensal", 
            "quero o anual", 
            "quero mensal",
            "quero anual",
            "mensal",
            "anual",
            "plano mensal",
            "plano anual"
        ]
        # Verifica se é uma escolha explícita (não apenas mencionar a palavra)
        if any(keyword in message_lower for keyword in escolha_keywords):
            # Verifica se não é apenas uma pergunta
            if not message_lower.endswith("?") and "qual" not in message_lower:
                return "ESCOLHEU_PLANO"
    
    return None


# ==================== AÇÕES DO FUNIL LONGO ====================

async def execute_funil_longo_action(
    trigger: str,
    phone_number: str,
    thread_meta: Optional[Dict] = None,
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Executa ação do funil longo baseado no gatilho.
    
    Returns:
        Tuple de (lead_stage_atualizado, metadata)
    """
    metadata = {}
    new_stage = None
    messages_sent = []  # Lista de mensagens enviadas para salvar no banco
    
    if trigger == "ENTRY_FUNIL_LONGO":
        # Envia áudio 1
        audio_path = get_audio_path("audio1_boas_vindas")
        if not audio_path:
            print(f"[AUTOMATION] ❌ Áudio 1 não encontrado no mapeamento")
            messages_sent.append("[Erro: áudio 1 não encontrado]")
        else:
            # Prioriza PUBLIC_BASE_URL (ngrok) que é acessível pelo Twilio
            public_base = os.getenv("PUBLIC_BASE_URL", "")
            files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
            
            # Se não tem PUBLIC_BASE_URL configurado, avisa
            if not public_base or "localhost" in public_base:
                print(f"[AUTOMATION] ⚠️ PUBLIC_BASE_URL não configurado ou é localhost. Twilio não conseguirá acessar o áudio!")
                print(f"[AUTOMATION] ⚠️ Configure PUBLIC_BASE_URL no .env com sua URL do ngrok (ex: https://abc123.ngrok-free.app)")
            
            # Usa PUBLIC_BASE_URL se disponível, senão tenta PUBLIC_FILES_BASE_URL, senão localhost (não funcionará)
            if public_base and "localhost" not in public_base:
                base_url = public_base.rstrip("/")
            elif files_base and "localhost" not in files_base:
                base_url = files_base.rstrip("/")
            else:
                base_url = "http://localhost:8000"
            
            # Remove barra inicial do audio_path se houver e constrói URL
            audio_path_clean = audio_path.lstrip("/")
            # O endpoint é /audios/{path}, então precisa remover /audios/ do path se já estiver
            if audio_path_clean.startswith("audios/"):
                audio_path_clean = audio_path_clean[7:]  # Remove "audios/"
            audio_url = f"{base_url}/audios/{audio_path_clean}"
            
            print(f"[AUTOMATION] 🎵 Enviando áudio 1:")
            print(f"[AUTOMATION]    URL: {audio_url}")
            print(f"[AUTOMATION]    Path: {audio_path}")
            print(f"[AUTOMATION]    Base: {base_url}")
            print(f"[AUTOMATION]    Phone: {phone_number}")
            
            try:
                print(f"[AUTOMATION] 📞 Chamando send_audio...")
                sid = await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
                print(f"[AUTOMATION] ✅ Áudio 1 enviado com sucesso! SID: {sid}")
                messages_sent.append(f"[Áudio enviado: 01-boas-vindas-qualificacao | SID: {sid}]")
                
                # Envia texto após o áudio (conforme README dos áudios)
                followup_text = "Perfeitaaa, me conta qual é seu objetivo hoje? 🔥✨\n\nO que você mais quer transformar no seu corpo agora?"
                try:
                    await asyncio.to_thread(twilio_provider.send_text, phone_number, followup_text, "BOT")
                    print(f"[AUTOMATION] ✅ Texto de follow-up enviado após áudio 1")
                    messages_sent.append(followup_text)
                except Exception as e2:
                    print(f"[AUTOMATION] ⚠️ Erro ao enviar texto de follow-up: {str(e2)}")
                    
            except Exception as e:
                print(f"[AUTOMATION] ❌ ERRO ao enviar áudio 1: {str(e)}")
                import traceback
                traceback.print_exc()
                # Mesmo com erro, continua o fluxo
                messages_sent.append(f"[Erro ao enviar áudio 1: {str(e)}]")
        
        new_stage = FUNIL_LONGO_FASE_1_FRIO
        metadata["audio_sent"] = "01-boas-vindas-qualificacao"
        metadata["event"] = "USER_SENT_FIRST_MESSAGE"
        metadata["messages_sent"] = messages_sent
    
    elif trigger == "DOR_DETECTADA":
        # Envia áudio 2 (dor genérica) + provas sociais
        audio_path = get_audio_path("audio2_dor_generica")
        if not audio_path:
            print(f"[AUTOMATION] ❌ Áudio 2 não encontrado no mapeamento")
            messages_sent.append("[Erro: áudio 2 não encontrado]")
        else:
            public_base = os.getenv("PUBLIC_BASE_URL", "")
            files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
            
            if public_base and "localhost" not in public_base:
                base_url = public_base.rstrip("/")
            elif files_base and "localhost" not in files_base:
                base_url = files_base.rstrip("/")
            else:
                base_url = "http://localhost:8000"
            
            audio_path_clean = audio_path.lstrip("/")
            if audio_path_clean.startswith("audios/"):
                audio_path_clean = audio_path_clean[7:]
            audio_url = f"{base_url}/audios/{audio_path_clean}"
            
            print(f"[AUTOMATION] 🎵 Enviando áudio 2: {audio_url}")
            try:
                await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
                print(f"[AUTOMATION] ✅ Áudio 2 enviado com sucesso para {phone_number}")
                messages_sent.append("[Áudio enviado: 02-dor-generica]")
            except Exception as e:
                print(f"[AUTOMATION] ❌ ERRO ao enviar áudio 2: {str(e)}")
                import traceback
                traceback.print_exc()
                messages_sent.append(f"[Erro ao enviar áudio 2: {str(e)}]")
        
        # Envia provas sociais (imagens)
        # TODO: Implementar envio de múltiplas imagens quando send_image estiver disponível
        
        # Envia texto de follow-up
        followup_text = "Me conta aqui gata, o que tá faltando pra tu dar esse passo? 👯‍♀️✨"
        try:
            await asyncio.to_thread(twilio_provider.send_text, phone_number, followup_text, "BOT")
            messages_sent.append(followup_text)
        except Exception as e:
            print(f"[AUTOMATION] ❌ ERRO ao enviar texto de follow-up: {str(e)}")
        
        new_stage = FUNIL_LONGO_FASE_2_AQUECIMENTO
        metadata["audio_sent"] = "02-dor-generica"
        metadata["images_sent"] = "prova-social"
        metadata["event"] = "IA_SENT_AUDIO_DOR"
        metadata["messages_sent"] = messages_sent
    
    elif trigger == "INTERESSE_PLANO":
        # Envia áudio 3 + template de planos
        audio_path = get_audio_path("audio3_explicacao_planos")
        if not audio_path:
            print(f"[AUTOMATION] ❌ Áudio 3 não encontrado no mapeamento")
            messages_sent.append("[Erro: áudio 3 não encontrado]")
        else:
            public_base = os.getenv("PUBLIC_BASE_URL", "")
            files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
            
            if public_base and "localhost" not in public_base:
                base_url = public_base.rstrip("/")
            elif files_base and "localhost" not in files_base:
                base_url = files_base.rstrip("/")
            else:
                base_url = "http://localhost:8000"
            
            audio_path_clean = audio_path.lstrip("/")
            if audio_path_clean.startswith("audios/"):
                audio_path_clean = audio_path_clean[7:]
            audio_url = f"{base_url}/audios/{audio_path_clean}"
            
            print(f"[AUTOMATION] 🎵 Enviando áudio 3: {audio_url}")
            try:
                await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
                print(f"[AUTOMATION] ✅ Áudio 3 enviado com sucesso para {phone_number}")
                messages_sent.append("[Áudio enviado: 03-explicacao-planos]")
            except Exception as e:
                print(f"[AUTOMATION] ❌ ERRO ao enviar áudio 3: {str(e)}")
                import traceback
                traceback.print_exc()
                messages_sent.append(f"[Erro ao enviar áudio 3: {str(e)}]")
        
        # Envia template de planos
        template_text = get_template_by_code("planos-life")
        if template_text:
            try:
                await asyncio.to_thread(twilio_provider.send_text, phone_number, template_text, "BOT")
                messages_sent.append(template_text)
            except Exception as e:
                print(f"[AUTOMATION] ❌ ERRO ao enviar template de planos: {str(e)}")
        
        new_stage = FUNIL_LONGO_FASE_3_AQUECIDO
        metadata["audio_sent"] = "03-explicacao-planos"
        metadata["template_sent"] = "planos-life"
        metadata["event"] = "IA_SENT_EXPLICACAO_PLANOS"
        metadata["messages_sent"] = messages_sent
    
    elif trigger == "ESCOLHEU_PLANO":
        # Detecta qual plano
        message_lower = (thread_meta.get("last_message", "") or "").lower()
        is_anual = "anual" in message_lower
        
        # Envia template correto
        template_code = "fechamento-anual" if is_anual else "fechamento-mensal"
        template_text = get_template_by_code(template_code)
        if template_text:
            await asyncio.to_thread(twilio_provider.send_text, phone_number, template_text, "BOT")
            messages_sent.append(template_text)
        
        new_stage = FUNIL_LONGO_FASE_4_QUENTE
        metadata["template_sent"] = template_code
        metadata["plano_escolhido"] = "anual" if is_anual else "mensal"
        metadata["event"] = "USER_ESCOLHEU_PLANO"
        metadata["messages_sent"] = messages_sent
    
    # Salva mensagens no banco se tiver thread_id e db_session
    if thread_id and db_session and messages_sent:
        from ..models import Message
        for msg_content in messages_sent:
            msg = Message(thread_id=thread_id, role="assistant", content=msg_content)
            db_session.add(msg)
        db_session.commit()
        print(f"[AUTOMATION] ✅ {len(messages_sent)} mensagens salvas no banco para thread {thread_id}")
    
    return new_stage, metadata


# ==================== PROCESSAMENTO PRINCIPAL ====================

async def process_automation(
    message: str,
    phone_number: str,
    thread_meta: Optional[Dict] = None,
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[Optional[str], Dict[str, Any], bool]:
    """
    Processa automação baseado na mensagem e estado atual.
    
    Args:
        message: Mensagem do usuário
        phone_number: Número do WhatsApp
        thread_meta: Metadata da thread (deve incluir lead_stage)
        db_session: Sessão do banco (opcional)
        thread_id: ID da thread (opcional)
    
    Returns:
        Tuple de (new_lead_stage, metadata, should_stop_automation)
        - new_lead_stage: Nova etapa do funil ou None
        - metadata: Metadados da ação executada
        - should_stop_automation: True se detectou suporte e deve parar
    """
    # Atualiza thread_meta com last_message para detecção de plano
    if thread_meta is None:
        thread_meta = {}
    thread_meta["last_message"] = message
    
    # 1. DETECÇÃO DE SUPORTE (prioridade máxima)
    is_support, support_reason = detect_support(message)
    if is_support:
        # Envia mensagem de encaminhamento
        takeover_msg = "Gata, pra isso o meu time de suporte é perfeito, tá? 💖\n\nVou te passar pra uma pessoa da equipe que resolve rapidinho esse tipo de coisa, combinado?"
        await asyncio.to_thread(twilio_provider.send_text, phone_number, takeover_msg, "BOT")
        
        print(f"[AUTOMATION] 🚨 SUPORTE DETECTADO: {support_reason}")
        return None, {"support_detected": True, "reason": support_reason, "need_human": True}, True
    
    # 2. DETECÇÃO DE GATILHOS DO FUNIL LONGO
    trigger = detect_funil_longo_trigger(message, thread_meta)
    if trigger:
        print(f"[AUTOMATION] 🎯 Gatilho detectado: {trigger}")
        new_stage, metadata = await execute_funil_longo_action(
            trigger, phone_number, thread_meta, db_session, thread_id
        )
        # Se executou ação, NÃO deve chamar LLM
        return new_stage, metadata, True  # should_stop=True significa "não chame LLM"
    
    # 3. Se não detectou gatilho, retorna None (IA processa normalmente)
    return None, {}, False


def update_lead_stage_from_event(event: str, current_stage: Optional[str] = None) -> Optional[str]:
    """
    Atualiza lead_stage baseado em evento.
    
    Returns:
        Novo lead_stage ou None se não houver mudança
    """
    if event in EVENT_TO_STAGE_MAP:
        return EVENT_TO_STAGE_MAP[event]
    return None


# ==================== AUTOMAÇÃO MINI FUNIL BF ====================

async def trigger_bf_funnel(
    phone_number: str,
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Dispara entrada no mini funil Black Friday.
    
    Pode ser chamado por:
    - Tag de campanha
    - Botão manual
    - Evento externo
    
    Returns:
        Tuple de (new_lead_stage, metadata)
    """
    import os
    
    metadata = {}
    
    # Envia áudio de oferta BF
    audio_path = get_audio_path("bf_01_oferta_black_friday")
    if not audio_path:
        # Fallback: tenta caminho direto
        audio_path = "/audios/mini-funil-bf/01-oferta-black-friday.opus"
    
    if audio_path:
        files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
        public_base = os.getenv("PUBLIC_BASE_URL", "")
        
        if files_base and "localhost" not in files_base:
            base_url = files_base
        elif public_base and "localhost" not in public_base:
            base_url = public_base
        else:
            base_url = "http://localhost:8000"
        
        audio_url = f"{base_url}{audio_path}"
        await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
        print(f"[AUTOMATION] ✅ Áudio BF enviado para {phone_number}")
    
    # Texto de acompanhamento
    bf_text = "Gataaaaa, olha issoooo 🔥🔥🔥\n\nSaiu uma condição INSANA da Black Friday, só HOJE!!\n\nQuer saber como funciona pra você aproveitar?"
    await asyncio.to_thread(twilio_provider.send_text, phone_number, bf_text, "BOT")
    
    new_stage = BF_AQUECIDO
    metadata["audio_sent"] = "01-oferta-black-friday"
    metadata["event"] = "BF_ENTRADA"
    
    return new_stage, metadata


async def trigger_bf_followup(
    phone_number: str,
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Dispara follow-up do mini funil BF (quando não respondeu).
    
    Returns:
        Tuple de (new_lead_stage, metadata)
    """
    import os
    
    metadata = {}
    
    # Envia áudio de follow-up
    audio_path = get_audio_path("bf_02_followup_sem_resposta")
    if not audio_path:
        audio_path = "/audios/mini-funil-bf/02-followup-sem-resposta.opus"
    
    if audio_path:
        files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
        public_base = os.getenv("PUBLIC_BASE_URL", "")
        
        if files_base and "localhost" not in files_base:
            base_url = files_base
        elif public_base and "localhost" not in public_base:
            base_url = public_base
        else:
            base_url = "http://localhost:8000"
        
        audio_url = f"{base_url}{audio_path}"
        await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
        print(f"[AUTOMATION] ✅ Áudio BF follow-up enviado para {phone_number}")
    
    # Texto de acompanhamento
    followup_text = "Só passando aqui rapidinho porque essa promoção é literalmente a mais forte do ano 🔥\n\nSe ainda fizer sentido pra você, me chama aqui que te explico antes de acabar!"
    await asyncio.to_thread(twilio_provider.send_text, phone_number, followup_text, "BOT")
    
    new_stage = BF_FOLLOWUP_ENVIADO
    metadata["audio_sent"] = "02-followup-sem-resposta"
    metadata["event"] = "BF_FOLLOWUP_1"
    
    return new_stage, metadata


# ==================== AUTOMAÇÃO RECUPERAÇÃO 50% ====================

async def trigger_recup_50_oferta(
    phone_number: str,
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Dispara oferta de recuperação 50%.
    
    Chamado quando:
    - Lead foi até o final da plataforma e não concluiu
    - Status Eduzz = iniciado mas não pago
    
    Returns:
        Tuple de (new_lead_stage, metadata)
    """
    metadata = {}
    
    # Envia template de oferta 50%
    template_text = get_template_by_code("recuperacao-50-oferta")
    if template_text:
        await asyncio.to_thread(twilio_provider.send_text, phone_number, template_text, "BOT")
        print(f"[AUTOMATION] ✅ Oferta 50% enviada para {phone_number}")
    
    new_stage = RECUP_50_OFERTA_ENVIADA
    metadata["template_sent"] = "recuperacao-50-oferta"
    metadata["event"] = "RECUP_50_DISPARADO"
    
    return new_stage, metadata


async def trigger_recup_50_followup_1(
    phone_number: str,
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Primeiro follow-up da recuperação 50% (se não respondeu).
    
    Returns:
        Tuple de (new_lead_stage, metadata)
    """
    import os
    
    metadata = {}
    
    # Envia áudio de follow-up
    audio_path = get_audio_path("recup_50_02_audio_followup")
    if not audio_path:
        audio_path = "/audios/recuperacao-50/02-audio-followup.opus"
    
    if audio_path:
        files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
        public_base = os.getenv("PUBLIC_BASE_URL", "")
        
        if files_base and "localhost" not in files_base:
            base_url = files_base
        elif public_base and "localhost" not in public_base:
            base_url = public_base
        else:
            base_url = "http://localhost:8000"
        
        audio_url = f"{base_url}{audio_path}"
        await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
        print(f"[AUTOMATION] ✅ Áudio recuperação 50% follow-up 1 enviado para {phone_number}")
    
    # Texto de acompanhamento
    followup_text = "Te mandei uma condição muito especial pro LIFE e não queria que passasse batido por você, gata. 💖\n\nMe chama aqui se ainda tiver vontade de aproveitar essa oportunidade!"
    await asyncio.to_thread(twilio_provider.send_text, phone_number, followup_text, "BOT")
    
    new_stage = RECUP_50_SEM_RESPOSTA_1
    metadata["audio_sent"] = "02-audio-followup"
    metadata["event"] = "RECUP_50_FOLLOWUP_1"
    
    return new_stage, metadata


async def trigger_recup_50_followup_2(
    phone_number: str,
    db_session = None,
    thread_id: Optional[int] = None
) -> Tuple[str, Dict[str, Any]]:
    """
    Último follow-up da recuperação 50% (último chamado).
    
    Returns:
        Tuple de (new_lead_stage, metadata)
    """
    import os
    
    metadata = {}
    
    # Envia áudio de último chamado
    audio_path = get_audio_path("recup_50_03_audio_ultimo_chamado")
    if not audio_path:
        audio_path = "/audios/recuperacao-50/03-audio-ultimo-chamado.opus"
    
    if audio_path:
        files_base = os.getenv("PUBLIC_FILES_BASE_URL", "")
        public_base = os.getenv("PUBLIC_BASE_URL", "")
        
        if files_base and "localhost" not in files_base:
            base_url = files_base
        elif public_base and "localhost" not in public_base:
            base_url = public_base
        else:
            base_url = "http://localhost:8000"
        
        audio_url = f"{base_url}{audio_path}"
        await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
        print(f"[AUTOMATION] ✅ Áudio recuperação 50% último chamado enviado para {phone_number}")
    
    # Texto de acompanhamento
    followup_text = "Prometo que é a última vez que apareço aqui sobre essa condição 🙈\n\nSe ainda bater aquela vontade de começar sua transformação com 50% OFF, é agora ou só na próxima… 😅🔥"
    await asyncio.to_thread(twilio_provider.send_text, phone_number, followup_text, "BOT")
    
    new_stage = RECUP_50_SEM_RESPOSTA_2
    metadata["audio_sent"] = "03-audio-ultimo-chamado"
    metadata["event"] = "RECUP_50_FOLLOWUP_2"
    
    return new_stage, metadata

