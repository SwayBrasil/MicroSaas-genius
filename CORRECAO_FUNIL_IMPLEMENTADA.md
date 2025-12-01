# ✅ CORREÇÃO CRÍTICA: FUNIL AGORA FUNCIONA CORRETAMENTE

## 🐛 PROBLEMA IDENTIFICADO

A IA estava **pulando todas as etapas do funil** e respondendo em texto livre ao invés de seguir o funil estruturado.

**Exemplo do problema:**
- Usuário: "quero saber do life"
- ❌ IA: Resposta em texto livre (pulou áudio 1)
- ❌ IA: Não detectou gatilho
- ❌ IA: Não atualizou lead_stage

---

## ✅ CORREÇÕES IMPLEMENTADAS

### 1. **Engine agora BLOQUEIA LLM quando detecta gatilho**

**Antes:**
```python
# Engine executava ação mas LLM ainda era chamado
new_stage, metadata, should_stop = await process_automation(...)
# should_stop sempre era False (exceto suporte)
# LLM era chamado mesmo assim
```

**Agora:**
```python
# Engine retorna should_skip_llm=True quando executa ação
new_stage, metadata, should_skip_llm = await process_automation(...)
# Se should_skip_llm=True, LLM NÃO é chamado
if should_skip_llm:
    return {"status": "ok", "automation_executed": True}
```

### 2. **Detecção de gatilhos melhorada**

**Gatilho de Entrada:**
- Detecta: "quero saber do life", "como funciona o life", "life", etc.
- ✅ Envia: `01-boas-vindas-qualificacao.opus`
- ✅ Atualiza: `lead_stage = "frio"`
- ✅ NÃO chama LLM

**Gatilho de Dor:**
- Detecta: "dor", "problema", "barriga", "flacidez", "quero emagrecer", etc.
- ✅ Envia: `02-dor-generica.opus` + provas sociais + texto
- ✅ Atualiza: `lead_stage = "aquecimento"`
- ✅ NÃO chama LLM

**Gatilho de Interesse em Plano:**
- Detecta: "quero saber os planos", "quanto custa", "preço", etc.
- ✅ Envia: `03-explicacao-planos.opus` + template `planos-life.json`
- ✅ Atualiza: `lead_stage = "aquecido"`
- ✅ NÃO chama LLM

**Gatilho de Escolha de Plano:**
- Detecta: "mensal", "anual", "quero o mensal", etc.
- ✅ Envia: Template `fechamento-mensal.txt` ou `fechamento-anual.txt` (com links corretos)
- ✅ Atualiza: `lead_stage = "quente"`
- ✅ NÃO chama LLM

### 3. **Mensagens salvas no banco**

Agora quando uma automação executa:
- ✅ Salva mensagens no banco (áudios, templates, textos)
- ✅ Histórico completo preservado
- ✅ Mensagem de sistema registra a automação executada

### 4. **Prompt atualizado**

Adicionada regra crítica no prompt:
```
🚨 REGRA CRÍTICA: NUNCA RESPONDA EM TEXTO LIVRE QUANDO HOUVER AUTOMAÇÃO

Se o sistema detectar um gatilho e executar uma automação (áudio, template, etc.), 
você NÃO deve responder em texto livre.

Você só deve responder em texto livre quando:
- Não há gatilho detectado
- A lead está fazendo perguntas que não são gatilhos
- Precisa trazer de volta ao funil
```

### 5. **Mapeamento de templates corrigido**

Adicionados aliases para facilitar:
- `"planos-life"` → `planos-life.json`
- `"fechamento-anual"` → `fechamento-anual.txt`
- `"fechamento-mensal"` → `fechamento-mensal.txt`

---

## 🔄 FLUXO CORRETO AGORA

### Mensagem 1: "quero saber do life"
```
1. Engine detecta gatilho: ENTRY_FUNIL_LONGO
2. Executa ação: Envia áudio 1
3. Atualiza: lead_stage = "frio"
4. Salva no banco
5. Retorna: should_skip_llm = True
6. ❌ LLM NÃO é chamado
```

### Mensagem 2: "minha barriga me incomoda"
```
1. Engine detecta gatilho: DOR_DETECTADA
2. Executa ação: Envia áudio 2 + provas sociais + texto
3. Atualiza: lead_stage = "aquecimento"
4. Salva no banco
5. Retorna: should_skip_llm = True
6. ❌ LLM NÃO é chamado
```

### Mensagem 3: "quero saber os planos"
```
1. Engine detecta gatilho: INTERESSE_PLANO
2. Executa ação: Envia áudio 3 + template planos
3. Atualiza: lead_stage = "aquecido"
4. Salva no banco
5. Retorna: should_skip_llm = True
6. ❌ LLM NÃO é chamado
```

### Mensagem 4: "mensal"
```
1. Engine detecta gatilho: ESCOLHEU_PLANO
2. Executa ação: Envia template fechamento-mensal.txt (com link correto)
3. Atualiza: lead_stage = "quente"
4. Salva no banco
5. Retorna: should_skip_llm = True
6. ❌ LLM NÃO é chamado
```

### Mensagem 5: "qual o horário de atendimento?"
```
1. Engine NÃO detecta gatilho
2. Retorna: should_skip_llm = False
3. ✅ LLM é chamado (responde em texto livre)
```

---

## 📝 ARQUIVOS MODIFICADOS

- ✅ `api/app/services/automation_engine.py`
  - `process_automation()` agora retorna `should_skip_llm=True` quando executa ação
  - `detect_funil_longo_trigger()` melhorado com detecção mais precisa
  - `execute_funil_longo_action()` salva mensagens no banco

- ✅ `api/app/main.py`
  - Verifica `should_skip_llm` antes de chamar LLM
  - Se `True`, retorna sem chamar LLM

- ✅ `api/app/agent_instructions.txt`
  - Adicionada regra crítica sobre não responder quando há automação

- ✅ `api/app/services/template_loader.py`
  - Adicionados aliases para templates

---

## ✅ TESTE AGORA

1. Envie: "quero saber do life"
   - ✅ Deve receber áudio 1
   - ✅ lead_stage deve ser "frio"
   - ✅ Não deve receber texto da IA

2. Envie: "minha barriga me incomoda"
   - ✅ Deve receber áudio 2 + provas sociais + texto
   - ✅ lead_stage deve ser "aquecimento"
   - ✅ Não deve receber texto da IA

3. Envie: "quero saber os planos"
   - ✅ Deve receber áudio 3 + template planos
   - ✅ lead_stage deve ser "aquecido"
   - ✅ Não deve receber texto da IA

4. Envie: "mensal"
   - ✅ Deve receber template fechamento-mensal.txt (com link correto)
   - ✅ lead_stage deve ser "quente"
   - ✅ Não deve receber texto da IA

---

## 🎯 RESULTADO ESPERADO

Agora o funil funciona **exatamente** como a Paloma descreveu:
- ✅ Áudios são enviados automaticamente
- ✅ Templates corretos são usados
- ✅ Links corretos são enviados
- ✅ lead_stage é atualizado automaticamente
- ✅ LLM só responde quando não há gatilho
- ✅ Histórico completo é preservado

