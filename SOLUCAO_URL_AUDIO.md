# 🔧 Solução: URL Pública para Áudios

## ⚠️ Problema Identificado

O Twilio **não consegue acessar URLs locais** (`localhost:3000`). Ele precisa de uma **URL pública acessível** para baixar os arquivos de áudio.

**Erro no log:**
```
[TWILIO] Erro ao enviar áudio: HTTP 400 error: Unable to create record: Invalid media URL(s)
```

## ✅ Solução

### Opção 1: Usar Ngrok (Recomendado para desenvolvimento)

1. **Configure o ngrok para expor o frontend:**
   ```bash
   ngrok http 3000
   ```

2. **Adicione no `infra/.env`:**
   ```bash
   PUBLIC_FILES_BASE_URL=https://seu-ngrok-url.ngrok-free.app
   ```

3. **Reinicie a API:**
   ```bash
   cd infra && docker-compose restart api
   ```

### Opção 2: Usar PUBLIC_BASE_URL (se já tiver ngrok)

O código já tenta usar `PUBLIC_BASE_URL` (ngrok) automaticamente se `PUBLIC_FILES_BASE_URL` for localhost.

**Verifique se está configurado:**
```bash
cd infra && docker-compose exec api env | grep PUBLIC_BASE_URL
```

Se retornar algo como `https://terrier-eternal-distinctly.ngrok-free.app`, está OK!

### Opção 3: Servir arquivos via backend (Produção)

Para produção, você pode:
1. Servir os arquivos estáticos via FastAPI
2. Ou usar um CDN/S3
3. Ou usar o próprio ngrok em produção

## 🧪 Teste Rápido

1. **Verifique a URL que será usada:**
   ```bash
   cd infra && docker-compose logs api | grep "URL do áudio"
   ```

2. **Teste se a URL é acessível:**
   ```bash
   curl -I https://seu-ngrok-url.ngrok-free.app/audios/funil-longo/02-dor-generica.opus
   ```

3. **Se retornar 200 OK, está funcionando!**

## 📝 Nota Importante

- ✅ O sistema **já detecta JSON corretamente**
- ✅ O sistema **já processa áudios corretamente**
- ⚠️ Só precisa de **URL pública** para o Twilio acessar

---

**Status atual:** Sistema funcionando, só precisa configurar URL pública! 🚀

