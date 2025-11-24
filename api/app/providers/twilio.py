# app/providers/twilio.py
import os
import time
import re
from twilio.rest import Client

# 🔧 Configurações de ambiente
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+5561947565536")

# Limite de caracteres do Twilio (1600 para mensagens concatenadas)
TWILIO_MAX_LENGTH = 1600

_client = Client(ACCOUNT_SID, AUTH_TOKEN)


def _fmt_whatsapp(num: str) -> str:
    """Garante que o número esteja no formato whatsapp:+55DDDNNNNNNN"""
    n = num.strip()
    if n.startswith("whatsapp:"):
        return n
    if n.startswith("+"):
        return f"whatsapp:{n}"
    return f"whatsapp:+{n}"


def _split_message(text: str, max_length: int = TWILIO_MAX_LENGTH) -> list[str]:
    """
    Divide uma mensagem longa em chunks menores de forma inteligente.
    Respeita parágrafos, listas e mantém contexto semântico.
    """
    if len(text) <= max_length:
        return [text]
    
    # Reserva espaço para indicador de parte (ex: " [1/3]")
    # Estimativa: até 10 partes = " [10/10]" = 7 chars
    indicator_space = 10
    effective_max = max_length - indicator_space
    
    chunks = []
    remaining = text.strip()
    total_chars = len(text)
    
    # Estima quantas partes serão necessárias (para o indicador)
    estimated_parts = (total_chars // max_length) + 1
    
    while len(remaining) > effective_max:
        chunk = remaining[:effective_max]
        
        # Prioridade 1: Quebra dupla de linha (parágrafo)
        last_double_newline = chunk.rfind('\n\n')
        if last_double_newline != -1 and last_double_newline > effective_max * 0.5:
            split_pos = last_double_newline + 2
            chunks.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
            continue
        
        # Prioridade 2: Detectar itens de lista e quebrar entre itens completos
        # Procura por padrões de lista: "1. ", "2. ", "- ", "* ", "• ", etc.
        list_patterns = [
            r'\n\d+\.\s+\*\*',  # "6. **["
            r'\n\d+\.\s+',       # "6. "
            r'\n[-*•]\s+',       # "- ", "* ", "• "
        ]
        
        best_list_break = -1
        for pattern in list_patterns:
            matches = list(re.finditer(pattern, remaining[:effective_max]))
            if matches:
                # Pega a última ocorrência antes do limite
                for match in reversed(matches):
                    if match.start() > effective_max * 0.3:  # Não muito no início
                        best_list_break = match.start()
                        break
                if best_list_break != -1:
                    break
        
        if best_list_break != -1:
            split_pos = best_list_break
            chunks.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
            continue
        
        # Prioridade 3: Quebra simples de linha (se não estiver muito no início)
        last_newline = chunk.rfind('\n')
        if last_newline != -1 and last_newline > effective_max * 0.3:
            # Verifica se a próxima linha parece ser início de item de lista
            if last_newline + 1 < len(remaining):
                next_char = remaining[last_newline + 1:last_newline + 10]
                # Verifica padrões comuns de início de lista
                is_list_item = (
                    next_char.strip().startswith(('-', '*', '•')) or
                    (len(next_char) >= 2 and next_char[0].isdigit() and next_char[1] in ['.', ')'])
                )
                
                if is_list_item:
                    # Se a próxima linha é item de lista, quebra antes dela
                    split_pos = last_newline + 1
                    chunks.append(remaining[:split_pos].strip())
                    remaining = remaining[split_pos:].strip()
                    continue
            
            # Quebra normal em linha
            split_pos = last_newline + 1
            chunks.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
            continue
        
        # Prioridade 3: Espaço (evita cortar palavras)
        last_space = chunk.rfind(' ')
        if last_space != -1 and last_space > effective_max * 0.5:
            split_pos = last_space + 1
            chunks.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
            continue
        
        # Prioridade 4: Pontuação (ponto, vírgula, ponto e vírgula)
        for punct in ['. ', ', ', '; ', '! ', '? ']:
            last_punct = chunk.rfind(punct)
            if last_punct != -1 and last_punct > effective_max * 0.4:
                split_pos = last_punct + len(punct)
                chunks.append(remaining[:split_pos].strip())
                remaining = remaining[split_pos:].strip()
                break
        else:
            # Último recurso: corta no limite (evita cortar no meio de uma palavra se possível)
            # Tenta encontrar o último caractere não-alfanumérico
            for i in range(effective_max - 1, max(0, effective_max - 50), -1):
                if not chunk[i].isalnum():
                    split_pos = i + 1
                    chunks.append(remaining[:split_pos].strip())
                    remaining = remaining[split_pos:].strip()
                    break
            else:
                # Força corte no limite
                split_pos = effective_max
                chunks.append(remaining[:split_pos].strip())
                remaining = remaining[split_pos:].strip()
    
    # Adiciona o último pedaço
    if remaining:
        chunks.append(remaining)
    
    # Adiciona indicadores de parte se houver múltiplas partes
    if len(chunks) > 1:
        total_parts = len(chunks)
        formatted_chunks = []
        for i, chunk in enumerate(chunks):
            part_indicator = f" [{i+1}/{total_parts}]"
            # Verifica se cabe o indicador
            if len(chunk) + len(part_indicator) <= max_length:
                formatted_chunks.append(chunk + part_indicator)
            else:
                # Se não cabe, tenta colocar no início
                if len(part_indicator + chunk) <= max_length:
                    formatted_chunks.append(part_indicator + " " + chunk)
                else:
                    # Se ainda não cabe, envia sem indicador (melhor que erro)
                    formatted_chunks.append(chunk)
        return formatted_chunks
    
    return chunks


def send_text(to_e164: str, body: str, sender: str = "BOT") -> str:
    """
    Envia mensagem de texto pelo WhatsApp via Twilio.
    Se a mensagem for maior que 1600 caracteres, divide em múltiplas mensagens.
    sender: "BOT" ou "HUMANO" (apenas para log)
    Retorna o SID da primeira mensagem enviada.
    """
    if not ACCOUNT_SID or not AUTH_TOKEN or not FROM:
        raise RuntimeError(
            "❌ TWILIO envs faltando (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM)"
        )

    to = _fmt_whatsapp(to_e164)
    from_ = FROM if FROM.startswith("whatsapp:") else f"whatsapp:{FROM}"

    # Divide a mensagem se necessário
    chunks = _split_message(body, TWILIO_MAX_LENGTH)
    
    if len(chunks) > 1:
        print(f"\033[93m[TWILIO] Mensagem longa detectada ({len(body)} chars), dividindo em {len(chunks)} partes\033[0m")
    
    first_sid = None
    
    # Envia cada chunk
    for i, chunk in enumerate(chunks):
        try:
            msg = _client.messages.create(to=to, from_=from_, body=chunk)
            
            if first_sid is None:
                first_sid = msg.sid
            
            # Log detalhado no terminal
            part_info = f" ({i+1}/{len(chunks)})" if len(chunks) > 1 else ""
            if sender.upper() == "BOT":
                print(f"\033[94m[TWILIO][BOT] → {to}{part_info} | SID={msg.sid} | {len(chunk)} chars\033[0m")  # azul
            else:
                print(f"\033[92m[TWILIO][HUMANO] → {to}{part_info} | SID={msg.sid} | {len(chunk)} chars\033[0m")  # verde
            
            # Pequeno delay entre mensagens para evitar rate limiting (apenas se houver múltiplas partes)
            if i < len(chunks) - 1:
                time.sleep(0.5)  # 500ms entre mensagens
                
        except Exception as e:
            print(f"\033[91m[TWILIO] Erro ao enviar parte {i+1}/{len(chunks)}: {str(e)}\033[0m")
            # Se for a primeira mensagem e falhar, propaga o erro
            if i == 0:
                raise
            # Se for uma mensagem subsequente, apenas loga o erro mas continua
    
    return first_sid or ""
