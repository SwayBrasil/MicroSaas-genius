# SWAY · Plataforma de Atendimento Inteligente

Plataforma completa de atendimento com **IAs Verticais** especializadas por setor. Sistema full-stack com **FastAPI**, **React (Vite)**, integração **WhatsApp (Twilio)** e agente comercial/consultivo automatizado.

---

## ✨ Principais recursos

* **Agente SWAY Universal** — IA comercial que atende prospects, diagnostica negócios e demonstra a solução
* **IAs Verticais** — Especializadas por setor (clínicas, advocacia, vendas, suporte, etc.)
* **Inbox Omnichannel** — WhatsApp, Webchat, Email em um único lugar
* **Handover Inteligente** — Transferência automática IA → humano quando necessário
* **CRM Leve** — Gestão de contatos, leads, tarefas e kanban
* **Analytics** — Dashboard com métricas de atendimento e conversão
* **Autenticação JWT** — Login seguro com seed: **dev@local.com / 123**
* **Histórico Persistido** — Todas as conversas salvas no Postgres
* **WebSockets** — Atualizações em tempo real no frontend
* **Docker Compose** — Setup completo com um comando

---

## 🧱 Arquitetura

```
api/         # FastAPI + SQLAlchemy + OpenAI + Twilio
  ├── app/
  │   ├── agent_instructions.txt  # Prompt do agente comercial
  │   ├── routers/                # CRM, Profile, Tasks, Takeover
  │   ├── providers/              # Twilio, Meta (WhatsApp)
  │   └── services/               # LLM, Media Processor
frontend/    # React + Vite + TypeScript
  ├── pages/                      # Chat, Dashboard, Contacts, Kanban, Tasks
  └── components/                 # Layout, MessageBubble, etc.
infra/       # docker-compose.yml + .env
```

---

## ✅ Requisitos

* Docker Desktop
* Ngrok (ou similar) para expor a API durante desenvolvimento
* Conta Twilio (WhatsApp Business API ou Sandbox) e chave OpenAI

---

## ⚙️ Configuração

1. Copie o `.env` de exemplo:

```bash
cd infra
cp .env.example .env
```

2. Edite `infra/.env` (principais variáveis):

```env
APP_NAME=SWAY
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
AGENT_INSTRUCTIONS_FILE=/app/app/agent_instructions.txt
JWT_SECRET=um_segredo_longo_aqui
WHATSAPP_PROVIDER=twilio

TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

PUBLIC_BASE_URL=https://<seu-ngrok>.ngrok-free.app
VITE_API_BASE_URL=http://localhost:8000

# Opcional: roteia todas as conversas WhatsApp para um usuário fixo
INBOX_OWNER_EMAIL=dev@local.com
```

> **Prompt do Agente:** O prompt comercial/consultivo está em `api/app/agent_instructions.txt`. Você pode editá-lo diretamente ou usar a variável `AGENT_INSTRUCTIONS` no `.env` (com `\n` para quebras de linha).

---

## ▶️ Subindo o projeto

**1. Exponha a API publicamente (para webhooks do WhatsApp):**

```bash
ngrok http 8000
```

**2. Em outro terminal, na raiz do projeto:**

```bash
docker compose -f infra/docker-compose.yml up --build
```

**Acessos:**
* Frontend: [http://localhost:3000](http://localhost:3000)
* API (docs): [http://localhost:8000/docs](http://localhost:8000/docs)
* Health: [http://localhost:8000/health](http://localhost:8000/health)

**Login padrão:** `dev@local.com` / `123`

---

## 💬 WhatsApp (Twilio)

### Sandbox (Desenvolvimento)

1. No **Twilio Console → Messaging → Try it out → WhatsApp → Sandbox settings**:
   * **When a message comes in**: `POST https://<seu-ngrok>/webhooks/twilio`
   * **Status callback URL**: (opcional)

2. Do seu WhatsApp, envie `join <seu-código>` para o número do Sandbox (geralmente **+1 415 523 8886**).

3. Envie mensagens para o número do Sandbox — elas aparecerão no inbox web.

### WhatsApp Business API (Produção)

Configure o webhook no Twilio Console apontando para:
```
POST https://<seu-dominio>/webhooks/twilio
```

**Teste rápido (curl):**

```bash
curl -X POST "https://<seu-ngrok>/webhooks/twilio" \
  -d "From=whatsapp:+5561984081114" \
  --data-urlencode "Body=olá via curl"
```

---

## 🤖 Agente SWAY Universal

O agente comercial está configurado em `api/app/agent_instructions.txt` e funciona como:

* **Consultor especializado** — Entende o negócio do cliente
* **Pré-vendas** — Explica a solução SWAY e seus benefícios
* **SDR automatizado** — Qualifica leads e identifica oportunidades
* **Demonstração** — Mostra como a IA funcionaria no setor do cliente
* **Handover inteligente** — Transfere para humano quando necessário

**Características:**
- Tom humano e simpático, estilo WhatsApp
- Foco em diagnóstico → solução → próximo passo
- Não negocia preços (transfere para humano)
- Adapta-se a qualquer setor mencionado pelo cliente

---

## 🔌 Endpoints principais

### Autenticação
* `POST /auth/login` → `{ email, password }` → `{ token }`
* `GET /me` → Perfil do usuário autenticado

### Threads e Mensagens
* `GET /threads` → Lista todas as conversas
* `POST /threads` → Cria nova thread
* `DELETE /threads/{id}` → Remove thread
* `GET /threads/{id}/messages` → Histórico de mensagens
* `POST /threads/{id}/messages` → Envia mensagem (dispara IA)

### CRM
* `GET /contacts` → Lista de contatos
* `GET /contacts/{id}` → Detalhes do contato
* `POST /contacts/{id}/tags` → Adiciona tags
* `POST /contacts/{id}/notes` → Adiciona notas
* `POST /contacts/{id}/reminders` → Cria lembretes

### Tasks e Kanban
* `GET /tasks` → Lista tarefas
* `POST /tasks` → Cria tarefa
* `PATCH /tasks/{id}` → Atualiza tarefa

### Takeover (Handover Humano)
* `POST /takeover/{thread_id}/takeover` → Ativa/desativa modo humano
* `POST /takeover/{thread_id}/human-reply` → Resposta manual

### Webhooks
* `POST /webhooks/twilio` → Recebe mensagens do WhatsApp (Twilio)
* `GET/POST /webhooks/meta` → Webhook Meta/Facebook (alternativo)

### Analytics
* `GET /stats` → Estatísticas gerais
* `GET /stats/usage` → Uso de tokens/mensagens
* `GET /activities` → Atividades recentes

### Health
* `GET /health` → Status da API

---

## 🧰 Comandos úteis

```bash
# Rebuild apenas da API (forçar reinstalação de deps)
docker compose -f infra/docker-compose.yml build --no-cache api
docker compose -f infra/docker-compose.yml up

# Logs em tempo real
docker compose -f infra/docker-compose.yml logs -f api
docker compose -f infra/docker-compose.yml logs -f frontend

# Parar tudo
docker compose -f infra/docker-compose.yml down

# Limpar volumes (cuidado: apaga dados)
docker compose -f infra/docker-compose.yml down -v
```

---

## 🛡️ Segurança

* **Nunca** comite `.env` (já ignorado em `.gitignore`)
* Rotacione chaves se já foram expostas
* Em produção:
  - Configure HTTPS real
  - Valide assinaturas do Twilio (`X-Twilio-Signature`)
  - Restrinja CORS adequadamente
  - Use variáveis de ambiente seguras

---

## 📋 Funcionalidades por Módulo

### Chat
- Conversas em tempo real via WebSocket
- Histórico completo de mensagens
- Modo takeover (humano assume)
- Suporte a mídia (imagens, documentos)

### Dashboard
- Métricas de atendimento
- Gráficos de volume de mensagens
- Estatísticas de uso da IA
- Atividades recentes

### CRM
- Gestão de contatos/leads
- Sistema de tags
- Notas e lembretes
- Lead scoring automático

### Kanban
- Organização de tarefas
- Drag & drop
- Filtros por status/prioridade

### Tasks
- Criação e gestão de tarefas
- Vinculação com contatos
- Lembretes e prazos

---

## 🚀 Próximos passos / Roadmap

* [ ] Integração com mais canais (Instagram, Telegram)
* [ ] Templates de mensagens transacionais
* [ ] Export de dados para planilhas/CRM externo
* [ ] Métricas avançadas e relatórios
* [ ] API pública para integrações
* [ ] Multi-tenant (múltiplas empresas)
* [ ] A/B testing de prompts
* [ ] Fine-tuning de modelos por setor

---

## 📄 Licença

Defina a licença desejada (por exemplo, MIT) em `LICENSE`.

---

## 🙋 Suporte

Para dúvidas ou problemas, abra uma issue no repositório.
