# api/app/services/event_detector.py
"""
Detector de Eventos - Converte mensagens do lead em EventType
"""
import re
from typing import Optional, Dict, Any
from .state_machine import EventType, FunilLongoStep, BFMiniStep


class EventDetector:
    """Detecta eventos a partir de mensagens do lead"""
    
    @staticmethod
    def detect_event(
        message: str,
        current_step: Optional[str] = None,
        current_flow: Optional[str] = None,
        is_first_message: bool = False
    ) -> EventType:
        """
        Detecta qual evento a mensagem representa.
        
        Args:
            message: Mensagem do lead
            current_step: Etapa atual do fluxo
            current_flow: Fluxo atual (FUNIL_LONGO, BF_MINI, etc.)
            is_first_message: Se é a primeira mensagem da conversa
        
        Returns:
            EventType detectado
        """
        message_lower = message.lower().strip()
        
        # Primeira mensagem
        if is_first_message or not current_step:
            return EventDetector._detect_first_contact(message_lower)
        
        # Detecta por etapa atual
        if current_flow == "FUNIL_LONGO":
            return EventDetector._detect_funil_longo_event(message_lower, current_step)
        elif current_flow == "BF_MINI":
            return EventDetector._detect_bf_event(message_lower, current_step)
        
        # Fallback: primeira mensagem
        return EventDetector._detect_first_contact(message_lower)
    
    @staticmethod
    def _detect_first_contact(message_lower: str) -> EventType:
        """Detecta primeiro contato"""
        first_contact_keywords = [
            "oi", "olá", "bom dia", "boa tarde", "boa noite",
            "quero saber", "quero entrar", "como funciona",
            "valores", "preço", "quanto custa"
        ]
        
        if any(keyword in message_lower for keyword in first_contact_keywords):
            return EventType.FIRST_CONTACT
        
        return EventType.FIRST_CONTACT  # Default
    
    @staticmethod
    def _detect_funil_longo_event(message_lower: str, current_step: str) -> EventType:
        """Detecta eventos do funil longo baseado na etapa atual"""
        
        # L1_ABERTURA ou L2_COLETA_DOR
        if current_step in [FunilLongoStep.L1_ABERTURA, FunilLongoStep.L2_COLETA_DOR]:
            # Detecta dor/objetivo
            pain_keywords = [
                "emagrecer", "secar", "perder peso", "gordura",
                "massa", "bumbum", "ganhar", "aumentar",
                "pochete", "flacidez", "celulite",
                "alimentação", "dieta", "resultado não vem",
                "autoestima", "motivação", "confiança"
            ]
            
            if any(keyword in message_lower for keyword in pain_keywords):
                return EventType.DESCRIBES_PAIN
            
            # Detecta pedido de preço direto
            if any(word in message_lower for word in ["preço", "quanto custa", "valores", "planos"]):
                return EventType.ASKS_PRICE
            
            # Mensagem vazia
            if len(message_lower) <= 2 or message_lower in ["?", "??", "1", "ok"]:
                return EventType.EMPTY_MESSAGE
        
        # L2_COLETA_DOR ou L3_DECISAO_OBJECAO
        if current_step in [FunilLongoStep.L2_COLETA_DOR, FunilLongoStep.L3_DECISAO_OBJECAO]:
            # Detecta objeção
            objection_keywords = [
                "sem tempo", "sem dinheiro", "não sei se consigo",
                "não funciona", "caro", "difícil", "não tenho",
                "não dá", "impossível"
            ]
            
            if any(keyword in message_lower for keyword in objection_keywords):
                return EventType.OBJECTION
            
            # Detecta interesse
            interest_keywords = [
                "sim", "pode", "quero", "legal", "ok", "entendi",
                "faz sentido", "gostei", "quero saber", "me explica",
                "conta pra mim", "me mostra"
            ]
            
            if any(keyword in message_lower for keyword in interest_keywords):
                return EventType.INTEREST
            
            # Detecta dúvida técnica
            technical_keywords = [
                "como funciona", "tem dieta", "tem treino",
                "serve pra", "tem suporte", "tem app"
            ]
            
            if any(keyword in message_lower for keyword in technical_keywords):
                return EventType.ASKS_TECHNICAL
        
        # L4_PERGUNTA_PLANOS
        if current_step == FunilLongoStep.L4_PERGUNTA_PLANOS:
            # Confirma que quer planos
            confirm_keywords = ["sim", "pode", "quero", "claro", "pode ser"]
            
            if any(keyword in message_lower for keyword in confirm_keywords):
                return EventType.CONFIRMS_PLANS
            
            # Pede preço mesmo assim
            if any(word in message_lower for word in ["preço", "quanto", "valores"]):
                return EventType.ASKS_PRICE
        
        # L5_PLANOS
        if current_step == FunilLongoStep.L5_PLANOS:
            # Escolhe mensal
            if any(word in message_lower for word in ["mensal", "quero o mensal", "vou querer o mensal"]):
                return EventType.CHOOSES_MENSAL
            
            # Escolhe anual
            if any(word in message_lower for word in ["anual", "quero o anual", "vou querer o anual"]):
                return EventType.CHOOSES_ANUAL
            
            # Dúvida sobre planos
            if any(word in message_lower for word in ["parcelamento", "cancelamento", "conteúdo", "suporte", "dúvida"]):
                return EventType.ASKS_TECHNICAL
        
        # L6_ESCOLHA_PLANO
        if current_step == FunilLongoStep.L6_ESCOLHA_PLANO:
            # Confirma compra
            if any(word in message_lower for word in ["comprei", "finalizei", "paguei", "ok"]):
                return EventType.CONFIRMS_PURCHASE
            
            # Erro no pagamento
            if any(word in message_lower for word in ["erro", "não passou", "cartão negado", "deu erro"]):
                return EventType.PURCHASE_ERROR
        
        # L7_AGUARDANDO_COMPRA
        if current_step == FunilLongoStep.L7_AGUARDANDO_COMPRA:
            if any(word in message_lower for word in ["comprei", "finalizei", "paguei"]):
                return EventType.CONFIRMS_PURCHASE
            
            if any(word in message_lower for word in ["erro", "não passou", "cartão negado"]):
                return EventType.PURCHASE_ERROR
        
        # Mensagem vazia ou sem sentido
        if len(message_lower) <= 2:
            return EventType.EMPTY_MESSAGE
        
        # Default: interesse genérico
        return EventType.INTEREST
    
    @staticmethod
    def _detect_bf_event(message_lower: str, current_step: str) -> EventType:
        """Detecta eventos do mini funil BF"""
        
        # BF1_OFERTA ou BF2_AGUARDANDO
        if current_step in [BFMiniStep.BF1_OFERTA, BFMiniStep.BF2_AGUARDANDO]:
            # Confirma interesse
            if any(word in message_lower for word in ["quero", "manda", "sim", "pode"]):
                return EventType.BF_CONFIRMS
            
            # Objeção
            if any(word in message_lower for word in ["caro", "sem dinheiro", "depois"]):
                return EventType.BF_OBJECTION
        
        # BF3_AGUARDANDO_COMPRA
        if current_step == BFMiniStep.BF3_AGUARDANDO_COMPRA:
            if any(word in message_lower for word in ["comprei", "finalizei", "paguei"]):
                return EventType.CONFIRMS_PURCHASE
        
        return EventType.NO_RESPONSE
    
    @staticmethod
    def detect_webhook_event(webhook_data: Dict[str, Any]) -> Optional[EventType]:
        """Detecta tipo de evento do webhook"""
        status = webhook_data.get("status", "").lower()
        event_type = webhook_data.get("event_type", "").lower()
        
        if "approved" in status or "paid" in status or "approved" in event_type:
            return EventType.WEBHOOK_PAID
        
        if "pending" in status or "pending" in event_type:
            return EventType.WEBHOOK_PENDING
        
        if "failed" in status or "declined" in status or "failed" in event_type:
            return EventType.WEBHOOK_FAILED
        
        if "refunded" in status or "chargeback" in status or "refunded" in event_type:
            return EventType.WEBHOOK_REFUNDED
        
        return None

