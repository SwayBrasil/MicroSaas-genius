# 🔧 Como Configurar Ngrok para Áudios

## ⚠️ Problema Atual

O Twilio precisa acessar os arquivos de áudio via URL pública. O ngrok atual está expondo apenas a **API (porta 8000)**, mas os áudios estão no **frontend (porta 3000)**.

## ✅ Solução: Expor Frontend no Ngrok

### Opção 1: Ngrok separado para Frontend (Recomendado)

1. **Abra um novo terminal e rode:**
   ```bash
   ngrok http 3000
   ```

2. **Copie a URL HTTPS gerada** (ex: `https://abc123.ngrok-free.app`)

3. **Adicione no `infra/.env`:**
   ```bash
   PUBLIC_FILES_BASE_URL=https://abc123.ngrok-free.app
   ```

4. **Reinicie a API:**
   ```bash
   cd infra && docker-compose restart api
   ```

### Opção 2: Usar o mesmo ngrok com rota

Se você tiver ngrok configurado com rotas, pode configurar:
- API: `https://seu-ngrok.com/api` → porta 8000
- Frontend: `https://seu-ngrok.com` → porta 3000

E configurar:
```bash
PUBLIC_FILES_BASE_URL=https://seu-ngrok.com
```

### Opção 3: Servir arquivos via API (Alternativa)

Você pode servir os arquivos estáticos via FastAPI também. Mas a opção 1 é mais simples.

## 🧪 Teste

1. **Verifique se o arquivo é acessível:**
   ```bash
   curl -I https://seu-ngrok-frontend.ngrok-free.app/audios/funil-longo/02-dor-generica.opus
   ```

2. **Deve retornar `HTTP/2 200`**

3. **Envie uma mensagem de teste e verifique os logs:**
   ```bash
   cd infra && ./monitor-logs.sh
   ```

## 📊 Logs Esperados

Quando funcionar, você verá:
```
[LLM_SERVICE] ✅ JSON detectado e parseado: {'response_type': 'audio', ...}
[RESPONSE_PROCESSOR] 🎵 URL final do áudio: https://seu-ngrok.ngrok-free.app/audios/...
[TWILIO][BOT] → whatsapp:+... | ÁUDIO | SID=...
```

---

**Status:** Aguardando configuração do ngrok para frontend! 🚀

