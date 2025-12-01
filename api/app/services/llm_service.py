# api/app/services/llm_service.py
import os
import asyncio
import math
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

from openai import OpenAI

# Importa funções de consulta ao WooCommerce
from .wc_data import (
    lookup_product,
    search_products,
    get_product_price,
    get_product_attributes,
    get_product_variations,
    get_product_description,
    build_product_link,
)

# -----------------------------
# Config
# -----------------------------
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("OPENAI_API_KEY")

# Onde ler o prompt:
# 1) AGENT_INSTRUCTIONS (string no .env, usando \n)
# 2) AGENT_INSTRUCTIONS_FILE (caminho para arquivo com o prompt multiline)
#    default aponta para o caminho dentro do container
DEFAULT_PROMPT_FILE = "/app/app/agent_instructions.txt"

# Robustez
REQUEST_TIMEOUT = float(os.getenv("OPENAI_REQUEST_TIMEOUT", "30"))  # segundos
MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
RETRY_BASE = float(os.getenv("OPENAI_RETRY_BASE", "0.6"))  # backoff exponencial
MAX_HISTORY = int(os.getenv("OPENAI_MAX_HISTORY", "20"))   # msgs (user/assistant/system)

def _load_agent_instructions() -> str:
    s = os.getenv("AGENT_INSTRUCTIONS", "") or ""
    path = os.getenv("AGENT_INSTRUCTIONS_FILE") or DEFAULT_PROMPT_FILE

    # Se não veio pelo .env, tenta o arquivo
    if not s and path and Path(path).exists():
        try:
            s = Path(path).read_text(encoding="utf-8")
        except Exception:
            s = ""

    # Permite usar \n no .env (opção B)
    s = s.replace("\\n", "\n").strip()

    # Fallback seguro
    if not s:
        s = "Você é uma assistente útil, cordial e objetiva. Responda em português do Brasil."
    return s


AGENT_INSTRUCTIONS = _load_agent_instructions()

# Cliente OpenAI
client = OpenAI(api_key=API_KEY)


# -----------------------------
# Utilidades
# -----------------------------
def _coerce_history(thread_history: Optional[List[Dict[str, str]]],
                    max_history: int = MAX_HISTORY) -> List[Dict[str, str]]:
    """
    Garante formato esperado e limita a N mensagens mais recentes
    para não estourar a janela de contexto.
    """
    if not thread_history:
        return []

    norm: List[Dict[str, str]] = []
    for m in thread_history:
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").strip()
        if not role or not content:
            continue
        # Apenas "user", "assistant" e "system" são relevantes para histórico
        if role not in ("user", "assistant", "system"):
            continue
        norm.append({"role": role, "content": content})

    if max_history and len(norm) > max_history:
        norm = norm[-max_history:]
    return norm


# Definições das funções disponíveis para a IA
FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_product",
            "description": "Busca um produto específico por nome ou slug. Use quando o cliente mencionar um produto específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nome ou slug do produto (ex: 'Raspadinhas Promocionais' ou 'raspadinhas-promocionais')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Busca múltiplos produtos por termo. Use quando o cliente mencionar um tipo de produto sem especificar exatamente qual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca (ex: 'cartão de visita', 'adesivo', 'banner')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de resultados (padrão: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_price",
            "description": "Obtém o preço de um produto, considerando variações se for produto variável. IMPORTANTE: SEMPRE use 'lookup_product' ou 'search_products' PRIMEIRO para verificar se o produto existe antes de chamar esta função. Se o produto não existir ou a variação não for encontrada, a função retornará um erro. NUNCA invente preços - sempre verifique se o produto existe no catálogo antes de informar preço ao cliente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_slug": {
                        "type": "string",
                        "description": "Slug do produto (ex: 'raspadinhas-promocionais'). DEVE ser um slug válido encontrado através de 'lookup_product' ou 'search_products'."
                    },
                    "attributes": {
                        "type": "object",
                        "description": "Atributos do produto (ex: {'pa_tamanho': '90x50mm', 'pa_quantidade': '1000'}). Use 'get_product_attributes' para verificar quais atributos são válidos antes de usar.",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["product_slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_attributes",
            "description": "Obtém os atributos disponíveis para um produto (tamanho, material, quantidade, etc.). Use para verificar quais opções existem. IMPORTANTE: Se o cliente já selecionou alguns atributos (ex: tamanho 200x90mm), passe esses atributos em 'selected_attributes' para obter APENAS as opções válidas para os atributos restantes. Isso evita mostrar opções que não são compatíveis com a escolha anterior.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_slug": {
                        "type": "string",
                        "description": "Slug do produto"
                    },
                    "selected_attributes": {
                        "type": "object",
                        "description": "Atributos já selecionados pelo cliente (ex: {'pa_tamanho': '200x90mm'}). Quando fornecido, retorna apenas as opções válidas para os atributos restantes, baseado nas variações disponíveis.",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["product_slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_description",
            "description": "Obtém a descrição completa de um produto. Use quando precisar de mais detalhes sobre o produto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_slug": {
                        "type": "string",
                        "description": "Slug do produto"
                    }
                },
                "required": ["product_slug"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "build_product_link",
            "description": "Constrói o link completo para um produto com atributos pré-selecionados, validando se a combinação existe nas variações. IMPORTANTE: Esta função valida se a combinação de atributos é válida consultando as variações do produto. Retorna um dicionário com 'link' (URL completa), 'type' (variation/manual/base), e informações sobre a combinação. Use quando for enviar o link ao cliente. SEMPRE use 'get_product_attributes' primeiro para obter os slugs corretos dos atributos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_slug": {
                        "type": "string",
                        "description": "Slug do produto (ex: 'etiquetas-bolinha-adesivo-papel'). DEVE ser um slug válido encontrado através de 'lookup_product' ou 'search_products'."
                    },
                    "attributes": {
                        "type": "object",
                        "description": "Atributos para incluir no link (ex: {'pa_tamanho': '40x40mm', 'pa_quantidade': '1000', 'pa_acabamento': 'etiqueta-bolinha'}). Use 'get_product_attributes' para verificar quais atributos são válidos e seus slugs corretos antes de usar.",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["product_slug"]
            }
        }
    }
]


def _execute_function(function_name: str, arguments: Dict[str, Any]) -> Any:
    """Executa uma função chamada pela IA"""
    try:
        if function_name == "lookup_product":
            return lookup_product(arguments.get("query", ""))
        elif function_name == "search_products":
            return search_products(arguments.get("query", ""), arguments.get("limit", 10))
        elif function_name == "get_product_price":
            return get_product_price(
                arguments.get("product_slug", ""),
                arguments.get("attributes")
            )
        elif function_name == "get_product_attributes":
            return get_product_attributes(
                arguments.get("product_slug", ""),
                arguments.get("selected_attributes")
            )
        elif function_name == "get_product_description":
            return get_product_description(arguments.get("product_slug", ""))
        elif function_name == "build_product_link":
            return build_product_link(
                arguments.get("product_slug", ""),
                arguments.get("attributes")
            )
        else:
            return {"error": f"Função desconhecida: {function_name}"}
    except Exception as e:
        return {"error": str(e)}


async def _call_openai_with_retries(messages: List[Dict[str, Any]], use_functions: bool = True) -> str:
    """
    Chamada ao OpenAI com retries, backoff exponencial e function calling.
    Executa a chamada síncrona em thread separada para não bloquear o loop.
    """
    max_function_iterations = 5  # Limite de iterações de function calling
    function_iterations = 0
    attempt = 0

    while True:
        attempt += 1
        last_err: Optional[BaseException] = None
        
        try:
            def _sync_call() -> Any:
                kwargs = {
                    "model": MODEL,
                    "messages": messages,
                    "timeout": REQUEST_TIMEOUT,
                }
                
                if use_functions and function_iterations < max_function_iterations:
                    kwargs["tools"] = FUNCTIONS
                    kwargs["tool_choice"] = "auto"
                
                return client.chat.completions.create(**kwargs)

            resp = await asyncio.to_thread(_sync_call)
            message = resp.choices[0].message
            
            # Verifica se há function calls
            if message.tool_calls and function_iterations < max_function_iterations:
                function_iterations += 1
                attempt = 0  # Reseta contador de retries para nova chamada
                
                # Adiciona a mensagem do assistente com tool calls
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                })
                
                # Executa as funções
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except:
                        arguments = {}
                    
                    result = _execute_function(function_name, arguments)
                    
                    # Adiciona resultado como tool message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                
                # Chama novamente com os resultados
                continue
            
            # Sem function calls ou limite atingido, retorna resposta final
            content = (message.content or "").strip()
            if not content and message.tool_calls:
                content = "Desculpe, não consegui obter as informações solicitadas. Pode reformular sua pergunta?"
            
            # Tenta extrair JSON do conteúdo (pode ter texto antes/depois)
            # A IA às vezes retorna texto + JSON, precisamos extrair só o JSON
            import re
            
            # Padrão melhorado: procura por { ... } que contenha "response_type"
            # Usa lookahead para garantir que tem response_type
            json_pattern = r'\{[^{}]*"response_type"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, content, re.DOTALL | re.IGNORECASE)
            
            # Se não encontrou com o padrão específico, tenta padrão genérico
            if not json_matches:
                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                json_matches = re.findall(json_pattern, content, re.DOTALL)
            
            for json_str in json_matches:
                try:
                    parsed = json.loads(json_str)
                    # Se for um objeto com response_type, retorna como dict para processamento especial
                    if isinstance(parsed, dict) and "response_type" in parsed:
                        # Log para debug
                        print(f"[LLM_SERVICE] ✅ JSON detectado e parseado: {parsed}")
                        return parsed
                except json.JSONDecodeError as e:
                    print(f"[LLM_SERVICE] ⚠️ Erro ao parsear JSON: {e}, conteúdo: {json_str[:100]}")
                    continue  # Tenta próximo match
            
            # Fallback: tenta parsear o conteúdo inteiro se começar com { ou [
            if content.startswith("{") or content.startswith("["):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict) and "response_type" in parsed:
                        print(f"[LLM_SERVICE] JSON detectado (início): {parsed}")
                        return parsed
                except json.JSONDecodeError:
                    pass  # Não é JSON válido, retorna como string
            
            return content
            
        except Exception as e:
            last_err = e
            if attempt >= MAX_RETRIES:
                break
            # Backoff exponencial com jitter leve
            delay = (RETRY_BASE ** attempt) + (attempt * 0.05)
            await asyncio.sleep(delay)

    # Fallback amigável
    return "Desculpe, tive um problema para gerar a resposta agora. Pode tentar novamente?"


# -----------------------------
# LLM
# -----------------------------
async def run_llm(
    message: str,
    thread_history: Optional[List[Dict[str, str]]] = None,
    takeover: bool = False,
) -> Optional[str]:
    """
    Gera uma resposta da LLM usando:
      - system prompt carregado do .env/arquivo
      - histórico (limite configurável)
      - mensagem do usuário

    Se `takeover=True`, não gera resposta (modo humano assumiu) e retorna None.
    """
    # 🔒 Bloqueio de takeover: nunca responder se humano assumiu
    if takeover:
        return None

    # Monta a lista de mensagens no formato da API
    messages: List[Dict[str, str]] = []
    
    # Monta system prompt com instruções do agente
    system_content = AGENT_INSTRUCTIONS
    if system_content:
        messages.append({"role": "system", "content": system_content})

    history = _coerce_history(thread_history, max_history=MAX_HISTORY)
    messages.extend(history)

    user_msg = (message or "").strip()
    messages.append({"role": "user", "content": user_msg})

    # Chamar OpenAI com robustez (timeout + retries + function calling)
    content = await _call_openai_with_retries(messages, use_functions=True)
    return content
