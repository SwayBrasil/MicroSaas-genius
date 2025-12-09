# app/services/multimedia_parser.py
"""
Parser para processar respostas da LLM que contêm comandos de áudio, imagem e texto.
Converte a resposta em uma lista ordenada de ações.
"""
import re
from typing import List, Dict, Any, Optional

# Regex patterns para detectar comandos
AUDIO_RE = re.compile(r"^\[Áudio enviado:\s*(?P<audio_id>[^\]]+)\]\s*$", re.IGNORECASE)
IMAGE_RE = re.compile(r"^\[Imagem enviada:\s*(?P<img_id>[^\]]+)\]\s*$", re.IGNORECASE)
IMAGES_RE = re.compile(r"^\[Imagens enviadas:\s*(?P<img_ids>[^\]]+)\]\s*$", re.IGNORECASE)


def parse_multimedia_reply(reply: str) -> List[Dict[str, Any]]:
    """
    Converte a resposta da LLM em uma lista de ações ordenadas.
    
    Comandos suportados:
    - [Áudio enviado: audio_id]
    - [Imagem enviada: image_id]
    - [Imagens enviadas: id1, id2, id3]
    - Texto normal (tudo que não começa com [)
    
    Args:
        reply: Resposta completa da LLM
        
    Returns:
        Lista de ações ordenadas:
        [
            {"type": "audio", "audio_id": "..."},
            {"type": "image", "image_id": "..."},
            {"type": "text", "message": "..."},
            ...
        ]
    """
    # Remove tracinhos de formatação de código que a LLM pode adicionar
    import re
    reply = re.sub(r'^```txt\s*\n?', '', reply, flags=re.MULTILINE)
    reply = re.sub(r'^```\s*\n?', '', reply, flags=re.MULTILINE)
    reply = re.sub(r'\n?```\s*$', '', reply, flags=re.MULTILINE)
    reply = reply.strip()
    
    actions: List[Dict[str, Any]] = []
    text_buffer: List[str] = []
    
    def flush_text():
        """Adiciona texto acumulado como ação de texto"""
        nonlocal text_buffer, actions
        if text_buffer:
            msg = "\n".join([line for line in text_buffer]).strip()
            if msg:
                actions.append({"type": "text", "message": msg})
            text_buffer = []
    
    # Processa linha por linha para manter a ordem
    lines = reply.splitlines()
    
    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip("\n\r")
        is_empty = not line.strip()
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        prev_line = lines[i - 1].strip() if i > 0 else ""
        
        # ÁUDIO
        m_audio = AUDIO_RE.match(line)
        if m_audio:
            flush_text()  # Envia texto pendente antes do áudio
            audio_id = m_audio.group("audio_id").strip()
            actions.append({"type": "audio", "audio_id": audio_id})
            continue
        
        # UMA IMAGEM
        m_img = IMAGE_RE.match(line)
        if m_img:
            flush_text()  # Envia texto pendente antes da imagem
            img_id = m_img.group("img_id").strip()
            actions.append({"type": "image", "image_id": img_id})
            continue
        
        # VÁRIAS IMAGENS (carrossel)
        m_imgs = IMAGES_RE.match(line)
        if m_imgs:
            flush_text()  # Envia texto pendente antes das imagens
            img_ids_str = m_imgs.group("img_ids")
            img_ids = [i.strip() for i in img_ids_str.split(",") if i.strip()]
            # Adiciona cada imagem como ação separada (serão enviadas em sequência)
            for img_id in img_ids:
                actions.append({"type": "image", "image_id": img_id})
            continue
        
        # DETECÇÃO DE SEÇÕES DE TEXTO SEPARADAS (mais conservadora)
        # Só separa quando há uma quebra CLARA de seção
        
        if is_empty and text_buffer and next_line:
            # Detecta se a próxima linha é início de uma NOVA SEÇÃO PRINCIPAL
            # Padrões específicos para planos e perguntas finais
            is_new_main_section = (
                # Início de novo plano (com emoji no início)
                (next_line.startswith("✅") and "Plano Mensal" in next_line) or
                (next_line.startswith("🔥") and "Plano Anual" in next_line) or
                # Pergunta final
                any(marker in next_line[:40] for marker in [
                    "Agora me fala, gata", "Agora me fala", "qual plano faz mais sentido"
                ])
            )
            
            if is_new_main_section:
                # Envia o texto atual como mensagem separada
                flush_text()
                continue
        
        # Se não bateu com nenhum comando → é TEXTO
        if not is_empty:
            # Só detecta início de seção se houver linha vazia antes (mais conservador)
            # Não separa linhas consecutivas sem linha em branco
            text_buffer.append(line)
        elif text_buffer:
            # Linha vazia - mantém no buffer (pode ser parte do parágrafo)
            # A separação só acontece se a próxima linha for início de seção principal
            pass
    
    # Envia texto final pendente
    flush_text()
    
    return actions


def validate_actions(actions: List[Dict[str, Any]]) -> tuple[bool, Optional[str]]:
    """
    Valida se as ações têm os campos necessários.
    
    Returns:
        (is_valid, error_message)
    """
    for i, action in enumerate(actions):
        action_type = action.get("type")
        
        if action_type == "audio":
            if "audio_id" not in action:
                return False, f"Ação {i}: áudio sem audio_id"
        elif action_type == "image":
            if "image_id" not in action:
                return False, f"Ação {i}: imagem sem image_id"
        elif action_type == "text":
            if "message" not in action:
                return False, f"Ação {i}: texto sem message"
        else:
            return False, f"Ação {i}: tipo desconhecido '{action_type}'"
    
    return True, None

