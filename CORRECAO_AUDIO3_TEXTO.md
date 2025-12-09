# 🔧 Correção: Áudio 3 + Texto dos Planos

## ❌ Problema Identificado

A LLM estava enviando apenas o áudio `audio3_explicacao_planos` sem incluir o texto dos planos na mesma resposta, fazendo com que a lead tivesse que pedir o texto separadamente.

## ✅ Correções Aplicadas

### 1. Regra Crítica Adicionada no Início do Prompt
- Adicionada seção **"🚨 REGRA CRÍTICA: ÁUDIO 3 + TEXTO DOS PLANOS (SEMPRE JUNTOS!)"** logo após a introdução
- Formato obrigatório explicado claramente
- Exemplos de formato correto vs. errado

### 2. Atualização na Seção de Exemplos
- Seção "Fase 3 - Explicação dos Planos" atualizada com formato obrigatório
- Exemplos práticos mostrando áudio + texto na mesma resposta

### 3. Atualização na Biblioteca de Áudios
- Instruções críticas adicionadas na tabela de mapeamento de áudios
- Formato obrigatório explicado com exemplos

### 4. Atualização nos Exemplos de Uso
- Seção "Situação: Lead pede informações sobre planos" atualizada
- Removido formato JSON antigo (PASSO 1 + PASSO 2)
- Substituído por formato multimídia único (áudio + texto na mesma resposta)

### 5. Atualização na Seção de Quebra de Objeções
- Exemplos de resposta atualizados para incluir formato multimídia
- Enfatizado que texto dos planos deve vir na mesma resposta

## 📋 Formato Obrigatório Agora

Quando a lead quer saber dos planos, a LLM deve responder assim:

```text
Amo essa atitude! Vou te mandar um áudio explicando os planos agora 💪🔥

[Áudio enviado: audio3_explicacao_planos]

*✅ Plano Mensal – R$69,90/mês*

• Acesso à base do LIFE: treinos, planos alimentares, aulas sobre disciplina e motivação.
• Pode cancelar quando quiser.

*🔥Plano Anual – R$598,80 (ou 12x de R$49,90)*

• Acesso COMPLETO a tudo no LIFE: treinos, planos alimentares, aulas extras com médicas, nutricionistas e psicólogas.
• Inclui o módulo exclusivo do Shape Slim.
• Pode ser parcelado em até 12x sem comprometer o limite do cartão.

Agora me fala, gata: qual plano faz mais sentido pra você? 💬🔥
```

## ✅ Resultado Esperado

Agora, quando a lead disser "pode ser", "quero saber", "me mostra", etc., a LLM vai:
1. ✅ Enviar o áudio `audio3_explicacao_planos`
2. ✅ Enviar o texto completo dos planos **na mesma resposta**
3. ✅ Tudo na ordem correta: áudio primeiro, texto depois

**Sem precisar a lead pedir o texto separadamente!**

## 🧪 Como Testar

1. Enviar mensagem como lead: "pode ser" ou "quero saber dos planos"
2. Verificar se a resposta inclui:
   - Comando `[Áudio enviado: audio3_explicacao_planos]`
   - Texto completo dos planos logo após
3. Verificar logs do sistema para confirmar que ambos foram enviados

---

**Data da correção:** 03/12/2025
**Arquivo modificado:** `api/app/agent_instructions.txt`


