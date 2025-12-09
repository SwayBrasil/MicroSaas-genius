# 📚 Documentação Completa - SWAY Plataforma de Atendimento Inteligente

## 🎯 Visão Geral do Projeto

**SWAY** é uma plataforma completa de atendimento automatizado com IA, focada em conversão de leads em clientes através de múltiplos canais. O sistema integra:

- **Atendimento automatizado via WhatsApp** (Twilio/Meta)
- **Agente comercial inteligente** (OpenAI GPT-4)
- **CRM integrado** com gestão de leads e contatos
- **Sistema de funis e automações** para qualificação de leads
- **Integração com plataformas de vendas** (Eduzz → The Members)
- **Dashboard analítico** com métricas de conversão

---

## 🏗️ Arquitetura do Sistema

### Stack Tecnológico

**Backend:**
- **FastAPI** (Python 3.12) - API REST
- **PostgreSQL** - Banco de dados relacional
- **SQLAlchemy** - ORM
- **OpenAI GPT-4** - Agente de IA
- **WebSockets** - Comunicação em tempo real
- **JWT** - Autenticação

**Frontend:**
- **React 18** + **TypeScript**
- **Vite** - Build tool
- **React Router** - Roteamento
- **Axios** - Cliente HTTP
- **WebSockets** - Atualizações em tempo real

**Infraestrutura:**
- **Docker Compose** - Orquestração de containers
- **Nginx/Caddy** (produção) - Reverse proxy

### Estrutura de Diretórios

```
MicroSaas-genius/
├── api/                    # Backend FastAPI
│   ├── app/
│   │   ├── main.py         # Aplicação principal
│   │   ├── models.py       # Modelos SQLAlchemy
│   │   ├── schemas.py      # Schemas Pydantic
│   │   ├── auth.py         # Autenticação JWT
│   │   ├── db.py           # Configuração DB
│   │   ├── agent_instructions.txt  # Prompt do agente
│   │   ├── routers/        # Endpoints organizados
│   │   │   ├── crm.py      # CRM (contatos, tags, notas)
│   │   │   ├── tasks.py    # Tarefas
│   │   │   ├── takeover.py # Handover humano
│   │   │   ├── billing.py  # Produtos e assinaturas
│   │   │   ├── eduzz.py    # Webhook Eduzz
│   │   │   └── integrations.py  # Status de integrações
│   │   ├── providers/      # Integrações externas
│   │   │   ├── twilio.py   # WhatsApp via Twilio
│   │   │   └── meta.py     # WhatsApp Business API
│   │   └── services/       # Lógica de negócio
│   │       ├── llm_service.py        # Serviço de IA
│   │       ├── media_processor.py    # Processamento de mídia
│   │       ├── themembers_service.py # API The Members
│   │       ├── automation_engine.py   # Motor de automações
│   │       ├── funnel_detector.py     # Detecção de funis
│   │       ├── funnel_stage_manager.py # Gestão de etapas
│   │       └── support_detector.py   # Detecção de suporte
│   └── requirements.txt
│
├── frontend/               # Frontend React
│   ├── src/
│   │   ├── pages/         # Páginas principais
│   │   │   ├── Chat.tsx           # Inbox de conversas
│   │   │   ├── Contacts.tsx       # Lista de contatos
│   │   │   ├── ContactDetail.tsx # Detalhes do contato
│   │   │   ├── Dashboard.tsx     # Analytics
│   │   │   ├── Kanban.tsx        # Funil visual
│   │   │   ├── Tasks.tsx          # Tarefas
│   │   │   ├── Profile.tsx        # Perfil do usuário
│   │   │   ├── Products.tsx      # Produtos The Members
│   │   │   ├── Integrations.tsx  # Status de integrações
│   │   │   ├── Automations.tsx   # Configuração de automações
│   │   │   └── Audios.tsx        # Gestão de áudios
│   │   ├── components/    # Componentes reutilizáveis
│   │   │   ├── AppHeader.tsx     # Cabeçalho com navegação
│   │   │   ├── ChatLayout.tsx   # Layout do chat
│   │   │   ├── MessageBubble.tsx # Bolha de mensagem
│   │   │   └── Page.tsx          # Wrapper de página
│   │   ├── hooks/         # React Hooks customizados
│   │   │   ├── useDarkMode.ts   # Tema claro/escuro
│   │   │   └── useLeadScore.ts  # Cálculo de lead score
│   │   ├── api.ts         # Cliente API (Axios)
│   │   ├── auth.tsx       # Context de autenticação
│   │   └── utils/         # Utilitários
│   │       └── leadScore.ts  # Lógica de scoring
│   └── package.json
│
└── infra/                 # Infraestrutura
    ├── docker-compose.yml # Orquestração Docker
    └── .env               # Variáveis de ambiente
```

---

## 🔄 Fluxos Principais do Sistema

### 1. Fluxo de Atendimento via WhatsApp

```
┌─────────────────┐
│  Cliente envia  │
│  mensagem no    │
│  WhatsApp       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Twilio/Meta    │
│  recebe e       │
│  envia webhook  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  POST /webhooks │
│  /twilio        │
└────────┬────────┘
         │
         ├─► Normaliza número de telefone
         ├─► Busca thread existente (ou cria nova)
         ├─► Cria contato automaticamente
         ├─► Salva mensagem do usuário
         │
         ▼
┌─────────────────┐
│  Detecção de    │
│  Funil          │
└────────┬────────┘
         │
         ├─► Detecta funil/etapa automaticamente
         ├─► Atualiza metadata da thread
         │
         ▼
┌─────────────────┐
│  Detecção de    │
│  Suporte        │
└────────┬────────┘
         │
         ├─► Verifica palavras-chave de suporte
         ├─► Se detectado → Ativa takeover humano
         │
         ▼
┌─────────────────┐
│  Motor de       │
│  Automações     │
└────────┬────────┘
         │
         ├─► Processa triggers configurados
         ├─► Executa ações (envio de áudio, template, etc)
         ├─► Atualiza etapa do funil
         │
         ▼
┌─────────────────┐
│  Agente IA      │
│  (OpenAI)       │
└────────┬────────┘
         │
         ├─► Carrega histórico da conversa
         ├─► Envia para GPT-4 com contexto
         ├─► Recebe resposta do agente
         │
         ▼
┌─────────────────┐
│  Processamento  │
│  de Resposta    │
└────────┬────────┘
         │
         ├─► Detecta se deve enviar áudio
         ├─► Detecta se deve usar template
         ├─► Formata resposta final
         │
         ▼
┌─────────────────┐
│  Envio via      │
│  Twilio/Meta    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Salva mensagem │
│  no banco       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Broadcast      │
│  WebSocket      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Frontend       │
│  atualiza em    │
│  tempo real     │
└─────────────────┘
```

### 2. Fluxo de Venda (Eduzz → The Members)

```
┌─────────────────┐
│  Cliente compra │
│  na Eduzz       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Eduzz envia    │
│  webhook        │
│  sale.approved  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  POST /webhook  │
│  /eduzz         │
└────────┬────────┘
         │
         ├─► Valida assinatura HMAC-SHA256
         ├─► Salva evento em sales_events
         │
         ▼
┌─────────────────┐
│  Busca contato  │
│  por email      │
└────────┬────────┘
         │
         ├─► Se não existe → cria contato
         │
         ▼
┌─────────────────┐
│  Verifica The   │
│  Members        │
└────────┬────────┘
         │
         ├─► Busca usuário por email
         ├─► Se não existe → cria usuário + assinatura
         │
         ▼
┌─────────────────┐
│  Atualiza       │
│  Contato        │
└────────┬────────┘
         │
         ├─► Vincula themembers_user_id
         │
         ▼
┌─────────────────┐
│  Cria/Atualiza  │
│  Subscription   │
└────────┬────────┘
         │
         ├─► Salva em subscriptions_external
         ├─► Vincula ao contato
         │
         ▼
┌─────────────────┐
│  Retorna        │
│  sucesso        │
└─────────────────┘
```

### 3. Fluxo de Qualificação de Lead

```
┌─────────────────┐
│  Mensagem       │
│  recebida       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Detecção de    │
│  Funil          │
└────────┬────────┘
         │
         ├─► Analisa conteúdo da mensagem
         ├─► Identifica palavras-chave
         ├─► Detecta origem (anúncio, orgânico, etc)
         │
         ▼
┌─────────────────┐
│  Atribuição de  │
│  Etapa          │
└────────┬────────┘
         │
         ├─► Inicial → Interesse → Qualificação → Proposta → Fechamento
         │
         ▼
┌─────────────────┐
│  Cálculo de     │
│  Lead Score     │
└────────┬────────┘
         │
         ├─► Baseado em:
         │   - Número de mensagens
         │   - Engajamento
         │   - Palavras-chave de interesse
         │   - Etapa do funil
         │
         ▼
┌─────────────────┐
│  Classificação  │
│  de Temperatura │
└────────┬────────┘
         │
         ├─► Quente (score alto)
         ├─► Morno (score médio)
         └─► Frio (score baixo)
```

### 4. Fluxo de Automações

```
┌─────────────────┐
│  Mensagem       │
│  recebida       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Verifica       │
│  Triggers       │
└────────┬────────┘
         │
         ├─► Trigger por etapa do funil
         ├─► Trigger por palavras-chave
         ├─► Trigger por tempo
         │
         ▼
┌─────────────────┐
│  Executa        │
│  Ações          │
└────────┬────────┘
         │
         ├─► Envia áudio pré-gravado
         ├─► Envia template de mensagem
         ├─► Atualiza etapa do funil
         ├─► Cria tarefa de follow-up
         │
         ▼
┌─────────────────┐
│  Pula LLM?      │
└────────┬────────┘
         │
         ├─► Se automação executada → NÃO chama IA
         └─► Se não → Chama IA normalmente
```

---

## 📱 Telas e Funcionalidades

### 1. **Login** (`/login`)

**Função:** Autenticação de usuários

**Funcionalidades:**
- Login com email e senha
- Geração de token JWT
- Redirecionamento para dashboard após login
- Validação de credenciais

**Fluxo:**
1. Usuário insere email e senha
2. POST `/auth/login`
3. Backend valida e retorna token JWT
4. Token salvo no localStorage
5. Redireciona para dashboard

---

### 2. **Chat** (`/` ou `/chat`)

**Função:** Inbox principal de conversas (estilo WhatsApp)

**Funcionalidades:**
- Lista de conversas na sidebar esquerda
- Visualização de mensagens em tempo real
- Envio de mensagens
- Indicador de digitação da IA
- Modo takeover (humano assume conversa)
- Suporte a mídia (imagens, áudios, documentos)
- Busca de conversas
- Filtros por status, origem, temperatura
- Preview da última mensagem
- Badge de status de assinatura (se contato tiver)

**Layout:**
```
┌─────────────┬──────────────────────┐
│  Sidebar    │  Área de Conversa    │
│  (Threads)  │                      │
│             │  ┌────────────────┐  │
│  [Busca]    │  │  Mensagens     │  │
│             │  │  (scrollável)  │  │
│  Thread 1   │  └────────────────┘  │
│  Thread 2   │                      │
│  Thread 3   │  ┌────────────────┐  │
│  ...        │  │  Input + Enviar│  │
│             │  └────────────────┘  │
└─────────────┴──────────────────────┘
```

**Fluxo de Mensagem:**
1. Usuário digita e envia
2. POST `/threads/{id}/messages`
3. Mensagem salva no banco
4. Broadcast via WebSocket
5. IA processa e responde
6. Resposta salva e enviada
7. Atualização em tempo real no frontend

**Recursos Especiais:**
- **Detecção automática de funil:** Identifica origem e etapa
- **Lead scoring:** Calcula score automaticamente
- **Takeover automático:** Detecta pedidos de suporte e transfere para humano
- **Processamento de mídia:** Transcreve áudios, descreve imagens

---

### 3. **Contatos** (`/contacts`)

**Função:** CRM - Gestão de leads e contatos

**Funcionalidades:**
- Lista todos os contatos
- Busca por nome, email, telefone
- Filtros avançados:
  - Por origem (WhatsApp, web, etc)
  - Por temperatura (quente, morno, frio)
  - Por funil
  - Por etapa do funil
  - Por produto
  - Por status de automação
- Ordenação (última interação, nome, etc)
- Visualização de métricas:
  - Total de pedidos
  - Total gasto
  - Ticket médio
  - Produtos mais comprados
- Badge de temperatura do lead
- Link para detalhes do contato

**Colunas da Tabela:**
- Nome
- Email
- Telefone
- Origem
- Temperatura (Quente/Morno/Frio)
- Funil/Etapa
- Última interação
- Ações (ver detalhes)

---

### 4. **Detalhes do Contato** (`/contacts/:threadId`)

**Função:** Visualização completa de um contato/lead

**Seções:**

**A) Dados Básicos:**
- Nome (editável)
- Email (editável)
- Telefone (editável)
- Empresa (editável)

**B) Assinatura:**
- Status (Ativo/Inativo)
- Produto associado
- Data de expiração
- Histórico de assinaturas
- ID The Members

**C) Métricas:**
- Total de pedidos
- Total gasto
- Ticket médio
- Produtos mais comprados

**D) Tags:**
- Adicionar/remover tags personalizadas
- Filtragem por tags

**E) Notas:**
- Notas internas sobre o contato
- Histórico de notas
- Criar nova nota

**F) Lembretes:**
- Criar lembretes de follow-up
- Marcar como concluído
- Visualizar pendentes

**G) Conversa:**
- Link para ver conversa completa
- Histórico de interações

---

### 5. **Dashboard** (`/dashboard`)

**Função:** Analytics e métricas do sistema

**Métricas Principais:**

**Cards de Resumo:**
- Total de conversas (threads)
- Mensagens do usuário
- Mensagens da IA
- Total de mensagens
- Última atividade

**Gráficos:**
- **Mensagens por dia:** Linha temporal de volume
- **Mensagens por hora:** Distribuição ao longo do dia (0-23h)
- **Crescimento de conversas:** Novas threads por dia (últimos 30 dias)
- **Distribuição de leads:** Quente/Morno/Frio
- **Distribuição por origem:** WhatsApp, Web, etc
- **Tempo médio de resposta:** IA response time

**Métricas Calculadas:**
- Taxa de resposta (% de conversas com resposta da IA)
- Tempo médio de resposta da IA (em ms)

---

### 6. **Kanban** (`/kanban`)

**Função:** Visualização do funil em formato Kanban

**Funcionalidades:**
- Colunas por etapa do funil:
  - Inicial
  - Interesse
  - Qualificação
  - Proposta
  - Fechamento
- Cards representam conversas/leads
- Drag & drop entre etapas (manual)
- Filtros:
  - Por funil
  - Por produto
  - Por temperatura
- Visualização de informações do lead no card:
  - Nome
  - Temperatura
  - Score
  - Última interação

**Ações:**
- Mover lead entre etapas manualmente
- Forçar etapa específica
- Ver detalhes do contato
- Abrir conversa

---

### 7. **Tarefas** (`/tasks`)

**Função:** Gestão de tarefas e lembretes

**Funcionalidades:**
- Lista de tarefas
- Criar nova tarefa
- Editar tarefa
- Marcar como concluída
- Deletar tarefa
- Filtrar por status (aberta/concluída)
- Vincular tarefa a contato
- Definir data de vencimento

**Campos:**
- Título
- Descrição/Notas
- Status (open/done)
- Data de vencimento
- Contato vinculado (opcional)

---

### 8. **Produtos** (`/products`)

**Função:** Lista de produtos da The Members

**Funcionalidades:**
- Lista todos os produtos sincronizados
- Informações de cada produto:
  - Título
  - ID externo (The Members)
  - Tipo (recorrente, venda única, vitalício)
  - Status (ativo, inativo)
- Sincronização automática com The Members
- Visualização quando não há produtos

**Uso:**
- Referência para entender quais produtos estão disponíveis
- Verificação de status dos produtos
- Identificação de IDs para configuração

---

### 9. **Integrações** (`/integrations`)

**Função:** Monitoramento e configuração de integrações

**Funcionalidades:**

**Dashboard de Status:**
- Cards de resumo:
  - Total de integrações
  - Integrações ativas
  - Integrações configuradas

**Por Integração:**
- **Eduzz:**
  - Status (Ativo/Inativo)
  - Webhook URL (com botão copiar)
  - Total de eventos processados
  - Último evento
  - Configuração (secret configurado)

- **The Members:**
  - Status
  - Base URL
  - Tokens configurados
  - Produto padrão
  - Total de assinaturas criadas
  - Última assinatura criada

- **Twilio (WhatsApp):**
  - Status
  - Webhook URL
  - Account SID configurado
  - Auth Token configurado
  - Número de origem

- **Meta (WhatsApp Business):**
  - Status
  - Webhook URL
  - Verify Token configurado

**Eventos Recentes:**
- Lista dos últimos 10 eventos
- Filtro por source
- Detalhes: email, pedido, valor, data

---

### 10. **Automações** (`/automations`)

**Função:** Configuração de automações e triggers

**Funcionalidades:**
- Visualização de automações configuradas
- Criar nova automação
- Editar automação existente
- Definir triggers:
  - Por etapa do funil
  - Por palavras-chave
  - Por tempo (delay)
- Definir ações:
  - Enviar áudio
  - Enviar template
  - Atualizar etapa
  - Criar tarefa
- Ativar/desativar automações

**Fluxo de Automação:**
1. Trigger é acionado (ex: lead entra na etapa "Qualificação")
2. Sistema verifica automações ativas para essa etapa
3. Executa ações configuradas
4. Pode pular chamada à IA se ação foi executada

---

### 11. **Áudios** (`/audios`)

**Função:** Gestão de áudios pré-gravados

**Funcionalidades:**
- Lista de áudios disponíveis
- Upload de novos áudios
- Associar áudio a etapa do funil
- Associar áudio a palavras-chave
- Preview de áudio
- Deletar áudio

**Uso:**
- Áudios são enviados automaticamente pela IA quando detecta contexto apropriado
- Exemplo: Áudio explicando planos quando lead pergunta sobre valores

---

### 12. **Perfil** (`/profile`)

**Função:** Configurações do usuário

**Funcionalidades:**
- Visualizar informações do perfil
- Alterar senha
- Configurações de notificações (futuro)
- Logout

---

## 🔌 Integrações Detalhadas

### 1. **Eduzz → The Members**

**Objetivo:** Automatizar criação de assinaturas quando há venda na Eduzz

**Fluxo Completo:**
1. Cliente compra produto na Eduzz
2. Eduzz envia webhook `sale.approved` para `/webhook/eduzz`
3. Sistema valida assinatura HMAC-SHA256
4. Salva evento em `sales_events`
5. Busca contato pelo email do comprador
6. Se não existe, cria contato
7. Verifica se usuário existe na The Members
8. Se não existe, cria usuário + assinatura via API The Members
9. Atualiza contato com `themembers_user_id`
10. Cria/atualiza registro em `subscriptions_external`
11. Retorna sucesso

**Configuração Necessária:**
- `EDUZZ_SECRET` - Secret do webhook Eduzz
- `THEMEMBERS_DEV_TOKEN` - Token de desenvolvimento
- `THEMEMBERS_PLATFORM_TOKEN` - Token de plataforma
- `THEMEMBERS_DEFAULT_PRODUCT_ID` - ID do produto padrão
- `THEMEMBERS_BASE_URL` - URL da API The Members

**Endpoints The Members Usados:**
- `GET /users/show-email/{email}` - Buscar usuário
- `POST /users/create` - Criar usuário + assinatura
- `GET /products/all-products` - Listar produtos

---

### 2. **Twilio (WhatsApp)**

**Objetivo:** Receber e enviar mensagens via WhatsApp

**Fluxo:**
1. Cliente envia mensagem no WhatsApp
2. Twilio recebe e envia webhook para `/webhooks/twilio`
3. Sistema processa mensagem:
   - Normaliza número de telefone
   - Busca/cria thread
   - Salva mensagem
   - Processa mídia (se houver)
4. IA responde automaticamente
5. Resposta enviada via Twilio API

**Configuração:**
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM` - Número de origem
- `ENABLE_TWILIO=true`
- `PUBLIC_BASE_URL` - URL pública para webhook

---

### 3. **Meta (WhatsApp Business API)**

**Objetivo:** Alternativa ao Twilio para WhatsApp

**Similar ao Twilio, mas usando:**
- `META_VERIFY_TOKEN` para validação
- `ENABLE_META=true`
- Endpoint `/webhooks/meta`

---

## 🧠 Sistema de IA (Agente SWAY)

### Prompt do Agente

O agente é configurado em `api/app/agent_instructions.txt` e funciona como:

**Personalidade:**
- Tom humano e empático
- Estilo WhatsApp (frases curtas)
- Máximo 1 emoji por mensagem
- Próxima, motivadora

**Capacidades:**
- Diagnóstico de negócio do cliente
- Explicação da solução SWAY
- Qualificação de leads
- Demonstração de como a IA funcionaria
- Quebra de objeções
- Apresentação de planos e valores

**Limitações:**
- Não negocia preços (transfere para humano)
- Não acessa sistema interno (transfere para humano)
- Não processa reembolsos (transfere para humano)

**Roteamento de Respostas:**
O agente pode retornar diferentes tipos de resposta:
- Texto simples
- Texto + áudio
- Template de mensagem
- JSON estruturado para ações

---

## 📊 Sistema de Funis e Etapas

### Funis Configurados

O sistema detecta automaticamente funis baseado em:
- Origem da conversa (anúncio, orgânico, etc)
- Palavras-chave na primeira mensagem
- Metadata da thread

### Etapas do Funil

1. **Inicial** - Primeiro contato
2. **Interesse** - Demonstrou interesse
3. **Qualificação** - Respondendo perguntas
4. **Proposta** - Apresentando solução
5. **Fechamento** - Pronto para comprar

### Detecção Automática

- Analisa conteúdo das mensagens
- Identifica palavras-chave
- Atualiza etapa automaticamente
- Pode ser forçada manualmente no Kanban

---

## 🎯 Sistema de Lead Scoring

### Cálculo de Score

Baseado em:
- **Número de mensagens:** Mais mensagens = maior engajamento
- **Palavras-chave de interesse:** Detecta intenção de compra
- **Etapa do funil:** Etapas avançadas = score maior
- **Tempo de resposta:** Respostas rápidas = maior interesse
- **Mencionou valores/preços:** Sinal de interesse avançado

### Classificação de Temperatura

- **Quente:** Score alto, etapa avançada, mencionou compra
- **Morno:** Score médio, demonstrou interesse
- **Frio:** Score baixo, pouco engajamento

---

## 🔄 Sistema de Automações

### Triggers Disponíveis

1. **Por Etapa do Funil:**
   - Quando lead entra em etapa específica
   - Ex: "Ao entrar em Qualificação, enviar áudio X"

2. **Por Palavras-chave:**
   - Detecta palavras na mensagem
   - Ex: "Se mencionar 'preço', enviar template de planos"

3. **Por Tempo:**
   - Delay após evento
   - Ex: "2 horas após última mensagem, enviar follow-up"

### Ações Disponíveis

1. **Enviar Áudio:**
   - Áudio pré-gravado
   - Associado a contexto específico

2. **Enviar Template:**
   - Mensagem pré-definida
   - Pode ter variáveis

3. **Atualizar Etapa:**
   - Move lead para próxima etapa
   - Automaticamente

4. **Criar Tarefa:**
   - Tarefa de follow-up
   - Vinculada ao contato

---

## 🗄️ Modelos de Dados Principais

### Thread (Conversa)
- `id` - ID único
- `user_id` - Usuário dono
- `title` - Título da conversa
- `external_user_phone` - Telefone do cliente
- `human_takeover` - Modo humano ativo?
- `origin` - Origem (whatsapp, web, etc)
- `lead_level` - Temperatura (quente/morno/frio)
- `lead_score` - Score numérico
- `lead_stage` - Etapa do funil
- `meta` - JSONB com dados extras (funnel_id, stage_id, etc)

### Message (Mensagem)
- `id` - ID único
- `thread_id` - Conversa
- `role` - user/assistant/system
- `content` - Conteúdo da mensagem
- `is_human` - Enviada por humano?
- `created_at` - Data/hora

### Contact (Contato)
- `id` - ID único
- `thread_id` - Conversa associada (opcional)
- `user_id` - Usuário dono
- `name` - Nome
- `email` - Email
- `phone` - Telefone
- `themembers_user_id` - ID na The Members
- `total_orders` - Total de pedidos
- `total_spent` - Total gasto (centavos)
- `average_ticket` - Ticket médio

### SaleEvent (Evento de Venda)
- `id` - ID único
- `source` - Fonte (eduzz, manual, etc)
- `event` - Tipo de evento
- `order_id` - ID do pedido
- `buyer_email` - Email do comprador
- `value` - Valor (centavos)
- `contact_id` - Contato vinculado
- `themembers_user_id` - ID The Members
- `raw_payload` - Payload completo

### SubscriptionExternal (Assinatura)
- `id` - ID único
- `contact_id` - Contato
- `themembers_user_id` - ID The Members
- `product_external_id` - Produto
- `status` - active/inactive/canceled
- `started_at` - Data de início
- `expires_at` - Data de expiração
- `source` - Origem (eduzz, manual)

### ProductExternal (Produto)
- `id` - ID único
- `external_product_id` - ID na The Members
- `title` - Título
- `type` - Tipo (recurring, one_time, lifetime)
- `status` - active/inactive

---

## 🔐 Segurança

### Autenticação
- JWT tokens
- Tokens armazenados no localStorage
- Validação em todas as rotas protegidas

### Webhooks
- **Eduzz:** Validação HMAC-SHA256
- **Twilio:** Validação de assinatura (opcional)
- **Meta:** Verify token

### CORS
- Configurável via `CORS_ALLOW_ORIGINS`
- Restrito a origens permitidas

---

## 📈 Métricas e Analytics

### Métricas Coletadas

**Conversas:**
- Total de threads
- Novas threads por dia
- Threads por origem

**Mensagens:**
- Total de mensagens
- Mensagens do usuário vs IA
- Mensagens por dia
- Mensagens por hora do dia

**Performance:**
- Tempo médio de resposta da IA
- Taxa de resposta (% de conversas respondidas)

**Leads:**
- Distribuição por temperatura
- Distribuição por etapa do funil
- Distribuição por origem

**Vendas:**
- Total de vendas (sales_events)
- Total de assinaturas criadas
- Conversão de conversas em vendas

---

## 🚀 Deploy e Produção

### Requisitos
- Docker e Docker Compose
- Domínio com SSL (para webhooks)
- Variáveis de ambiente configuradas

### Variáveis Importantes

**Backend:**
- `OPENAI_API_KEY` - Chave OpenAI
- `JWT_SECRET` - Secret para JWT
- `DB_URL` - URL do PostgreSQL
- `PUBLIC_BASE_URL` - URL pública da API
- `EDUZZ_SECRET` - Secret do webhook Eduzz
- `THEMEMBERS_DEV_TOKEN` - Token The Members
- `THEMEMBERS_PLATFORM_TOKEN` - Token The Members
- `TWILIO_ACCOUNT_SID` - Twilio
- `TWILIO_AUTH_TOKEN` - Twilio

**Frontend:**
- `VITE_API_BASE_URL` - URL da API

### Processo de Deploy

1. Configure `.env` em `infra/`
2. Exponha API publicamente (ngrok ou domínio)
3. Configure webhooks nas plataformas externas
4. Execute `docker-compose up`
5. Acesse frontend e faça login

---

## 🎨 Design e UX

### Tema
- Suporte a modo claro e escuro
- Variáveis CSS para cores
- Design moderno e limpo

### Responsividade
- Layout adaptativo para mobile
- Menu hambúrguer em telas pequenas
- Grid flexível

### Componentes Reutilizáveis
- `AppHeader` - Cabeçalho com navegação
- `MessageBubble` - Bolha de mensagem
- `Page` - Wrapper de página
- Cards, botões, inputs estilizados

---

## 📝 Conclusão

O **SWAY** é uma plataforma completa que automatiza o atendimento desde o primeiro contato até a conversão em venda, integrando:

- **Atendimento inteligente** via WhatsApp
- **Qualificação automática** de leads
- **Gestão de funis** visual
- **Automações** configuráveis
- **Integração com vendas** (Eduzz → The Members)
- **Analytics** completo
- **CRM** integrado

Tudo isso em uma interface moderna e intuitiva, com atualizações em tempo real e processamento inteligente de mensagens.



