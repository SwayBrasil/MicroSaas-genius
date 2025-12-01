# 🔍 DEBUG: ÁUDIOS NÃO APARECEM NO WHATSAPP

## Problema Identificado

Os áudios estão sendo registrados no banco como mensagens de texto `[Áudio enviado: ...]` mas **não estão sendo enviados via Twilio** ou **não estão acessíveis pelo Twilio**.

---

## ✅ Correções Implementadas

### 1. **Tratamento de Erro Melhorado**
- Agora captura e loga erros ao enviar áudios
- Mostra traceback completo para debug
- Continua o fluxo mesmo se áudio falhar

### 2. **URL do Áudio Corrigida**
- Usa `PUBLIC_BASE_URL` (ngrok) como prioridade
- Constrói URL correta: `{PUBLIC_BASE_URL}/audios/{path}`
- Remove barras duplicadas

### 3. **Logs Detalhados**
- Mostra URL completa que está sendo usada
- Mostra base URL configurada
- Avisa se `PUBLIC_BASE_URL` não está configurado

---

## 🔧 COMO VERIFICAR SE ESTÁ FUNCIONANDO

### 1. Verifique os logs do backend

Quando enviar "quero saber do life", você deve ver:

```
[AUTOMATION] 🎵 Enviando áudio 1:
[AUTOMATION]    URL: https://abc123.ngrok-free.app/audios/funil-longo/01-boas-vindas-qualificacao.opus
[AUTOMATION]    Path: /audios/funil-longo/01-boas-vindas-qualificacao.opus
[AUTOMATION]    Base: https://abc123.ngrok-free.app
[TWILIO][BOT] → whatsapp:+5561... | ÁUDIO | SID=SM... | URL=...
```

### 2. Verifique se PUBLIC_BASE_URL está configurado

No arquivo `infra/.env`:

```env
PUBLIC_BASE_URL=https://seu-ngrok.ngrok-free.app
```

**⚠️ IMPORTANTE:** Deve ser a URL do **ngrok** (não localhost), pois o Twilio precisa acessar de fora.

### 3. Teste a URL manualmente

Abra no navegador:
```
https://seu-ngrok.ngrok-free.app/audios/funil-longo/01-boas-vindas-qualificacao.opus
```

**Deve:**
- ✅ Baixar o arquivo de áudio
- ✅ Não dar erro 404
- ✅ Não dar erro de CORS

### 4. Verifique os logs do Twilio

Se houver erro, você verá:
```
[TWILIO] Erro ao enviar áudio: ...
```

---

## 🐛 POSSÍVEIS PROBLEMAS

### Problema 1: PUBLIC_BASE_URL não configurado

**Sintoma:** Logs mostram `localhost:8000`

**Solução:**
```bash
# No infra/.env
PUBLIC_BASE_URL=https://seu-ngrok.ngrok-free.app
```

### Problema 2: URL não acessível

**Sintoma:** Erro 404 ou timeout no Twilio

**Solução:**
1. Verifique se o ngrok está rodando
2. Teste a URL no navegador
3. Verifique se o endpoint `/audios/{path}` está funcionando

### Problema 3: Arquivo não encontrado

**Sintoma:** Log mostra `[SERVE_AUDIO] ❌ Arquivo não encontrado`

**Solução:**
1. Verifique se o arquivo existe em `frontend/public/audios/funil-longo/01-boas-vindas-qualificacao.opus`
2. Verifique se o volume está montado no Docker

### Problema 4: CORS ou permissão

**Sintoma:** Twilio não consegue acessar

**Solução:**
- O endpoint já tem `Access-Control-Allow-Origin: *`
- Verifique se o ngrok não está bloqueando

---

## 📝 PRÓXIMOS PASSOS PARA DEBUG

1. **Verifique os logs do backend** quando enviar mensagem
2. **Copie a URL** que aparece nos logs
3. **Teste a URL** no navegador
4. **Verifique se o Twilio recebeu** a requisição (logs do Twilio)

Se ainda não funcionar, envie os logs completos para análise.

