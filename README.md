# MicroSaas Genius · Sistema de Automação de Vendas via WhatsApp

Sistema completo de automação de vendas com **funis inteligentes**, integração **WhatsApp (Twilio)**, **IA conversacional** e gestão de leads. Desenvolvido para automação de vendas do LIFE com múltiplos funis (Funil Longo, Mini Funil BF, Recuperação 50%).

---

## ✨ Principais recursos

* **Funis Automatizados** — Funil Longo, Mini Funil Black Friday, Recuperação 50%
* **IA Conversacional** — Atendimento automático via WhatsApp com tom personalizado
* **Sistema de Estágios** — Rastreamento automático da fase do lead no funil
* **Automações Inteligentes** — Disparo automático de áudios, imagens e textos baseado em gatilhos
* **Integrações** — Eduzz (webhooks de vendas), The Members (assinantes)
* **CRM Completo** — Gestão de contatos, leads, tarefas e kanban
* **Dashboard Analytics** — Métricas de conversão e performance dos funis
* **Handover Inteligente** — Transferência automática IA → humano quando necessário
* **WebSockets** — Atualizações em tempo real no frontend
* **Docker Compose** — Setup completo com um comando

---

## 🧱 Arquitetura

```
api/         # FastAPI + SQLAlchemy + OpenAI + Twilio
  ├── app/
  │   ├── agent_instructions.txt  # Prompt da IA do LIFE
  │   ├── config/
  │   │   └── funnel_config.json  # Configuração dos funis
  │   ├── routers/                # CRM, Analytics, Billing, Integrations
  │   ├── providers/              # Twilio, Meta (WhatsApp)
  │   └── services/              # LLM, Automation Engine, Funnel Detector
  │       ├── automation_engine.py      # Motor de automações
  │       ├── funnel_detector.py        # Detecção de funis
  │       └── funnel_stage_manager.py    # Gerenciamento de estágios
frontend/    # React + Vite + TypeScript
  ├── pages/                      # Chat, Dashboard, Contacts, Kanban, Tasks
  └── components/                 # Layout, MessageBubble, etc.
infra/       # docker-compose.yml + .env
```

---

## 🎯 Funis Implementados

### Funil Longo (Principal)
1. **Lead Frio** — Primeira mensagem, envio de áudio de boas-vindas
2. **Aquecimento** — Detecção de dor, envio de áudio + provas sociais
3. **Aquecido** — Interesse ou objeção detectada
4. **Quente** — Apresentação dos planos (Mensal/Anual)
5. **Fechamento** — Envio de link de checkout
6. **Pós-Venda** — Confirmação de compra via webhook Eduzz
7. **Recuperação** — Carrinho abandonado, oferta especial

### Mini Funil Black Friday
- Campanha promocional com follow-ups automáticos

### Recuperação 50%
- Oferta especial para leads que não completaram a compra

---

## ✅ Requisitos

* Docker Desktop
* Ngrok (ou similar) para expor a API durante desenvolvimento
* Conta Twilio (WhatsApp Business API ou Sandbox)
* Chave OpenAI (GPT-4o-mini recomendado)
* Conta Eduzz (para webhooks de vendas)

---

## ⚙️ Configuração

1. **Copie o `.env` de exemplo:**

```bash
cd infra
cp .env.example .env
```

2. **Edite `infra/.env` (principais variáveis):**

```env
APP_NAME=MicroSaas Genius
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
AGENT_INSTRUCTIONS_FILE=/app/app/agent_instructions.txt
JWT_SECRET=um_segredo_longo_aqui
WHATSAPP_PROVIDER=twilio

TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

PUBLIC_BASE_URL=https://<seu-ngrok>.ngrok-free.app
PUBLIC_FILES_BASE_URL=https://<seu-ngrok>.ngrok-free.app
VITE_API_BASE_URL=http://localhost:8000

# Integrações
EDUZZ_WEBHOOK_SECRET=seu_secret_aqui
THEMEMBERS_API_KEY=sua_chave_aqui

# Opcional: roteia todas as conversas WhatsApp para um usuário fixo
INBOX_OWNER_EMAIL=dev@local.com
```

> **Prompt da IA:** O prompt está em `api/app/agent_instructions.txt`. Você pode editá-lo diretamente ou usar a variável `AGENT_INSTRUCTIONS` no `.env` (com `\n` para quebras de linha).

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

## 🤖 Sistema de Automações

O sistema detecta automaticamente em qual funil e estágio o lead está através de:

1. **Detecção de Gatilhos** — Palavras-chave na mensagem do cliente
2. **Estágio Atual** — Armazenado em `thread.meta.lead_stage` e `thread.lead_stage`
3. **Motor de Automação** — `automation_engine.py` processa triggers e executa ações
4. **Atualização Automática** — Estágio atualizado após cada ação

### Como funciona:

- **Entrada no Funil:** Detecta palavras-chave como "quero saber do life", "quero emagrecer"
- **Avanço de Estágio:** Baseado em respostas do cliente (dor detectada → interesse → planos)
- **Ações Automáticas:** Envio de áudios, imagens, textos conforme configuração
- **Rastreamento:** Cada thread mantém `funnel_id`, `stage_id`, `lead_level` no metadata

---

## 🔌 Endpoints principais

### Autenticação
* `POST /auth/login` → `{ email, password }` → `{ token }`
* `GET /me` → Perfil do usuário autenticado

### Threads e Mensagens
* `GET /threads` → Lista todas as conversas (com metadata de funil)
* `POST /threads` → Cria nova thread
* `PATCH /threads/{id}` → Atualiza thread (incluindo metadata)
* `DELETE /threads/{id}` → Remove thread
* `GET /threads/{id}/messages` → Histórico de mensagens
* `POST /threads/{id}/messages` → Envia mensagem (dispara IA)

### CRM
* `GET /contacts` → Lista de contatos
* `GET /contacts/{id}` → Detalhes do contato
* `POST /contacts/{id}/tags` → Adiciona tags
* `POST /contacts/{id}/notes` → Adiciona notas
* `POST /contacts/{id}/reminders` → Cria lembretes

### Integrações
* `POST /webhooks/eduzz` → Webhook de vendas Eduzz
* `GET /integrations/eduzz/products` → Lista produtos Eduzz
* `POST /integrations/eduzz/sync` → Sincroniza produtos

### Analytics
* `GET /stats` → Estatísticas gerais
* `GET /analytics/funnels` → Métricas dos funis
* `GET /activities` → Atividades recentes

### Webhooks
* `POST /webhooks/twilio` → Recebe mensagens do WhatsApp (Twilio)
* `GET/POST /webhooks/meta` → Webhook Meta/Facebook (alternativo)

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

## 📋 Estrutura de Funis

### Configuração dos Funis

Os funis são configurados em `api/app/config/funnel_config.json` e incluem:

- **Fases** — Etapas do funil com IDs e nomes
- **Triggers** — Palavras-chave que disparam ações
- **Ações** — Áudios, imagens, textos a serem enviados
- **Transições** — Como avançar entre fases

### Gerenciamento de Estágios

O sistema usa três componentes principais:

1. **`funnel_detector.py`** — Detecta qual funil o lead deve entrar
2. **`automation_engine.py`** — Processa triggers e executa ações
3. **`funnel_stage_manager.py`** — Mapeia eventos para estágios

### Metadata da Thread

Cada thread armazena no `meta` (JSON):
```json
{
  "funnel_id": "1",
  "stage_id": "2",
  "lead_stage": "aquecimento",
  "lead_level": "morno",
  "phase": "aquecimento",
  "last_event": "DOR_DETECTADA"
}
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
- Suporte a mídia (imagens, áudios, documentos)
- Visualização do estágio atual do funil

### Dashboard
- Métricas de atendimento
- Gráficos de volume de mensagens
- Estatísticas de uso da IA
- Performance dos funis
- Atividades recentes

### CRM
- Gestão de contatos/leads
- Sistema de tags
- Notas e lembretes
- Lead scoring automático
- Histórico de compras (Eduzz)

### Kanban
- Organização de tarefas
- Drag & drop
- Filtros por status/prioridade
- Vinculação com contatos

### Tasks
- Criação e gestão de tarefas
- Vinculação com contatos
- Lembretes e prazos

---

## 🚀 Próximos passos / Roadmap

* [ ] A/B testing de mensagens nos funis
* [ ] Otimização de conversão por estágio
* [ ] Integração com mais plataformas de pagamento
* [ ] Templates de mensagens personalizáveis
* [ ] Export de dados para planilhas/CRM externo
* [ ] Métricas avançadas e relatórios
* [ ] Multi-tenant (múltiplas empresas)
* [ ] Fine-tuning de modelos por funil

---

## 📄 Licença

Defina a licença desejada (por exemplo, MIT) em `LICENSE`.

---

## 🙋 Suporte

Para dúvidas ou problemas, abra uma issue no repositório.
