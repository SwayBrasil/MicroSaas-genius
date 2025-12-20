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

# Inicializa cliente apenas se as credenciais estiverem configuradas
_client = None
if ACCOUNT_SID and AUTH_TOKEN:
    try:
        _client = Client(ACCOUNT_SID, AUTH_TOKEN)
    except Exception:
        pass


def is_configured() -> bool:
    """Verifica se o Twilio está configurado corretamente"""
    return bool(ACCOUNT_SID and AUTH_TOKEN and FROM)


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
    
    # Não reserva espaço para indicador (removido conforme solicitado)
    effective_max = max_length
    
    chunks = []
    remaining = text.strip()
    
    while len(remaining) > effective_max:
        chunk = remaining[:effective_max]
        
        # Prioridade 1: Quebra dupla de linha (parágrafo)
        last_double_newline = chunk.rfind('\n\n')
        if last_double_newline != -1 and last_double_newline > effective_max * 0.5:
            split_pos = last_double_newline + 2
            chunks.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
            continue
        
        # Prioridade 2: Detectar itens de lista numerada e quebrar APÓS cada item completo
        # Procura por padrões de lista: "1. **", "2. **", etc. (produtos)
        # Busca TODOS os itens no chunk atual para encontrar o último item completo
        list_patterns = [
            r'\n(\d+)\.\s+\*\*',  # "6. **["
            r'\n(\d+)\.\s+',       # "6. "
        ]
        
        best_list_break = -1
        last_item_end = -1
        
        # Busca todos os itens de lista no chunk
        for pattern in list_patterns:
            matches = list(re.finditer(pattern, remaining))
            if matches:
                # Encontra o último item completo que cabe no limite
                for match in reversed(matches):
                    item_start = match.start()
                    item_num = match.group(1) if match.groups() else None
                    
                    # Se o item começa antes do limite, procura onde ele termina
                    if item_start < effective_max:
                        # Procura o próximo item ou fim do texto
                        next_item_match = None
                        for next_match in matches:
                            if next_match.start() > item_start:
                                next_item_match = next_match
                                break
                        
                        if next_item_match:
                            # Item termina antes do próximo item
                            item_end = next_item_match.start()
                        else:
                            # É o último item, termina no fim do texto ou no limite
                            item_end = min(len(remaining), effective_max)
                        
                        # Se o item completo cabe, usa ele
                        if item_end <= effective_max and item_end > effective_max * 0.3:
                            last_item_end = item_end
                            best_list_break = item_end
                            break
                
                if best_list_break != -1:
                    break
        
        if best_list_break != -1:
            # Quebra após o item completo
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
    
    # Retorna chunks sem indicadores de parte (removido conforme solicitado)
    return chunks


def send_text(to_e164: str, body: str, sender: str = "BOT") -> str:
    """
    Envia mensagem de texto pelo WhatsApp via Twilio.
    Se a mensagem for maior que 1600 caracteres, divide em múltiplas mensagens.
    sender: "BOT" ou "HUMANO" (apenas para log)
    Retorna o SID da primeira mensagem enviada.
    """
    if not is_configured():
        print(f"\033[93m[TWILIO] ⚠️ Twilio não configurado. Mensagem não enviada: {body[:50]}...\033[0m")
        return ""
    
    if not _client:
        print(f"\033[93m[TWILIO] ⚠️ Cliente Twilio não inicializado. Mensagem não enviada.\033[0m")
        return ""

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


def send_audio(to_e164: str, audio_url: str, sender: str = "BOT") -> str:
    """
    Envia áudio pelo WhatsApp via Twilio.
    
    Args:
        to_e164: Número do destinatário (formato E.164)
        audio_url: URL pública do áudio (deve ser acessível pelo Twilio)
        sender: "BOT" ou "HUMANO" (apenas para log)
    
    Returns:
        SID da mensagem enviada
    """
    print(f"\033[93m[TWILIO][send_audio] 🎵 INICIANDO envio de áudio\033[0m")
    print(f"\033[93m[TWILIO][send_audio]    to_e164: {to_e164}\033[0m")
    print(f"\033[93m[TWILIO][send_audio]    audio_url: {audio_url}\033[0m")
    print(f"\033[93m[TWILIO][send_audio]    sender: {sender}\033[0m")
    
    if not is_configured():
        error_msg = "⚠️ Twilio não configurado. Áudio não enviado."
        print(f"\033[93m[TWILIO][send_audio] {error_msg}\033[0m")
        return ""
    
    if not _client:
        print(f"\033[93m[TWILIO][send_audio] ⚠️ Cliente Twilio não inicializado. Áudio não enviado.\033[0m")
        return ""

    to = _fmt_whatsapp(to_e164)
    from_ = FROM if FROM.startswith("whatsapp:") else f"whatsapp:{FROM}"
    
    print(f"\033[93m[TWILIO][send_audio]    to (formatado): {to}\033[0m")
    print(f"\033[93m[TWILIO][send_audio]    from: {from_}\033[0m")

    try:
        # Twilio requer que o áudio seja uma URL pública acessível
        print(f"\033[93m[TWILIO][send_audio] 📤 Chamando Twilio API...\033[0m")
        
        msg = _client.messages.create(
            to=to,
            from_=from_,
            media_url=[audio_url]  # Twilio aceita lista de URLs de mídia
        )
        
        print(f"\033[93m[TWILIO][send_audio] ✅ Twilio API respondeu: SID={msg.sid}\033[0m")
        print(f"\033[93m[TWILIO][send_audio]    Status: {getattr(msg, 'status', 'N/A')}\033[0m")
        
        if sender.upper() == "BOT":
            print(f"\033[94m[TWILIO][BOT] → {to} | ÁUDIO | SID={msg.sid} | URL={audio_url}\033[0m")
        else:
            print(f"\033[92m[TWILIO][HUMANO] → {to} | ÁUDIO | SID={msg.sid} | URL={audio_url}\033[0m")
        
        return msg.sid
    except Exception as e:
        print(f"\033[91m[TWILIO][send_audio] ❌ ERRO ao enviar áudio: {str(e)}\033[0m")
        import traceback
        traceback.print_exc()
        raise


def send_image(to_e164: str, image_url: str, sender: str = "BOT", body: str = None) -> str:
    """
    Envia imagem pelo WhatsApp via Twilio.
    
    Args:
        to_e164: Número do destinatário (formato E.164)
        image_url: URL pública da imagem (deve ser acessível pelo Twilio)
        sender: "BOT" ou "HUMANO" (apenas para log)
        body: Texto opcional (legenda da imagem)
    
    Returns:
        SID da mensagem enviada
    """
    if not is_configured():
        error_msg = "⚠️ Twilio não configurado. Imagem não enviada."
        print(f"\033[93m[TWILIO][send_image] {error_msg}\033[0m")
        return ""
    
    if not _client:
        print(f"\033[93m[TWILIO][send_image] ⚠️ Cliente Twilio não inicializado. Imagem não enviada.\033[0m")
        return ""

    to = _fmt_whatsapp(to_e164)
    from_ = FROM if FROM.startswith("whatsapp:") else f"whatsapp:{FROM}"
    
    try:
        # Constrói parâmetros da mensagem
        msg_params = {
            "to": to,
            "from_": from_,
            "media_url": [image_url]  # Twilio aceita lista de URLs de mídia
        }
        
        # Adiciona body (legenda) se fornecido
        if body:
            msg_params["body"] = body
        
        msg = _client.messages.create(**msg_params)
        
        if sender.upper() == "BOT":
            print(f"\033[94m[TWILIO][BOT] → {to} | IMAGEM | SID={msg.sid} | URL={image_url}\033[0m")
        else:
            print(f"\033[92m[TWILIO][HUMANO] → {to} | IMAGEM | SID={msg.sid} | URL={image_url}\033[0m")
        
        return msg.sid
    except Exception as e:
        print(f"\033[91m[TWILIO][send_image] ❌ ERRO ao enviar imagem: {str(e)}\033[0m")
        import traceback
        traceback.print_exc()
        raise
