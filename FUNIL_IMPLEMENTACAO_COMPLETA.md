# ✅ FUNIL COMPLETO - IMPLEMENTAÇÃO FINALIZADA

## 📋 O QUE FOI IMPLEMENTADO

### 1. ✅ Arquivo JSON de Configuração
**Localização:** `api/app/config/funnel_config.json`

Contém:
- ✅ Funil Longo completo (7 fases)
- ✅ Mini Funil BF (5 fases)
- ✅ Todos os gatilhos e triggers
- ✅ Todas as mensagens exatas
- ✅ Mapeamento de estados de leads
- ✅ Links de checkout
- ✅ Textos oficiais

### 2. ✅ Biblioteca de Assets Atualizada
**Localização:** `api/app/services/assets_library.py`

Mapeados:
- ✅ Áudio 1 (boas-vindas): `00000011-AUDIO-2025-11-24-22-40-30.opus`
- ✅ Áudio 2 (dor genérica): `00000017-AUDIO-2025-11-24-22-47-05.opus`
- ✅ Áudio 3 (explicação planos): `00000032-AUDIO-2025-11-24-22-51-49.opus`
- ✅ Áudio carrinho abandonado: `00000041-AUDIO-2025-11-24-22-56-22.opus`
- ✅ Áudios BF (follow-ups): `00000047.opus`, `00000049.opus`, `00000060.opus`, `00000063.opus`
- ✅ 8 imagens de prova social (00000018 a 00000025)
- ✅ Imagens de campanha BF (00000044, 00000045)

### 3. ✅ Gerenciador de Estados Atualizado
**Localização:** `api/app/services/funnel_stage_manager.py`

Estados implementados:
- ✅ FASE 1 - Lead Frio
- ✅ FASE 2 - Aquecimento (Descoberta da Dor)
- ✅ FASE 3 - Aquecido (Objeção ou Interesse)
- ✅ FASE 4 - Quente (Apresentação dos Planos)
- ✅ FASE 5 - Fechamento
- ✅ FASE 6 - Pós-Venda
- ✅ FASE 7 - Carrinho Abandonado
- ✅ Mini Funil BF (5 fases)

### 4. ✅ Detecção de Gatilhos Melhorada
**Localização:** `api/app/services/automation_engine.py`

Gatilhos implementados:
- ✅ Entrada do funil (palavras-chave exatas)
- ✅ Detecção de dor (5 tipos mapeados)
- ✅ Detecção de objeções
- ✅ Detecção de interesse
- ✅ Pedido de planos
- ✅ Escolha de plano (mensal/anual)
- ✅ Priorização: "como funciona" não dispara áudio 1

---

## 🔥 FLUXO COMPLETO DO FUNIL LONGO

### FASE 1 - Lead Frio
**Gatilhos:**
- "Oi Paloma"
- "Eae"
- "Quero saber como funciona o Life"
- "Preciso fazer algo por mim mesma"
- "Quero ficar gostosa"
- Qualquer variação de interesse

**Ação:**
1. Envia áudio 1: `00000011-AUDIO-2025-11-24-22-40-30.opus`
2. Texto: "Perfeitaaa, me conta qual é seu objetivo hoje? 🔥✨\n\nO que você mais quer transformar no seu corpo agora?"

**Próxima fase:** FASE 2

---

### FASE 2 - Descoberta da Dor
**Gatilhos:**
- Perder gordura / pochete
- Flacidez / celulite
- Ganhar massa / bunda / coxas
- Falta de foco
- Dieta / alimentação / constância

**Ação:**
1. Envia áudio 2: `00000017-AUDIO-2025-11-24-22-47-05.opus`
2. Envia carrossel de 8 imagens (00000018 a 00000025)
3. Texto: "Me conta aqui gata, o que tá faltando pra tu dar esse passo? 👯‍♀️✨"

**Próxima fase:** FASE 3

---

### FASE 3 - Objeção ou Interesse Alto
**Gatilhos:**
- Objeções: "tô sem tempo", "tô sem dinheiro", "não sei se consigo"
- Interesse: "sim", "pode ser", "legal", "ok", "entendi"

**Ação:**
- Quebra objeção (se houver)
- Texto: "Perfeitaaaa, posso te explicar melhor sobre os planos?"

**Próxima fase:** FASE 4

---

### FASE 4 - Apresentação dos Planos
**Gatilho:**
- Lead responde "sim" ou pede planos

**Ação:**
1. Envia áudio 3: `00000032-AUDIO-2025-11-24-22-51-49.opus`
2. Texto do Plano Mensal:
   ```
   *✅ Plano Mensal – R$69,90/mês*
   
   • Acesso à base do LIFE: treinos, planos alimentares, aulas sobre disciplina e motivação.
   • Pode cancelar quando quiser.
   ```
3. Texto do Plano Anual:
   ```
   *🔥 Plano Anual – R$598,80 (ou 12x de R$49,90)*
   
   • Acesso COMPLETO a tudo no LIFE: treinos, planos alimentares, aulas extras com médicas, nutricionistas e psicólogas.
   • Inclui o módulo exclusivo do Shape Slim.
   • Pode ser parcelado em até 12x sem comprometer o limite do cartão.
   ```
4. Pergunta final: "Agora me fala, gata: qual plano faz mais sentido pra você? 💬🔥"

**Próxima fase:** FASE 5

---

### FASE 5 - Fechamento
**Gatilhos:**
- "anual", "plano anual", "quero o anual" → Link: `https://edzz.la/DO408?a=10554737`
- "mensal", "plano mensal", "quero o mensal" → Link: `https://edzz.la/GQRLF?a=10554737`

**Ação:**
- Envia link de checkout correspondente
- Texto de confirmação

**Próxima fase:** FASE 6 (webhook) ou FASE 7 (carrinho abandonado)

---

### FASE 6 - Pós-Venda (Webhook Eduzz)
**Gatilho:**
- Webhook Eduzz: `sale.approved`

**Ação:**
- Envia mensagem de boas-vindas com:
  - Links do app (Android/iOS)
  - Link do grupo WhatsApp
  - Link de primeiro acesso (24h)
  - Links de suporte

**Estado:** Assinante

---

### FASE 7 - Carrinho Abandonado
**Gatilho:**
- 30 minutos após receber link de checkout sem comprar

**Ação:**
1. Envia áudio: `00000041-AUDIO-2025-11-24-22-56-22.opus`
2. Texto: "Ooi minha gata, percebi que você chegou até o final da sua inscrição no LIFE mas não concluiu 😢\n\n*Seu plano já está pronto pra começar hoje!*\n\n👉 Te preparei um link especial com *50% DE DESCONTO SÓ HOJE!!!*\n\nQuer saber mais? 💪✨"

---

## 🟣 MINI FUNIL - BLACK FRIDAY

### FASE 1 - Imagem da Campanha
- Envia: `00000044.jpg` e `00000045.jpg`

### FASE 2 - Áudio da Promo
- Envia: `00000047.opus`

### FASE 3 - Follow-up 1 (60 min sem resposta)
- Envia: `00000049.opus`

### FASE 4 - Follow-up 2 (120 min sem resposta)
- Envia: `00000060.opus`

### FASE 5 - Follow-up 3 (240 min sem resposta)
- Envia: `00000063.opus`

---

## 📊 ESTADOS DE LEADS

| Estado | Score | Descrição |
|--------|-------|-----------|
| **Frio** | 0-20 | Chegou agora sem contexto |
| **Aquecimento** | 21-40 | Já ouviu áudio 1 |
| **Aquecido** | 41-60 | Já respondeu dor e recebeu provas sociais |
| **Quente** | 61-80 | Já pediu planos / viu planos |
| **Assinante** | 81-100 | Webhook de compra confirmado |
| **Pendência** | 0 | Assinante com fatura atrasada |
| **Aquecido (plataforma)** | 41-60 | Já criou conta na plataforma |
| **Quente (recebeu oferta)** | 61-80 | Recebeu promo / desconto / link especial |

---

## 🔧 PRÓXIMOS PASSOS PARA FINALIZAR

### 1. Atualizar `agent_instructions.txt`
O arquivo já existe e está funcional, mas pode ser refinado com base no documento fornecido.

### 2. Implementar Follow-ups Automáticos
Criar sistema de agendamento para:
- Follow-ups de inatividade
- Carrinho abandonado (30 min)
- Follow-ups do Mini Funil BF

### 3. Integrar Webhook Eduzz
Já existe estrutura em `api/app/routers/eduzz.py`, apenas garantir que dispara FASE 6.

### 4. Testar Fluxo Completo
Testar cada fase do funil para garantir que está funcionando corretamente.

---

## 📝 NOTAS IMPORTANTES

1. **Áudios específicos por tipo de dor:** Por enquanto todos usam o áudio genérico. Quando a Paloma enviar os 5 áudios específicos, atualizar o mapeamento.

2. **Links de checkout:** Já estão configurados no JSON:
   - Anual: `https://edzz.la/DO408?a=10554737`
   - Mensal: `https://edzz.la/GQRLF?a=10554737`

3. **Link de primeiro acesso:** Precisa ser gerado dinamicamente pelo webhook da Eduzz.

4. **Follow-ups:** Sistema de agendamento precisa ser implementado (pode usar Celery ou similar).

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

- [x] JSON de configuração criado
- [x] Assets mapeados
- [x] Estados do funil definidos
- [x] Gatilhos implementados
- [x] Detecção de "como funciona" corrigida
- [ ] Follow-ups automáticos (próximo passo)
- [ ] Testes end-to-end
- [ ] Refinamento do prompt da IA

---

**Status:** ✅ **IMPLEMENTAÇÃO BASE COMPLETA**

O sistema está pronto para processar o funil completo. Falta apenas implementar os follow-ups automáticos e fazer testes.

