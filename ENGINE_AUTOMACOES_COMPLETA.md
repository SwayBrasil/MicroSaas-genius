# ✅ ENGINE DE AUTOMAÇÕES - IMPLEMENTAÇÃO COMPLETA

## 📋 Resumo

Engine completa de automações implementada com:
- Campo `lead_stage` no banco (Thread)
- Constantes de todas as etapas
- Gatilhos do funil longo
- Automações BF e Recuperação 50%
- Detector de suporte integrado

---

## 🗄️ 1. CAMPO `lead_stage` NO BANCO

### Arquivo: `api/app/models.py`

**Adicionado:**
```python
lead_stage = Column(String(64), nullable=True, index=True)
```

**Migração:** `_fix_threads_lead_stage()` em `main.py`
- Cria coluna se não existir
- Cria índice para performance

---

## 📊 2. CONSTANTES DE ETAPAS

### Arquivo: `api/app/services/automation_engine.py`

### Funil Longo:
- `FUNIL_LONGO_FASE_1_FRIO = "frio"`
- `FUNIL_LONGO_FASE_2_AQUECIMENTO = "aquecimento"`
- `FUNIL_LONGO_FASE_3_AQUECIDO = "aquecido"`
- `FUNIL_LONGO_FASE_4_QUENTE = "quente"`
- `FUNIL_LONGO_POS_COMPRA = "pos_compra"`
- `FUNIL_LONGO_FATURA_PENDENTE = "fatura_pendente"`
- `FUNIL_LONGO_RECUPERACAO = "recuperacao"`

### Mini Funil BF:
- `BF_AQUECIDO = "bf_aquecido"`
- `BF_QUENTE = "bf_quente"`
- `BF_FOLLOWUP_ENVIADO = "bf_followup_enviado"`

### Recuperação 50%:
- `RECUP_50_OFERTA_ENVIADA = "recup_50_oferta_enviada"`
- `RECUP_50_SEM_RESPOSTA_1 = "recup_50_sem_resposta_1"`
- `RECUP_50_SEM_RESPOSTA_2 = "recup_50_sem_resposta_2"`

---

## 🎯 3. GATILHOS DO FUNIL LONGO

### 3.1 Gatilho de Entrada
**Detecta:**
- "quero saber do life"
- "como funciona o life"
- "quero ser gostosa"
- "quero emagrecer"
- "life", "como funciona", "quero saber"

**Ação:**
- Envia `01-boas-vindas-qualificacao.opus`
- Define `lead_stage = "frio"`
- Evento: `USER_SENT_FIRST_MESSAGE`

### 3.2 Gatilho de Dor
**Detecta:**
- Lead está em `frio`
- Menciona: "dor", "problema", "incomoda", "barriga", "flacidez", "autoestima", etc.

**Ação:**
- Envia `02-dor-generica.opus`
- Envia provas sociais (imagens) - TODO: implementar send_image
- Envia texto: "Me conta aqui gata, o que tá faltando pra tu dar esse passo? 👯‍♀️✨"
- Define `lead_stage = "aquecimento"`
- Evento: `IA_SENT_AUDIO_DOR`

### 3.3 Gatilho de Interesse em Plano
**Detecta:**
- Lead está em `aquecimento` ou `aquecido`
- Menciona: "quero saber os planos", "como funciona o pagamento", "quanto custa", "preço"

**Ação:**
- Envia `03-explicacao-planos.opus`
- Envia template `planos-life.json`
- Define `lead_stage = "aquecido"`
- Evento: `IA_SENT_EXPLICACAO_PLANOS`

### 3.4 Gatilho de Escolha de Plano
**Detecta:**
- Lead está em `aquecido`
- Menciona: "quero o mensal", "quero o anual", "mensal", "anual"

**Ação:**
- Envia template `fechamento-anual.txt` ou `fechamento-mensal.txt`
- Define `lead_stage = "quente"`
- Evento: `USER_ESCOLHEU_PLANO`

### 3.5 Gatilho Pós-Compra (via webhook)
**Quando:** Eduzz envia webhook "paid"

**Ação:**
- Envia template `pos-compra-life.txt`
- Define `lead_stage = "pos_compra"`
- Evento: `EDUZZ_WEBHOOK_APROVADA`

**TODO:** Implementar endpoint `/webhooks/eduzz`

---

## 🎁 4. AUTOMAÇÃO MINI FUNIL BF

### 4.1 Entrada no Funil BF
**Função:** `trigger_bf_funnel()`

**Pode ser disparado por:**
- Tag de campanha
- Botão manual
- Evento externo

**Ação:**
- Envia `mini-funil-bf/01-oferta-black-friday.opus`
- Envia texto de acompanhamento
- Define `lead_stage = "bf_aquecido"`
- Evento: `BF_ENTRADA`

### 4.2 Follow-up BF
**Função:** `trigger_bf_followup()`

**Quando:** Não respondeu em X tempo

**Ação:**
- Envia `mini-funil-bf/02-followup-sem-resposta.opus`
- Envia texto de acompanhamento
- Define `lead_stage = "bf_followup_enviado"`
- Evento: `BF_FOLLOWUP_1`

**TODO:** Implementar worker de agendamento de follow-ups

---

## 💰 5. AUTOMAÇÃO RECUPERAÇÃO 50%

### 5.1 Oferta Inicial
**Função:** `trigger_recup_50_oferta()`

**Disparado quando:**
- Lead foi até o final da plataforma e não concluiu
- Status Eduzz = iniciado mas não pago

**Ação:**
- Envia template `recuperacao-50-oferta.txt`
- Define `lead_stage = "recup_50_oferta_enviada"`
- Evento: `RECUP_50_DISPARADO`

### 5.2 Follow-up 1
**Função:** `trigger_recup_50_followup_1()`

**Quando:** Não respondeu em X minutos

**Ação:**
- Envia `recuperacao-50/02-audio-followup.opus`
- Envia texto de acompanhamento
- Define `lead_stage = "recup_50_sem_resposta_1"`
- Evento: `RECUP_50_FOLLOWUP_1`

### 5.3 Follow-up 2 (Último Chamado)
**Função:** `trigger_recup_50_followup_2()`

**Quando:** Ainda não respondeu após follow-up 1

**Ação:**
- Envia `recuperacao-50/03-audio-ultimo-chamado.opus`
- Envia texto de acompanhamento
- Define `lead_stage = "recup_50_sem_resposta_2"`
- Evento: `RECUP_50_FOLLOWUP_2`

**TODO:** Implementar worker de agendamento de follow-ups

---

## 🚨 6. DETECTOR DE SUPORTE

### Integrado na Engine

**Prioridade máxima:** Antes de qualquer automação

**Detecta:**
- Acesso, login, app, cobrança, fatura, erro, suporte, cancelamento, cartão, pagamento falho

**Ação:**
- Envia mensagem: "Gata, pra isso o meu time de suporte é perfeito, tá? 💖\n\nVou te passar pra uma pessoa da equipe que resolve rapidinho esse tipo de coisa, combinado?"
- Marca `need_human = true`
- Para automações (não empurra para venda)
- Retorna `should_stop_automation = True`

---

## 🔧 7. INTEGRAÇÃO NO BACKEND

### `api/app/main.py` - Webhook Twilio

**Fluxo:**
1. Recebe mensagem
2. Processa automação (`process_automation()`)
3. Se detectou suporte → para e ativa takeover
4. Se detectou gatilho → executa ação e atualiza `lead_stage`
5. Se não detectou → processa com LLM normalmente

**Atualização de `lead_stage`:**
- Atualiza coluna `thread.lead_stage`
- Atualiza `thread.meta["lead_stage"]`
- Salva no banco

---

## 📝 8. MAPEAMENTO DE EVENTOS PARA ESTÁGIOS

```python
EVENT_TO_STAGE_MAP = {
    "USER_SENT_FIRST_MESSAGE": "frio",
    "IA_SENT_AUDIO_DOR": "aquecimento",
    "IA_SENT_EXPLICACAO_PLANOS": "aquecido",
    "USER_ESCOLHEU_PLANO": "quente",
    "EDUZZ_WEBHOOK_APROVADA": "pos_compra",
    "EDUZZ_WEBHOOK_PENDENTE": "fatura_pendente",
    "TEMPO_LIMITE_PASSOU": "recuperacao",
    "BF_ENTRADA": "bf_aquecido",
    "BF_CLICOU_REAGIU": "bf_quente",
    "RECUP_50_DISPARADO": "recup_50_oferta_enviada",
    "RECUP_50_FOLLOWUP_1": "recup_50_sem_resposta_1",
    "RECUP_50_FOLLOWUP_2": "recup_50_sem_resposta_2",
}
```

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

- [x] Campo `lead_stage` no banco
- [x] Constantes de todas as etapas
- [x] Gatilho de entrada (funil longo)
- [x] Gatilho de dor (funil longo)
- [x] Gatilho de interesse em plano (funil longo)
- [x] Gatilho de escolha de plano (funil longo)
- [x] Automação BF (entrada + follow-up)
- [x] Automação Recuperação 50% (oferta + 2 follow-ups)
- [x] Detector de suporte integrado
- [x] Atualização automática de `lead_stage`
- [x] Integração no webhook Twilio
- [ ] Webhook Eduzz (pós-compra)
- [ ] Worker de agendamento de follow-ups
- [ ] Função `send_image()` para provas sociais

---

## 🚀 PRÓXIMOS PASSOS

1. **Implementar webhook Eduzz:**
   - Endpoint `/webhooks/eduzz`
   - Processar eventos: `purchase_approved`, `purchase_pending`, `purchase_refused`
   - Atualizar `lead_stage` para `pos_compra` ou `fatura_pendente`

2. **Implementar worker de follow-ups:**
   - Agendar follow-ups baseado em tempo
   - Processar fila de follow-ups pendentes
   - Atualizar `lead_stage` automaticamente

3. **Implementar `send_image()`:**
   - Função no `twilio.py`
   - Enviar múltiplas imagens (provas sociais)
   - Integrar na ação de dor

4. **Testar fluxo completo:**
   - Testar cada gatilho
   - Verificar atualização de `lead_stage`
   - Verificar detecção de suporte

---

## 📚 ARQUIVOS CRIADOS/MODIFICADOS

- ✅ `api/app/services/automation_engine.py` (novo)
- ✅ `api/app/models.py` (adicionado `lead_stage`)
- ✅ `api/app/main.py` (integração + migração)
- ✅ `ENGINE_AUTOMACOES_COMPLETA.md` (documentação)

