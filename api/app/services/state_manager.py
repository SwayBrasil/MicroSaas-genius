# api/app/services/state_manager.py
"""
Gerenciador de Máquina de Estados - Implementa toda a lógica de transição
"""
import time
import json
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta

from .state_machine import (
    LeadStage, CurrentFlow, PurchaseStatus, PainPoint, PlanInterest,
    FunilLongoStep, BFMiniStep, EventType, Transition,
    FUNIL_LONGO_TRANSITIONS, BF_MINI_TRANSITIONS,
    StateMachineRules, MessageTemplates
)
from .funnel_packages import execute_pacote_fase_2, execute_pacote_fase_3
from .assets_library import resolve_audio_url, resolve_image_url
from ..providers import twilio as twilio_provider


class StateManager:
    """Gerenciador principal da máquina de estados"""
    
    def __init__(self, thread, db_session=None):
        self.thread = thread
        self.db_session = db_session
        self.meta = self._get_meta()
    
    def _get_meta(self) -> Dict[str, Any]:
        """Obtém metadata da thread"""
        if not self.thread.meta:
            return {}
        if isinstance(self.thread.meta, dict):
            return self.thread.meta.copy()
        if isinstance(self.thread.meta, str):
            try:
                return json.loads(self.thread.meta)
            except:
                return {}
        return {}
    
    def _save_meta(self):
        """Salva metadata na thread"""
        self.thread.meta = self.meta
        if self.db_session:
            self.db_session.commit()
            self.db_session.refresh(self.thread)
    
    def get_current_state(self) -> Tuple[str, str, str]:
        """Retorna (current_flow, flow_step, lead_stage)"""
        current_flow = self.meta.get("current_flow", CurrentFlow.NONE)
        flow_step = self.meta.get("flow_step")
        lead_stage = self.thread.lead_stage or self.meta.get("lead_stage", LeadStage.FRIO)
        return current_flow, flow_step, lead_stage
    
    def update_state(
        self,
        current_flow: Optional[str] = None,
        flow_step: Optional[str] = None,
        lead_stage: Optional[str] = None,
        purchase_status: Optional[str] = None,
        pain_point: Optional[str] = None,
        plan_interest: Optional[str] = None,
        **kwargs
    ):
        """Atualiza estado da thread"""
        if current_flow:
            self.meta["current_flow"] = current_flow
        if flow_step:
            self.meta["flow_step"] = flow_step
        if lead_stage:
            self.meta["lead_stage"] = lead_stage
            self.thread.lead_stage = lead_stage
        if purchase_status:
            self.meta["purchase_status"] = purchase_status
        if pain_point:
            self.meta["pain_point"] = pain_point
        if plan_interest:
            self.meta["plan_interest"] = plan_interest
        
        # Atualiza timestamps
        self.meta["last_state_update"] = datetime.now().isoformat()
        
        # Atualiza outros campos
        for key, value in kwargs.items():
            self.meta[key] = value
        
        self._save_meta()
    
    def update_timestamps(self, inbound: bool = False, outbound: bool = False, offer: bool = False):
        """Atualiza timestamps de interação"""
        now = time.time()
        if inbound:
            self.meta["last_inbound_at"] = now
        if outbound:
            self.meta["last_outbound_at"] = now
        if offer:
            self.meta["last_offer_at"] = now
        self._save_meta()
    
    def find_transition(self, current_step: str, event: EventType, current_flow: str) -> Optional[Transition]:
        """Encontra transição válida para o estado atual"""
        transitions = FUNIL_LONGO_TRANSITIONS if current_flow == CurrentFlow.FUNIL_LONGO else BF_MINI_TRANSITIONS
        
        for trans in transitions:
            if trans.from_step == current_step and trans.event == event:
                # Verifica condições se houver
                if trans.conditions:
                    # TODO: Implementar verificação de condições
                    pass
                return trans
        return None
    
    def process_event(self, event: EventType, event_data: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
        """
        Processa um evento e executa transição se válida.
        
        Returns:
            (success, action_result)
        """
        current_flow, flow_step, lead_stage = self.get_current_state()
        
        # Se não tem estado inicial, inicializa
        if not flow_step and current_flow == CurrentFlow.NONE:
            if event == EventType.FIRST_CONTACT:
                return self.handle_l1_abertura()
        
        # Encontra transição
        transition = self.find_transition(flow_step, event, current_flow)
        if not transition:
            print(f"[STATE_MANAGER] ⚠️ Nenhuma transição encontrada: step={flow_step}, event={event}")
            return False, None
        
        # Executa ação
        action_func = getattr(self, transition.action, None)
        if not action_func:
            print(f"[STATE_MANAGER] ❌ Handler não encontrado: {transition.action}")
            return False, None
        
        try:
            result = action_func(event_data or {})
            # Atualiza estado para próximo passo
            self.update_state(
                flow_step=transition.to_step,
                current_flow=current_flow  # Mantém o fluxo atual
            )
            return True, result
        except Exception as e:
            print(f"[STATE_MANAGER] ❌ Erro ao executar {transition.action}: {e}")
            import traceback
            traceback.print_exc()
            return False, None
    
    # ==================== HANDLERS DO FUNIL LONGO ====================
    
    async def handle_l1_abertura(self, event_data: Dict = None) -> str:
        """L1_ABERTURA: Envia áudio1 e pergunta sobre dor"""
        phone_number = self.thread.external_user_phone
        
        # Envia áudio1
        audio_url = resolve_audio_url("audio1_boas_vindas")
        if audio_url:
            await twilio_provider.send_audio(phone_number, audio_url, "BOT")
        
        # Aguarda um pouco
        import asyncio
        await asyncio.sleep(1.0)
        
        # Envia pergunta
        await twilio_provider.send_text(phone_number, MessageTemplates.L1_PERGUNTA_DOR, "BOT")
        
        self.update_state(
            current_flow=CurrentFlow.FUNIL_LONGO,
            flow_step=FunilLongoStep.L2_COLETA_DOR,
            lead_stage=LeadStage.FRIO
        )
        self.update_timestamps(outbound=True)
        
        return "L1_ABERTURA executado"
    
    async def handle_l2_coleta_dor(self, event_data: Dict = None) -> str:
        """L2_COLETA_DOR: Executa PACOTE_FASE_2 (áudio2 + imagens + textos)"""
        phone_number = self.thread.external_user_phone
        message = event_data.get("message", "")
        
        # Classifica dor (por enquanto usa genérico)
        pain_point = self._classify_pain(message)
        
        # Executa pacote fixo
        await execute_pacote_fase_2(
            phone_number=phone_number,
            audio_id="audio2_dor_generica",
            db_session=self.db_session,
            thread_id=self.thread.id
        )
        
        self.update_state(
            flow_step=FunilLongoStep.L3_DECISAO_OBJECAO,
            lead_stage=LeadStage.AQUECIMENTO,
            pain_point=pain_point
        )
        self.update_timestamps(outbound=True)
        
        return "L2_COLETA_DOR executado"
    
    def _classify_pain(self, message: str) -> str:
        """Classifica a dor mencionada (simplificado por enquanto)"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["emagrecer", "secar", "perder peso", "gordura"]):
            return PainPoint.EMAGRECIMENTO_SECAR
        elif any(word in message_lower for word in ["massa", "bumbum", "ganhar", "aumentar"]):
            return PainPoint.GANHO_MASSA_BUMBUM
        elif any(word in message_lower for word in ["pochete", "flacidez", "celulite"]):
            return PainPoint.POCHEte_FLACIDEZ_CELULITE
        elif any(word in message_lower for word in ["alimentação", "dieta", "resultado não vem"]):
            return PainPoint.ALIMENTACAO_RESULTADO_NAO_VEM
        elif any(word in message_lower for word in ["autoestima", "motivação", "confiança"]):
            return PainPoint.AUTOESTIMA_MOTIVACAO
        
        return PainPoint.NONE
    
    async def handle_l3_objeção(self, event_data: Dict = None) -> str:
        """L3_DECISAO_OBJECAO: Quebra objeção e puxa para planos"""
        phone_number = self.thread.external_user_phone
        message = event_data.get("message", "")
        
        # Resposta curta validando + quebrando objeção
        # TODO: Usar LLM para quebrar objeção de forma personalizada
        response = "Entendo, gata. Mas dá pra resolver sim! Posso te explicar rapidinho os planos pra você ver o que encaixa melhor?"
        
        await twilio_provider.send_text(phone_number, response, "BOT")
        
        self.update_state(
            flow_step=FunilLongoStep.L4_PERGUNTA_PLANOS,
            lead_stage=LeadStage.AQUECIDO
        )
        self.update_timestamps(outbound=True)
        
        return "L3_OBJECAO executado"
    
    async def handle_l3_interesse(self, event_data: Dict = None) -> str:
        """L3_DECISAO_OBJECAO: Interesse direto"""
        phone_number = self.thread.external_user_phone
        
        await twilio_provider.send_text(phone_number, MessageTemplates.L3_INTERESSE, "BOT")
        
        self.update_state(
            flow_step=FunilLongoStep.L4_PERGUNTA_PLANOS,
            lead_stage=LeadStage.AQUECIDO
        )
        self.update_timestamps(outbound=True)
        
        return "L3_INTERESSE executado"
    
    async def handle_l4_pergunta_planos(self, event_data: Dict = None) -> str:
        """L4_PERGUNTA_PLANOS: Pergunta se quer saber dos planos"""
        phone_number = self.thread.external_user_phone
        
        await twilio_provider.send_text(phone_number, MessageTemplates.L4_PERGUNTA, "BOT")
        
        self.update_timestamps(outbound=True)
        
        return "L4_PERGUNTA_PLANOS executado"
    
    async def handle_l4_pergunta_planos_with_context(self, event_data: Dict = None) -> str:
        """L4 com contexto: quando pede preço direto"""
        phone_number = self.thread.external_user_phone
        
        # Valida e pede contexto mínimo
        response = "Tem mensal e anual! Mas antes, me conta rapidinho: teu foco é mais secar ou ganhar massa?"
        
        await twilio_provider.send_text(phone_number, response, "BOT")
        
        self.update_state(
            flow_step=FunilLongoStep.L4_PERGUNTA_PLANOS,
            lead_stage=LeadStage.QUENTE
        )
        self.update_timestamps(outbound=True)
        
        return "L4_PERGUNTA_PLANOS_WITH_CONTEXT executado"
    
    async def handle_l5_planos(self, event_data: Dict = None) -> str:
        """L5_PLANOS: Executa PACOTE_FASE_3 (intro + áudio3 + planos + pergunta)"""
        phone_number = self.thread.external_user_phone
        
        # Executa pacote fixo
        await execute_pacote_fase_3(
            phone_number=phone_number,
            db_session=self.db_session,
            thread_id=self.thread.id
        )
        
        self.update_state(
            flow_step=FunilLongoStep.L6_ESCOLHA_PLANO,
            lead_stage=LeadStage.QUENTE
        )
        self.update_timestamps(outbound=True, offer=True)
        
        return "L5_PLANOS executado"
    
    async def handle_l6_mensal(self, event_data: Dict = None) -> str:
        """L6_ESCOLHA_PLANO: Escolheu mensal"""
        phone_number = self.thread.external_user_phone
        
        template = f"""*🔥 Bora garantir sua transformação agoraaaa!!*

Aqui tá o link do MENSAL pra você finalizar:

➡️ {MessageTemplates.LINK_MENSAL}

Assim que finalizar, me avisa que já te envio todos os acessos... Fico te esperando aqui!! 🩷"""
        
        await twilio_provider.send_text(phone_number, template, "BOT")
        
        self.update_state(
            flow_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
            purchase_status=PurchaseStatus.INITIATED,
            plan_interest=PlanInterest.MENSAL
        )
        self.update_timestamps(outbound=True, offer=True)
        
        return "L6_MENSAL executado"
    
    async def handle_l6_anual(self, event_data: Dict = None) -> str:
        """L6_ESCOLHA_PLANO: Escolheu anual"""
        phone_number = self.thread.external_user_phone
        
        template = f"""*Amoo!🔥 Bora garantir sua transformação agoraaaa!!*

Aqui está o link pra você finalizar o ANUAL:

➡️ {MessageTemplates.LINK_ANUAL}

_💳 Na hora da compra, basta antes ajustar o limite do cartão, lá no app do seu banco, para R$50 (isso só precisa ser feito uma única vez). O sistema vai cobrar apenas a parcela mensal e não vai comprometer seu limite total._

Assim que finalizar, me avisa que já te envio todos os acessos... Fico te esperando aqui!! 🩷"""
        
        await twilio_provider.send_text(phone_number, template, "BOT")
        
        self.update_state(
            flow_step=FunilLongoStep.L7_AGUARDANDO_COMPRA,
            purchase_status=PurchaseStatus.INITIATED,
            plan_interest=PlanInterest.ANUAL
        )
        self.update_timestamps(outbound=True, offer=True)
        
        return "L6_ANUAL executado"
    
    async def handle_l7_aguardando(self, event_data: Dict = None) -> str:
        """L7_AGUARDANDO_COMPRA: Lead confirma compra"""
        phone_number = self.thread.external_user_phone
        
        await twilio_provider.send_text(phone_number, MessageTemplates.L7_CONFIRMA, "BOT")
        
        self.update_timestamps(outbound=True)
        
        return "L7_AGUARDANDO executado"
    
    async def handle_l7_resgate(self, event_data: Dict = None) -> str:
        """L7_AGUARDANDO_COMPRA: Resgate após tempo sem resposta"""
        phone_number = self.thread.external_user_phone
        
        # Envia áudio de resgate
        audio_url = resolve_audio_url("audio5_resgate_boleto")
        if audio_url:
            await twilio_provider.send_audio(phone_number, audio_url, "BOT")
        
        # Reenvia link
        plan_interest = self.meta.get("plan_interest", PlanInterest.UNKNOWN)
        link = MessageTemplates.LINK_ANUAL if plan_interest == PlanInterest.ANUAL else MessageTemplates.LINK_MENSAL
        
        await twilio_provider.send_text(phone_number, f"Segue o link novamente: {link}", "BOT")
        
        self.update_timestamps(outbound=True)
        
        return "L7_RESGATE executado"
    
    async def handle_l8_pendente(self, event_data: Dict = None) -> str:
        """L8_COMPRA_PENDENTE: Compra ficou pendente"""
        import asyncio
        phone_number = self.thread.external_user_phone
        
        # CRÍTICO: Ordem garantida - áudio ANTES do texto
        # Envia áudio de resgate primeiro
        audio_url = resolve_audio_url("audio5_resgate_boleto")
        if audio_url:
            await asyncio.to_thread(twilio_provider.send_audio, phone_number, audio_url, "BOT")
            print(f"[L8_PENDENTE] ✅ [ORDEM 1/2] Áudio enviado: audio5_resgate_boleto")
            
            # Delay após áudio para garantir ordem de entrega
            await asyncio.sleep(3.0)  # 3.0s após áudio
            print(f"[L8_PENDENTE] ⏳ Delay de 3.0s após áudio aplicado (GARANTIR ORDEM DE ENTREGA)")
        
        # Depois envia texto
        await asyncio.to_thread(twilio_provider.send_text, phone_number, MessageTemplates.L8_PERGUNTA, "BOT")
        print(f"[L8_PENDENTE] ✅ [ORDEM 2/2] Texto enviado: {MessageTemplates.L8_PERGUNTA[:50]}...")
        
        self.update_state(
            flow_step=FunilLongoStep.L8_COMPRA_PENDENTE,
            purchase_status=PurchaseStatus.PENDING
        )
        self.update_timestamps(outbound=True)
        
        return "L8_PENDENTE executado"
    
    async def handle_l9_pos_compra(self, event_data: Dict = None) -> str:
        """L9_POS_COMPRA: Webhook PAID - Envia mensagem pós-compra completa"""
        from .post_purchase import send_post_purchase_message
        
        phone_number = self.thread.external_user_phone
        webhook_data = event_data.get("webhook_data", {})
        
        # Verifica idempotência
        transaction_id = webhook_data.get("transaction_id") or webhook_data.get("order_id")
        if transaction_id:
            seen_ids = self.meta.get("seen_event_ids", [])
            if transaction_id in seen_ids:
                print(f"[STATE_MANAGER] ⚠️ Webhook duplicado ignorado: {transaction_id}")
                return "Webhook duplicado ignorado"
            seen_ids.append(transaction_id)
            self.meta["seen_event_ids"] = seen_ids
        
        # Envia mensagem pós-compra
        await send_post_purchase_message(
            phone_number=phone_number,
            thread_id=self.thread.id,
            db_session=self.db_session,
            webhook_data=webhook_data
        )
        
        self.update_state(
            flow_step=FunilLongoStep.L9_POS_COMPRA,
            purchase_status=PurchaseStatus.PAID,
            lead_stage=LeadStage.ASSINANTE_ATIVO,
            current_flow=CurrentFlow.NONE
        )
        self.update_timestamps(outbound=True)
        
        return "L9_POS_COMPRA executado"
    
    # ==================== HANDLERS DE CASOS ESPECIAIS ====================
    
    async def handle_empty_message(self, event_data: Dict = None) -> str:
        """Trata mensagem vazia ou sem sentido"""
        phone_number = self.thread.external_user_phone
        
        await twilio_provider.send_text(phone_number, MessageTemplates.EMPTY_MESSAGE_RESPONSE, "BOT")
        
        self.update_timestamps(outbound=True)
        
        return "EMPTY_MESSAGE tratado"
    
    async def handle_l5_duvida(self, event_data: Dict = None) -> str:
        """L5_PLANOS: Responde dúvida sobre planos"""
        # TODO: Usar LLM para responder dúvida específica
        phone_number = self.thread.external_user_phone
        
        response = "Claro! Qual sua dúvida específica sobre os planos?"
        await twilio_provider.send_text(phone_number, response, "BOT")
        
        self.update_timestamps(outbound=True)
        
        return "L5_DUVIDA tratado"
    
    async def handle_l7_erro(self, event_data: Dict = None) -> str:
        """L7_AGUARDANDO_COMPRA: Erro no pagamento"""
        phone_number = self.thread.external_user_phone
        
        await twilio_provider.send_text(phone_number, MessageTemplates.L7_ERRO, "BOT")
        
        # Reenvia link
        plan_interest = self.meta.get("plan_interest", PlanInterest.UNKNOWN)
        link = MessageTemplates.LINK_ANUAL if plan_interest == PlanInterest.ANUAL else MessageTemplates.LINK_MENSAL
        
        await twilio_provider.send_text(phone_number, f"Segue o link novamente: {link}", "BOT")
        
        self.update_timestamps(outbound=True)
        
        return "L7_ERRO tratado"
    
    # ==================== HANDLERS DO MINI FUNIL BF ====================
    # TODO: Implementar handlers do BF quando necessário

