# 🧪 Teste Rápido - Áudios e Templates

## ✅ Status dos Containers

- ✅ **API**: Rodando em `http://localhost:8000` (healthy)
- ✅ **Frontend**: Rodando em `http://localhost:3000` (healthy)
- ✅ **Database**: PostgreSQL rodando (healthy)

## ✅ Verificações Realizadas

1. ✅ API respondendo (`/health` OK)
2. ✅ Áudios acessíveis via HTTP (`/audios/funil-longo/01-boas-vindas-qualificacao.opus`)
3. ✅ Templates acessíveis via HTTP (`/images/templates/fechamento-anual.txt`)
4. ✅ Módulos Python importando corretamente

## 🧪 Como Testar

### 1. Teste de Áudio

Envie uma mensagem no WhatsApp que deve gerar `response_type: "audio"`:

**Exemplo de mensagem:**
```
Quero emagrecer e minha barriga me incomoda
```

**Resposta esperada do LLM:**
```json
{
  "response_type": "audio",
  "audio_id": "audio2_barriga_inchaco",
  "message": "",
  "next_stage": "apresentar_planos"
}
```

**O que deve acontecer:**
1. Sistema detecta JSON com `response_type: "audio"`
2. Busca caminho do áudio: `/audios/funil-longo/02-dor-generica.opus`
3. Converte para URL: `http://localhost:3000/audios/funil-longo/02-dor-generica.opus`
4. Envia via Twilio usando `send_audio()`
5. Salva mensagem no banco com `[Áudio enviado: audio2_barriga_inchaco]`

### 2. Teste de Template

Envie uma mensagem que deve gerar `response_type: "checkout"`:

**Exemplo de mensagem:**
```
Quero o plano anual
```

**Resposta esperada do LLM:**
```json
{
  "response_type": "checkout",
  "template_code": "life_funil_longo_plano_anual",
  "message": "",
  "next_stage": "aguardando_confirmacao_quebra_objecao"
}
```

**O que deve acontecer:**
1. Sistema detecta JSON com `response_type: "checkout"`
2. Busca template: `fechamento-anual.txt`
3. Carrega conteúdo do arquivo
4. Envia via Twilio usando `send_text()`
5. Salva mensagem no banco com o conteúdo do template

### 3. Verificar Logs

```bash
# Ver logs da API em tempo real
cd infra && docker-compose logs -f api

# Ver logs do frontend
cd infra && docker-compose logs -f frontend

# Ver logs do Twilio (envios)
cd infra && docker-compose logs api | grep TWILIO
```

## 🔍 Troubleshooting

### Áudio não envia

1. Verifique se `PUBLIC_FILES_BASE_URL` está no `.env`:
   ```bash
   PUBLIC_FILES_BASE_URL=http://localhost:3000
   ```

2. Verifique se o arquivo existe:
   ```bash
   curl -I http://localhost:3000/audios/funil-longo/02-dor-generica.opus
   ```

3. Verifique logs:
   ```bash
   docker-compose logs api | grep -i audio
   ```

### Template não carrega

1. Verifique se o arquivo existe:
   ```bash
   curl http://localhost:3000/images/templates/fechamento-anual.txt
   ```

2. Verifique logs:
   ```bash
   docker-compose logs api | grep -i template
   ```

### JSON não é processado

1. Verifique se a resposta do LLM é JSON válido:
   ```bash
   docker-compose logs api | grep "LLM reply generated"
   ```

2. Verifique se começa com `{`:
   - Se sim, deve ser processado como dict
   - Se não, será enviado como texto normal

## 📊 Próximos Passos

1. **Testar fluxo completo:**
   - Lead entra → recebe áudio 1
   - Responde sobre dor → recebe áudio 2
   - Avança para planos → recebe template

2. **Verificar dados no banco:**
   - `threads.meta` deve ter `next_stage`
   - `messages` deve ter conteúdo correto

3. **Monitorar logs:**
   - Verificar se áudios/templates estão sendo enviados
   - Verificar se há erros

---

**Status:** ✅ Pronto para testar!

