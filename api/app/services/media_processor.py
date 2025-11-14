"""
Serviço para processar mídia recebida via WhatsApp:
- Áudio: transcrição com Whisper
- Imagens: descrição com GPT-4 Vision
- Documentos: extração de texto/descrição com GPT-4 Vision
"""
import os
import httpx
import tempfile
from typing import Optional, Dict, Any
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def download_media(url: str, auth: tuple = None) -> bytes:
    """Baixa mídia do Twilio (requer autenticação e segue redirects)"""
    # httpx segue redirects automaticamente, mas vamos garantir
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, max_redirects=10) as http_client:
        # Twilio requer autenticação Basic Auth na URL inicial
        # O redirect vai para uma URL assinada do CDN que não precisa de auth
        try:
            if auth:
                response = await http_client.get(url, auth=auth)
            else:
                # Tenta com credenciais do Twilio se disponíveis
                twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
                twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
                if twilio_sid and twilio_token:
                    # Primeira requisição precisa de auth, redirect não precisa
                    response = await http_client.get(url, auth=(twilio_sid, twilio_token))
                else:
                    response = await http_client.get(url)
            
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            # Se for redirect, tenta seguir manualmente
            if e.response.status_code in (301, 302, 303, 307, 308):
                redirect_url = e.response.headers.get("Location")
                if redirect_url:
                    # URL do redirect não precisa de autenticação
                    response = await http_client.get(redirect_url)
                    response.raise_for_status()
                    return response.content
            raise


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    """
    Transcreve áudio usando Whisper API da OpenAI.
    Retorna o texto transcrito.
    """
    try:
        # Cria arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name
        
        try:
            # Transcreve com Whisper
            with open(tmp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="pt"  # Português
                )
            return transcript.text
        finally:
            # Remove arquivo temporário
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        raise Exception(f"Erro ao transcrever áudio: {str(e)}")


async def describe_image(image_bytes: bytes, filename: str = "image.jpg") -> str:
    """
    Descreve imagem usando GPT-4 Vision.
    Retorna descrição detalhada da imagem.
    """
    try:
        import base64
        
        # Converte para base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Determina o tipo MIME baseado na extensão
        mime_type = "image/jpeg"
        if filename.lower().endswith('.png'):
            mime_type = "image/png"
        elif filename.lower().endswith('.gif'):
            mime_type = "image/gif"
        elif filename.lower().endswith('.webp'):
            mime_type = "image/webp"
        
        # Usa GPT-4 Vision para descrever
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Descreva detalhadamente esta imagem. Inclua todos os elementos visíveis, textos, cores, objetos, pessoas, cenário e qualquer informação relevante. Se for um documento, descreva o conteúdo textual e visual."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"Erro ao descrever imagem: {str(e)}")


async def process_document(document_bytes: bytes, filename: str, mime_type: str) -> str:
    """
    Processa documentos (PDF, DOCX, etc).
    Para PDFs e imagens, usa GPT-4 Vision.
    Para outros formatos, tenta extrair texto.
    """
    # Se for PDF ou imagem, usa GPT-4 Vision
    if mime_type.startswith("image/") or mime_type == "application/pdf":
        return await describe_image(document_bytes, filename)
    
    # Para outros formatos, tenta extrair texto básico
    # (pode ser expandido com bibliotecas específicas)
    try:
        if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # DOCX - requer python-docx (não implementado ainda)
            return "Documento Word recebido. Por favor, descreva o conteúdo ou envie como PDF/imagem."
        elif mime_type == "text/plain":
            # Texto simples
            return document_bytes.decode('utf-8', errors='ignore')
        else:
            return f"Documento recebido ({mime_type}). Por favor, descreva o conteúdo ou envie como PDF/imagem."
    except Exception as e:
        return f"Erro ao processar documento: {str(e)}"


async def process_media(
    media_url: str,
    media_type: str,  # "audio", "image", "document"
    filename: str = None,
    mime_type: str = None
) -> Dict[str, Any]:
    """
    Processa mídia recebida e retorna o texto/descrição.
    
    Args:
        media_url: URL da mídia no Twilio
        media_type: "audio", "image", ou "document"
        filename: Nome do arquivo (opcional)
        mime_type: Tipo MIME (opcional)
    
    Returns:
        Dict com:
        - success: bool
        - content: str (texto transcrito/descrito)
        - error: str (se houver erro)
    """
    try:
        # Baixa a mídia
        media_bytes = await download_media(media_url)
        
        if media_type == "audio":
            content = await transcribe_audio(media_bytes, filename or "audio.ogg")
            return {
                "success": True,
                "content": content,
                "type": "transcription"
            }
        elif media_type == "image":
            content = await describe_image(media_bytes, filename or "image.jpg")
            return {
                "success": True,
                "content": content,
                "type": "description"
            }
        elif media_type == "document":
            content = await process_document(
                media_bytes,
                filename or "document",
                mime_type or "application/octet-stream"
            )
            return {
                "success": True,
                "content": content,
                "type": "extraction"
            }
        else:
            return {
                "success": False,
                "error": f"Tipo de mídia não suportado: {media_type}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

