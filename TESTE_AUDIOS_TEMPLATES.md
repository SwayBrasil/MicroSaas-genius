# 🧪 Guia de Teste - Áudios e Templates

## ✅ O que foi implementado

### 1. Função para enviar áudios (`api/app/providers/twilio.py`)
- ✅ `send_audio()` - Envia áudio via Twilio usando URL pública

### 2. Carregador de templates (`api/app/services/template_loader.py`)
- ✅ `load_template()` - Carrega templates de texto do `frontend/public/images/templates/`
- ✅ `get_audio_path()` - Mapeia `audio_id` para caminho do arquivo
- ✅ `get_template_by_code()` - Carrega template por código interno

### 3. Processador de respostas (`api/app/services/response_processor.py`)
- ✅ `process_llm_response()` - Processa respostas JSON do LLM
- ✅ Envia áudios quando `response_type: "audio"`
- ✅ Envia templates quando `response_type: "checkout"` ou `"template"`
- ✅ Salva `next_stage` nos metadados da thread

### 4. Modificações no LLM Service (`api/app/services/llm_service.py`)
- ✅ Detecta respostas JSON e retorna como dict quando tem `response_type`

### 5. Atualização do Webhook (`api/app/main.py`)
- ✅ Usa `process_llm_response()` para processar respostas
- ✅ Envia áudios/templates automaticamente

---

## ⚙️ Configuração necessária

### 1. Variável de ambiente para URLs públicas

Adicione no `.env`:

```bash
# URL base para arquivos públicos (áudios, imagens)
PUBLIC_FILES_BASE_URL=http://localhost:3000
# Ou em produção:
# PUBLIC_FILES_BASE_URL=https://seudominio.com
```

### 2. Servir arquivos estáticos

Os áudios precisam estar acessíveis via HTTP. Opções:

**Opção A: Via frontend (Recomendado)**
- O frontend já serve arquivos de `/public/`
- Áudios em `/audios/` ficam acessíveis em `http://localhost:3000/audios/...`

**Opção B: Via backend (Alternativa)**
- Adicionar rota no FastAPI para servir arquivos estáticos
- Exemplo:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="frontend/public"), name="static")
```

### 3. Mapeamento de audio_id

Atualize `api/app/services/template_loader.py` se necessário:

```python
audio_map = {
    "audio2_inconstancia": "/audios/funil-longo/02-dor-generica.opus",
    # Adicione outros mapeamentos conforme necessário
}
```

---

## 🧪 Como testar

### Teste 1: Enviar áudio

1. Envie mensagem que deve gerar `response_type: "audio"`
2. Verifique logs:
   ```
   [TWILIO][BOT] → whatsapp:+... | ÁUDIO | SID=... | URL=...
   ```
3. Verifique se o áudio chegou no WhatsApp

### Teste 2: Enviar template

1. Envie mensagem que deve gerar `response_type: "checkout"`
2. Verifique se o template foi carregado e enviado
3. Verifique logs:
   ```
   [TWILIO][BOT] → whatsapp:+... | SID=... | ... chars
   ```

### Teste 3: Verificar dados no banco

1. Verifique se `next_stage` foi salvo em `threads.meta`
2. Verifique se mensagem foi salva com conteúdo correto

---

## 📝 Formato de resposta esperado do LLM

O prompt deve retornar JSON quando necessário:

```json
{
  "response_type": "audio",
  "audio_id": "audio2_inconstancia",
  "message": "",
  "next_stage": "apresentar_planos"
}
```

ou

```json
{
  "response_type": "checkout",
  "template_code": "life_funil_longo_plano_anual",
  "message": "",
  "next_stage": "aguardando_confirmacao"
}
```

ou texto simples (string) para respostas normais.

---

## 🔍 Troubleshooting

### Áudio não envia
- ✅ Verifique se `PUBLIC_FILES_BASE_URL` está configurado
- ✅ Verifique se o arquivo existe em `frontend/public/audios/...`
- ✅ Verifique se o arquivo é acessível via HTTP (abra no navegador)
- ✅ Verifique logs do Twilio para erros

### Template não carrega
- ✅ Verifique se o arquivo existe em `frontend/public/images/templates/`
- ✅ Verifique se o `template_code` está mapeado em `template_loader.py`
- ✅ Verifique logs para erros de leitura

### JSON não é processado
- ✅ Verifique se a resposta do LLM começa com `{` ou `[`
- ✅ Verifique logs para ver o tipo da resposta
- ✅ Adicione logs em `llm_service.py` se necessário

---

## 📊 Próximos passos

1. **Adicionar campos no Thread:**
   - `funnel_id`, `stage_id`, `product_id` (pode usar `meta` JSON ou adicionar colunas)

2. **Atualizar prompt:**
   - Garantir que retorna JSON quando necessário
   - Mapear `audio_id` corretos

3. **Testar fluxo completo:**
   - Lead entra no funil
   - Recebe áudio 1
   - Responde e recebe áudio 2
   - Avança para etapa de planos
   - Recebe template de checkout

---

**Última atualização:** 2025-01-XX

