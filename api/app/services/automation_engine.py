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
    print(f"[AUTOMATION][detect_funil_longo_trigger] Mensagem: '{message_lower}', Stage atual: {current_stage}")
    
    # 🚨 PRIORIDADE: Verifica se há menção a preços/planos/funcionamento ANTES de qualquer outra coisa
    # Se mencionar preços/planos/funcionamento, NÃO dispara áudio 1, deixa o LLM lidar (Fase 3)
    preco_keywords = [
        "preço", "preços", "quanto custa", "valores", "planos", "opções de plano",
        "quero ver os precos", "me passa os preços", "quais os valores",
        "quero saber dos planos", "me mostra os planos", "investimento"
    ]
    
    funcionamento_keywords = [
        "como funciona", "como é", "me explica", "me fala mais", "conta pra mim"
    ]
    
    # Se mencionar preços, NÃO dispara automação - deixa LLM responder com Fase 3
    if any(keyword in message_lower for keyword in preco_keywords):
        return None
    
    # Gatilho de entrada (primeira mensagem ou sem stage definido)
    if not current_stage or current_stage == FUNIL_LONGO_FASE_1_FRIO:
        # Palavras-chave de entrada (verifica ANTES de verificar "como funciona")
        entry_keywords = [
            "quero saber do life",
            "quero ser gostosa",
            "quero emagrecer",
            "quero transformar",
            "preciso fazer algo",
            "quero mudar",
            "quero melhorar",
            "me tornarei",
            "tornar",
            "gostosa",
            "grande gostosa",
            "life",
            "quero saber",
        ]
        
        # Verifica se tem palavras-chave de entrada
        tem_entry_keyword = any(keyword in message_lower for keyword in entry_keywords)
        
        # Se tem "como funciona", verifica se tem contexto de transformação
        tem_como_funciona = any(keyword in message_lower for keyword in funcionamento_keywords)
        tem_contexto_transformacao = any(keyword in message_lower for keyword in [
            "quero ser gostosa", "quero emagrecer", "quero transformar", 
            "preciso fazer algo", "quero mudar", "quero melhorar",
            "me tornarei", "tornar", "gostosa", "grande gostosa"
        ])
        
        # Se tem palavra-chave de entrada OU (tem "como funciona" E tem contexto de transformação)
        if tem_entry_keyword or (tem_como_funciona and tem_contexto_transformacao):
            # Se não tem stage, dispara ENTRY_FUNIL_LONGO
            if not current_stage:
                return "ENTRY_FUNIL_LONGO"
            # Se está em FRIO mas não mencionou dor ainda, pode ser entrada repetida
            # Vamos permitir que avance para dor se mencionar objetivo
            pass
    
    # 🚨 PRIORIDADE: Detecta interesse em planos ANTES de detectar dor
    # Se está em AQUECIMENTO (já recebeu áudio 2 + imagens), respostas positivas indicam interesse
    if current_stage == FUNIL_LONGO_FASE_2_AQUECIMENTO:
        # Palavras-chave que indicam interesse/aceitação após ver as imagens
        interesse_keywords = [
            "falta de vergonha", "falta vergonha", "falta vergonha na cara", "vergonha na cara",
            "legal", "ok", "entendi", "faz sentido", "gostei", "quero saber",
            "quero ver", "me mostra", "me fala", "conta pra mim",
            "quero saber os planos", "quero saber sobre os planos",
            "como funciona o pagamento", "quanto custa", "preço", "planos",
            "quais são os planos", "me fala dos planos", "quero ver os precos",
            "me passa os preços", "quais os valores", "investimento"
        ]
        if any(keyword in message_lower for keyword in interesse_keywords):
            print(f"[AUTOMATION] ✅ INTERESSE_PLANO detectado após Fase 2: '{message_lower}'")
            return "INTERESSE_PLANO"
    
    # Gatilho de interesse em plano (está em AQUECIDO ou sem stage)
    # CORREÇÃO D: Usa intent_classifier para distinguir ASK_PLANS vs CHOOSE_PLAN
    if current_stage in [FUNIL_LONGO_FASE_3_AQUECIDO, None]:
        from .intent_classifier import detect_plans_intent
        intent = detect_plans_intent(message, current_stage)
        
        if intent == "ASK_PLANS":
            return "INTERESSE_PLANO"
        elif intent == "CHOOSE_PLAN":
            return "ESCOLHEU_PLANO"
    
    # Gatilho de dor (está na etapa 1 - FRIO ou sem stage)
    # IMPORTANTE: Detecta dor mesmo se já está em FRIO (lead já recebeu áudio 1)
    # MAS: Remove "vergonha" isolada - só detecta se for "vergonha" como dor (ex: "tenho vergonha")
    # E: NÃO detecta dor se já está em AQUECIMENTO (já passou da fase de dor)
    if current_stage == FUNIL_LONGO_FASE_2_AQUECIMENTO:
        # Se já está em AQUECIMENTO, não detecta mais dor - deve detectar interesse em planos
        print(f"[AUTOMATION] ⚠️ Stage é AQUECIMENTO, pulando detecção de dor (já passou dessa fase)")
        return None
    
    if current_stage == FUNIL_LONGO_FASE_1_FRIO or current_stage is None:
        dor_keywords = [
            "dor", "problema", "incomoda", "quero emagrecer", "quero perder peso",
            "barriga", "flacidez", "celulite", "autoestima",
            "tenho vergonha", "sinto vergonha", "me dá vergonha", "vergonha de",
            "não gosto", "me incomoda", "me derruba", "travamento", "objetivo",
            "quero definir", "quero ganhar massa", "pochete", "papada",
            "gordinha", "gordo", "gorda", "meio gordinha", "meio gordo", "meio gorda",
            "gorda", "obesa", "obeso", "estou gorda", "me sinto gorda", "sou gorda",
            "triste", "me sinto", "me sinto muito", "sentindo", "estou me sentindo",
            "insatisfeita", "insatisfeito", "não gosto do meu", "não gosto da minha",
            "evito", "não consigo", "sempre desisto", "falta disciplina",
            "emagrecer", "emagrecer msm", "queria emagrecer", "preciso emagrecer",
            # Expressões de frustração/necessidade de mudança
            "impossível continuar", "não dá mais", "não aguento mais", "não aguento",
            "preciso mudar", "preciso mudar isso", "tem que mudar", "tem q mudar",
            "não posso mais", "não consigo mais", "não dá pra continuar", "não dá pra continuar assim",
            "preciso fazer algo", "preciso fazer alguma coisa", "algo tem que mudar",
            "tem que ser diferente", "tem q ser diferente", "preciso de uma solução",
            # Respostas vagas/indecisas que indicam necessidade de ajuda
            "não sei", "n sei", "não sei o que", "n sei o que", "não sei bem",
            "n sei bem", "não sei exatamente", "n sei exatamente", "não sei exataemnte",
            "n sei exataemnte", "não sei direito", "n sei direito", "não sei como",
            "n sei como", "não tenho certeza", "n tenho certeza", "não sei ao certo",
            "n sei ao certo", "tô perdida", "to perdida", "estou perdida", "tô confusa",
            "to confusa", "estou confusa", "não entendo", "n entendo", "não entendi",
            "n entendi", "me ajuda", "me ajuda ai", "me ajuda aí", "preciso de ajuda",
            "preciso ajuda", "me orienta", "me oriente", "me explica", "me fala"
        ]
        # Exclui "falta de vergonha" e "vergonha na cara" que indicam interesse, não dor
        if "falta de vergonha" in message_lower or "falta vergonha na cara" in message_lower or "vergonha na cara" in message_lower:
            return None
        if any(keyword in message_lower for keyword in dor_keywords):
            print(f"[AUTOMATION] ✅ DOR_DETECTADA: '{message_lower}' contém palavra-chave de dor")
            return "DOR_DETECTADA"
    
    # Gatilho de escolha de plano (está em AQUECIDO)
    # CORREÇÃO D: Usa intent_classifier para detectar CHOOSE_PLAN
    if current_stage == FUNIL_LONGO_FASE_3_AQUECIDO:
        from .intent_classifier import detect_plans_intent
        intent = detect_plans_intent(message, current_stage)
        
        if intent == "CHOOSE_PLAN":
            return "ESCOLHEU_PLANO"
    
    return None


# ==================== AÇÕES DO FUNIL LONGO ====================

async def execute_funil_longo_action(
    trigger: str,
    phone_number: str,
    thread_meta: Optional[Dict] = None,
    db_session = None,
    thread_id: Optional[int] = None,
    message: str = None
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
                
                # FASE 1: Apenas áudio, sem texto adicional (o LLM vai responder depois)
                    
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
        # FASE 2: Executa PACOTE_FASE_2 fixo (sem LLM)
        # Pacote fixo: áudio2 + 8 imagens + textos com delays corretos
        print(f"[AUTOMATION] 🎯 Fase 2 detectada (dor), executando PACOTE_FASE_2 fixo")
        
        from .funnel_packages import execute_pacote_fase_2
        
        # Detecta qual áudio usar baseado na mensagem (por enquanto usa genérico)
        # TODO: Pode melhorar para escolher áudio específico baseado na dor mencionada
        audio_id = "audio2_dor_generica"
        
        try:
            msgs_sent, pkg_metadata = await execute_pacote_fase_2(
                phone_number=phone_number,
                audio_id=audio_id,
                db_session=db_session,
                thread_id=thread_id
            )
            messages_sent.extend(msgs_sent)
            metadata.update(pkg_metadata)
            print(f"[AUTOMATION] ✅ PACOTE_FASE_2 executado com sucesso")
        except Exception as e:
            print(f"[AUTOMATION] ❌ Erro ao executar PACOTE_FASE_2: {e}")
            import traceback
            traceback.print_exc()
        
        new_stage = FUNIL_LONGO_FASE_2_AQUECIMENTO
        metadata["event"] = "DOR_DETECTADA"
        metadata["stage"] = "fase_2_aquecimento"
        metadata["messages_sent"] = messages_sent
    
    elif trigger == "INTERESSE_PLANO":
        # FASE 3: Executa PACOTE_FASE_3 fixo (sem LLM)
        # Pacote fixo: intro + áudio3 + planos + pergunta com delays corretos
        print(f"[AUTOMATION] 🎯 Interesse em planos detectado, executando PACOTE_FASE_3 fixo")
        
        from .funnel_packages import execute_pacote_fase_3
        
        try:
            msgs_sent, pkg_metadata = await execute_pacote_fase_3(
                phone_number=phone_number,
                db_session=db_session,
                thread_id=thread_id
            )
            messages_sent.extend(msgs_sent)
            metadata.update(pkg_metadata)
            print(f"[AUTOMATION] ✅ PACOTE_FASE_3 executado com sucesso")
        except Exception as e:
            print(f"[AUTOMATION] ❌ Erro ao executar PACOTE_FASE_3: {e}")
            import traceback
            traceback.print_exc()
        
        new_stage = FUNIL_LONGO_FASE_3_AQUECIDO
        metadata["event"] = "IA_SENT_EXPLICACAO_PLANOS"
        metadata["messages_sent"] = messages_sent
    
    elif trigger == "ESCOLHEU_PLANO":
        # CORREÇÃO D: Usa intent_classifier para detectar plano escolhido
        from .intent_classifier import extract_plan_choice
        # Usa a mensagem atual passada como parâmetro, não last_message do meta
        message_text = message or thread_meta.get("last_message", "") or ""
        plan_choice = extract_plan_choice(message_text)
        
        is_anual = plan_choice == "ANUAL" if plan_choice else "anual" in message_text.lower()
        
        # Envia template correto
        template_code = "fechamento-anual" if is_anual else "fechamento-mensal"
        template_text = get_template_by_code(template_code)
        if template_text:
            await asyncio.to_thread(twilio_provider.send_text, phone_number, template_text, "BOT")
            messages_sent.append(template_text)
            print(f"[AUTOMATION] ✅ Template '{template_code}' enviado para {phone_number}")
        else:
            # Fallback: envia mensagem hardcoded se template não for encontrado
            print(f"[AUTOMATION] ⚠️ Template '{template_code}' não encontrado, usando fallback")
            if is_anual:
                fallback_msg = """Amoo! 🔥 Bora garantir sua transformação agoraaaa!! 💖

Aqui está o link pra você finalizar o *Plano Anual* do LIFE:

➡️ https://edzz.la/DO408?a=10554737

💳 Gatinha, antes de finalizar, ajusta o limite do cartão lá no app do seu banco para algo em torno de R$50.  

Isso não vai comprometer o seu limite total, é só pra autorização da primeira parcela mesmo.

O sistema vai cobrar apenas a parcela mensal certinha, tá?

Assim que finalizar, me avisa aqui que eu já te envio todos os acessos e te coloco no caminho da sua melhor versão.  

Tô te esperando do outro lado! 🚀✨"""
            else:
                fallback_msg = """🔥 Bora garantir sua transformação agoraaaa!! 💖

Aqui tá o link do *Plano Mensal* pra você finalizar:

➡️ https://edzz.la/GQRLF?a=10554737

É super simples: você assina, já recebe os acessos e começa hoje mesmo com treino e dieta alinhadinhos com o que você me contou. 😍

Assim que finalizar, me avisa aqui que eu já te envio tudo e organizo seu passo a passo no LIFE.  

Tô aqui pra caminhar contigo, gata! ✨"""
            await asyncio.to_thread(twilio_provider.send_text, phone_number, fallback_msg, "BOT")
            messages_sent.append(fallback_msg)
            print(f"[AUTOMATION] ✅ Mensagem de checkout (fallback) enviada para {phone_number}")
        
        # Marca que checkout foi enviado (evita reenvio de áudio3)
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
                    meta["checkout_sent_at"] = datetime.now().isoformat()
                    meta["last_checkout_plan"] = "anual" if is_anual else "mensal"
                    thread.meta = meta
                    db_session.commit()
                    print(f"[AUTOMATION] ✅ Marcado checkout_sent_at (plano: {'anual' if is_anual else 'mensal'})")
            except Exception as e:
                print(f"[AUTOMATION] ⚠️ Erro ao marcar checkout_sent_at: {e}")
        
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
    thread_id: Optional[int] = None,
    message_history: Optional[List[Dict]] = None
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
    # CORREÇÃO: Verifica se há mensagens anteriores com dor antes de detectar trigger
    # Se já houve indicação de dor, qualquer mensagem subsequente dispara PACOTE_FASE_2
    current_stage = thread_meta.get("lead_stage") if thread_meta else None
    
    # Verifica se há mensagens anteriores com dor (apenas se está em FRIO)
    has_previous_pain = False
    if current_stage == FUNIL_LONGO_FASE_1_FRIO and message_history:
        # Lista de palavras-chave de dor (mesma lista usada em detect_funil_longo_trigger)
        dor_keywords = [
            "dor", "problema", "incomoda", "quero emagrecer", "quero perder peso",
            "barriga", "flacidez", "celulite", "autoestima",
            "tenho vergonha", "sinto vergonha", "me dá vergonha", "vergonha de",
            "não gosto", "me incomoda", "me derruba", "travamento", "objetivo",
            "quero definir", "quero ganhar massa", "pochete", "papada",
            "gordinha", "gordo", "gorda", "meio gordinha", "meio gordo", "meio gorda",
            "gorda", "obesa", "obeso", "estou gorda", "me sinto gorda", "sou gorda",
            "triste", "me sinto", "me sinto muito", "sentindo", "estou me sentindo",
            "insatisfeita", "insatisfeito", "não gosto do meu", "não gosto da minha",
            "evito", "não consigo", "sempre desisto", "falta disciplina",
            "emagrecer", "emagrecer msm", "queria emagrecer", "preciso emagrecer",
            "impossível continuar", "não dá mais", "não aguento mais", "não aguento",
            "preciso mudar", "preciso mudar isso", "tem que mudar", "tem q mudar",
            "não posso mais", "não consigo mais", "não dá pra continuar", "não dá pra continuar assim",
            "preciso fazer algo", "preciso fazer alguma coisa", "algo tem que mudar",
            "tem que ser diferente", "tem q ser diferente", "preciso de uma solução",
            "não sei", "n sei", "não sei o que", "n sei o que", "não sei bem",
            "n sei bem", "não sei exatamente", "n sei exatamente", "não sei exataemnte",
            "n sei exataemnte", "não sei direito", "n sei direito", "não sei como",
            "n sei como", "não tenho certeza", "n tenho certeza", "não sei ao certo",
            "n sei ao certo", "tô perdida", "to perdida", "estou perdida", "tô confusa",
            "to confusa", "estou confusa", "não entendo", "n entendo", "não entendi",
            "n entendi", "me ajuda", "me ajuda ai", "me ajuda aí", "preciso de ajuda",
            "preciso ajuda", "me orienta", "me oriente", "me explica", "me fala"
        ]
        
        # Verifica mensagens anteriores do usuário (role="user")
        for msg in message_history:
            if msg.get("role") == "user":
                msg_content = msg.get("content", "").lower()
                # Verifica se contém palavras-chave de dor
                if any(keyword in msg_content for keyword in dor_keywords):
                    # Exclui "falta de vergonha" que indica interesse, não dor
                    if "falta de vergonha" not in msg_content and "falta vergonha na cara" not in msg_content and "vergonha na cara" not in msg_content:
                        has_previous_pain = True
                        print(f"[AUTOMATION] ✅ Dor detectada em mensagem anterior: '{msg_content[:100]}'")
                        break
    
    # Inicializa intent como None
    intent = None
    
    # Se já houve dor anteriormente e está em FRIO, dispara DOR_DETECTADA diretamente
    if has_previous_pain and current_stage == FUNIL_LONGO_FASE_1_FRIO:
        trigger = "DOR_DETECTADA"
        intent = "OTHER"  # Define intent para evitar erro no print
        print(f"[AUTOMATION] 🎯 Dor anterior detectada + mensagem subsequente -> DOR_DETECTADA (bypass detect_funil_longo_trigger)")
    else:
        # CORREÇÃO D: Usa intent_classifier para distinguir ASK_PLANS vs CHOOSE_PLAN ANTES de detectar trigger
        from .intent_classifier import detect_plans_intent
        
        # Detecta intent primeiro para ajustar trigger
        intent = detect_plans_intent(message, current_stage)
        
        # Se for CHOOSE_PLAN, força trigger ESCOLHEU_PLANO (não passa por detect_funil_longo_trigger)
        if intent == "CHOOSE_PLAN":
            trigger = "ESCOLHEU_PLANO"
            print(f"[AUTOMATION] 🎯 Intent CHOOSE_PLAN detectado -> trigger ESCOLHEU_PLANO (bypass detect_funil_longo_trigger)")
        else:
            trigger = detect_funil_longo_trigger(message, thread_meta)
    
    if trigger:
        print(f"[AUTOMATION] 🎯 Gatilho detectado: {trigger} (mensagem: '{message[:100]}', stage: {thread_meta.get('lead_stage')}, intent: {intent})")
        new_stage, metadata = await execute_funil_longo_action(
            trigger, phone_number, thread_meta, db_session, thread_id, message
        )
        # FASE 1 (ENTRY_FUNIL_LONGO): Automação envia apenas áudio, NÃO chama LLM (aguarda resposta da lead)
        # FASE 2 (DOR_DETECTADA): Automação executa PACOTE_FASE_2 fixo, NÃO chama LLM
        # FASE 3 (INTERESSE_PLANO): Automação executa PACOTE_FASE_3 fixo, NÃO chama LLM
        # FASE 4 (ESCOLHEU_PLANO): Automação envia link, NÃO chama LLM
        # Outras fases: Automação completa, não chama LLM
        if trigger == "ENTRY_FUNIL_LONGO":
            # Fase 1: automação já enviou áudio, não precisa chamar LLM agora
            metadata["event"] = trigger
            return new_stage, metadata, True  # should_skip=True: não chame LLM, aguarde resposta da lead
        elif trigger == "DOR_DETECTADA":
            # Fase 2: automação executou PACOTE_FASE_2 fixo, não chama LLM
            metadata["event"] = trigger
            return new_stage, metadata, True  # should_skip=True: pacote fixo já executou tudo
        elif trigger == "INTERESSE_PLANO":
            # Fase 3: automação executou PACOTE_FASE_3 fixo, não chama LLM
            metadata["event"] = trigger
            return new_stage, metadata, True  # should_skip=True: pacote fixo já executou tudo
        elif trigger == "ESCOLHEU_PLANO":
            # Fase 4: automação enviou link, não chama LLM
            metadata["event"] = trigger
            return new_stage, metadata, True  # should_skip=True: link já foi enviado
        else:
            # Outras fases: automação completa, não chama LLM
            return new_stage, metadata, True  # should_skip=True: não chame LLM
    
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
        print(f"[AUTOMATION] ✅ [ORDEM 1/2] Áudio BF enviado para {phone_number}")
        
        # Delay após áudio para garantir ordem de entrega
        await asyncio.sleep(3.0)  # 3.0s após áudio
        print(f"[AUTOMATION] ⏳ Delay de 3.0s após áudio BF aplicado (GARANTIR ORDEM DE ENTREGA)")
    
    # Texto de acompanhamento (DEPOIS do áudio)
    bf_text = "Gataaaaa, olha issoooo 🔥🔥🔥\n\nSaiu uma condição INSANA da Black Friday, só HOJE!!\n\nQuer saber como funciona pra você aproveitar?"
    await asyncio.to_thread(twilio_provider.send_text, phone_number, bf_text, "BOT")
    print(f"[AUTOMATION] ✅ [ORDEM 2/2] Texto BF enviado")
    
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
        print(f"[AUTOMATION] ✅ [ORDEM 1/2] Áudio BF follow-up enviado para {phone_number}")
        
        # Delay após áudio para garantir ordem de entrega
        await asyncio.sleep(3.0)  # 3.0s após áudio
        print(f"[AUTOMATION] ⏳ Delay de 3.0s após áudio BF follow-up aplicado (GARANTIR ORDEM DE ENTREGA)")
    
    # Texto de acompanhamento (DEPOIS do áudio)
    followup_text = "Só passando aqui rapidinho porque essa promoção é literalmente a mais forte do ano 🔥\n\nSe ainda fizer sentido pra você, me chama aqui que te explico antes de acabar!"
    await asyncio.to_thread(twilio_provider.send_text, phone_number, followup_text, "BOT")
    print(f"[AUTOMATION] ✅ [ORDEM 2/2] Texto BF follow-up enviado")
    
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
        print(f"[AUTOMATION] ✅ [ORDEM 1/2] Áudio recuperação 50% follow-up 1 enviado para {phone_number}")
        
        # Delay após áudio para garantir ordem de entrega
        await asyncio.sleep(3.0)  # 3.0s após áudio
        print(f"[AUTOMATION] ⏳ Delay de 3.0s após áudio recuperação 50% aplicado (GARANTIR ORDEM DE ENTREGA)")
    
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
        print(f"[AUTOMATION] ✅ [ORDEM 1/2] Áudio recuperação 50% último chamado enviado para {phone_number}")
        
        # Delay após áudio para garantir ordem de entrega
        await asyncio.sleep(3.0)  # 3.0s após áudio
        print(f"[AUTOMATION] ⏳ Delay de 3.0s após áudio recuperação 50% aplicado (GARANTIR ORDEM DE ENTREGA)")
    
    # Texto de acompanhamento (DEPOIS do áudio)
    followup_text = "Prometo que é a última vez que apareço aqui sobre essa condição 🙈\n\nSe ainda bater aquela vontade de começar sua transformação com 50% OFF, é agora ou só na próxima… 😅🔥"
    await asyncio.to_thread(twilio_provider.send_text, phone_number, followup_text, "BOT")
    print(f"[AUTOMATION] ✅ [ORDEM 2/2] Texto recuperação 50% último chamado enviado")
    
    new_stage = RECUP_50_SEM_RESPOSTA_2
    metadata["audio_sent"] = "03-audio-ultimo-chamado"
    metadata["event"] = "RECUP_50_FOLLOWUP_2"
    
    return new_stage, metadata

