# ✅ Checklist de Telas e Funcionalidades

## 📊 Status Atual vs. Planejado

### 🔄 TELAS EXISTENTES (Atualizações Necessárias)

#### ✅ Chat (`/chat`)
**Status:** ✅ **Parcialmente implementado**

- ✅ Mostrar automação/status de automação
- ✅ Modal de automação (visualização)
- ⚠️ **FALTA:** Mostrar funil/etapa/produto explicitamente na interface
- ⚠️ **FALTA:** Badge ou indicador visual do funil atual e etapa
- ✅ Sistema de takeover funcionando

**O que precisa ser adicionado:**
- Badge mostrando funil atual (ex: "Funil Longo - Etapa 3")
- Indicador de produto vinculado
- Status de automação mais visível (pausado/ativo/concluído)

---

#### ⚠️ Contacts (`/contacts`)
**Status:** ⚠️ **Parcialmente implementado**

- ✅ Lista de contatos funcionando
- ✅ Filtros por origem (`origin`)
- ✅ Campos de funil/etapa/produto já existem no código (`funnel_id`, `stage_id`, `product_id`)
- ⚠️ **FALTA:** Filtros por funil/etapa/produto na UI
- ⚠️ **FALTA:** Coluna de status de automação visível
- ⚠️ **FALTA:** Badges visuais para funil/etapa

**O que precisa ser adicionado:**
- Filtros dropdown: Funil, Etapa, Produto, Status Automação
- Colunas na tabela: Funil, Etapa, Produto, Status
- Chips/badges visuais para identificação rápida

---

#### ⚠️ ContactDetail (`/contacts/:threadId`)
**Status:** ⚠️ **Parcialmente implementado**

- ✅ Informações básicas do contato
- ✅ Métricas (pedidos, gasto, ticket médio)
- ✅ Tags, notas, lembretes
- ❌ **FALTA:** Linha do tempo (timeline) de eventos
- ❌ **FALTA:** Integrações (The Members, Eduzz)
- ❌ **FALTA:** Histórico de ações do funil

**O que precisa ser adicionado:**
- Timeline com eventos do funil (quando entrou, etapas percorridas)
- Seção de integrações mostrando dados do The Members
- Histórico de compras/transações da Eduzz
- Eventos de webhook (quando foi disparado)

---

#### ⚠️ Kanban (`/kanban`)
**Status:** ⚠️ **Parcialmente implementado**

- ✅ Colunas por nível de lead (frio/morno/quente)
- ✅ Mostra funil/etapa/produto nos cards (mas só como texto pequeno)
- ❌ **FALTA:** Virar funil real (colunas = etapas do funil)
- ❌ **FALTA:** Filtro de funil/produto
- ❌ **FALTA:** Drag & drop entre etapas do funil

**O que precisa ser mudado:**
- **REFATORAR:** Colunas devem ser etapas do funil selecionado, não níveis de lead
- Adicionar seletor de funil no topo
- Cards devem ser arrastáveis entre etapas (mudar `stage_id`)
- Filtro por produto

---

#### ⚠️ Tasks (`/tasks`)
**Status:** ⚠️ **Parcialmente implementado**

- ✅ Lista de tarefas
- ✅ Criação/edição básica
- ❌ **FALTA:** Vincular a contatos
- ❌ **FALTA:** Campo de origem (manual/automação)
- ❌ **FALTA:** Indicador visual de origem

**O que precisa ser adicionado:**
- Campo `contact_id` ou `thread_id` na tarefa
- Campo `origin: "manual" | "automation"`
- Filtro por origem
- Link para o contato na tarefa

---

#### ⚠️ Dashboard (`/dashboard`)
**Status:** ⚠️ **Parcialmente implementado**

- ✅ Métricas básicas (threads, mensagens)
- ✅ Gráficos de volume
- ❌ **FALTA:** Métricas de funil (taxa de conversão por etapa)
- ❌ **FALTA:** Métricas de integrações (The Members, Eduzz)
- ❌ **FALTA:** Funil de conversão visual
- ❌ **FALTA:** Taxa de abandono por etapa

**O que precisa ser adicionado:**
- Funil de conversão por etapa
- Taxa de conversão entre etapas
- Métricas de integração (compras, assinaturas)
- Tempo médio em cada etapa

---

#### ⚠️ Profile (`/profile`)
**Status:** ✅ **Básico implementado**

- ✅ Informações do usuário
- ⚠️ **FALTA:** Status de integrações (nice to have)
- ❌ **FALTA:** Testes de conexão com APIs externas

**O que precisa ser adicionado (nice to have):**
- Seção "Integrações" mostrando status de conexões
- Botão para testar conexões (Eduzz, The Members)
- Indicadores de status (conectado/desconectado/erro)

---

### 🆕 TELAS NOVAS (A Criar)

#### ✅ `/automations`
**Status:** ✅ **JÁ EXISTE!**

- ✅ Lista de automações/funis
- ✅ Visualização de etapas
- ⚠️ **FALTA:** Editor completo (criar/editar funis)
- ⚠️ **FALTA:** Configurar gatilhos e ações na UI

**O que precisa ser melhorado:**
- Editor visual para criar/editar funis
- Configuração de gatilhos (condições)
- Configuração de ações (o que fazer quando disparar)
- Preview do fluxo

---

#### ✅ `/audios`
**Status:** ✅ **JÁ EXISTE!**

- ✅ Biblioteca de áudios
- ✅ Filtros por funil
- ✅ Visualização de informações
- ✅ **COMPLETO** - Não precisa de mais nada

---

#### ❌ `/products`
**Status:** ❌ **NÃO EXISTE**

**O que precisa ser criado:**
- Lista de produtos mapeados
- Mapeamento: Eduzz ID ↔ The Members ID ↔ Sway ID
- Campos: nome, preço, descrição, links de compra
- Edição/criação de produtos
- Busca e filtros

**Backend já tem:**
- `api/app/services/wc_data.py` - Busca de produtos do WooCommerce
- Estrutura para mapear produtos

---

#### ❌ `/integrations`
**Status:** ❌ **NÃO EXISTE**

**O que precisa ser criado:**
- Configuração de tokens (Eduzz API, The Members API)
- Status de conexão
- Botões para testar conexões
- Histórico de sincronizações
- Configuração de webhooks

**Backend já tem:**
- Webhooks configurados (Eduzz, The Members podem ser adicionados)
- Estrutura para integrações

---

#### ❌ `/events-log`
**Status:** ❌ **NÃO EXISTE** (Opcional, mas útil)

**O que precisa ser criado:**
- Histórico de webhooks recebidos
- Eventos de automação disparados
- Filtros por tipo de evento, data, funil
- Visualização de payload do webhook
- Status (sucesso/erro)

**Backend já tem:**
- Webhooks funcionando (`/webhooks/twilio`, `/webhooks/meta`)
- Logs no backend

---

## 📋 Resumo Executivo

### ✅ Totalmente Implementado (2/15)
- ✅ `/audios` - Biblioteca completa
- ✅ `/automations` - Visualização (falta editor)

### ⚠️ Parcialmente Implementado (6/15)
- ⚠️ `/chat` - Falta mostrar funil/etapa/produto
- ⚠️ `/contacts` - Falta filtros e colunas
- ⚠️ `/contacts/:id` - Falta timeline e integrações
- ⚠️ `/kanban` - Precisa refatorar para funil real
- ⚠️ `/tasks` - Falta vincular a contatos
- ⚠️ `/dashboard` - Falta métricas de funil/integrações

### ❌ Não Implementado (4/15)
- ❌ `/products` - Tela completa a criar
- ❌ `/integrations` - Tela completa a criar
- ❌ `/events-log` - Tela completa a criar (opcional)
- ❌ `/profile` - Integrações (nice to have)

### ✅ Básico OK (1/15)
- ✅ `/profile` - Funcional, falta só status de integrações

---

## 🎯 Prioridades Sugeridas

### 🔴 Alta Prioridade
1. **Contacts** - Adicionar filtros de funil/etapa/produto
2. **ContactDetail** - Timeline e integrações
3. **Kanban** - Refatorar para funil real
4. **Dashboard** - Métricas de funil

### 🟡 Média Prioridade
5. **Chat** - Mostrar funil/etapa/produto
6. **Tasks** - Vincular a contatos
7. **Automations** - Editor completo
8. **Products** - Criar tela

### 🟢 Baixa Prioridade
9. **Integrations** - Criar tela
10. **Events-log** - Criar tela (opcional)
11. **Profile** - Status de integrações (nice to have)

---

## 💡 Observações

- O backend já tem muito da estrutura necessária (campos de funil/etapa/produto existem no `Thread`)
- A maioria das telas precisa apenas de melhorias na UI, não de novas APIs
- Algumas funcionalidades já estão parcialmente implementadas no código, só precisam ser expostas na UI



