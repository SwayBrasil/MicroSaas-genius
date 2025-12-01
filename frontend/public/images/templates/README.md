# 📝 Templates de Texto - Documentação

Esta pasta contém os **textos prontos** que a IA/sistema vai usar como mensagem nos funis de automação.

## 📁 Arquivos Disponíveis

### 1. `planos-life.json`
**Descrição:** Estrutura JSON com textos dos planos Mensal e Anual.

**Conteúdo:**
- Texto do Plano Mensal (R$69,90/mês)
- Texto do Plano Anual (R$598,80 ou 12x de R$49,90)
- Pergunta final: "Agora me fala, gata: qual plano faz mais sentido pra você?"

**Quando usar:** Após o áudio `03-explicacao-planos.opus` no Funil Longo.

---

### 2. `fechamento-anual.txt`
**Descrição:** Mensagem de fechamento para o Plano Anual.

**Conteúdo:**
- Texto motivacional
- Link: `https://edzz.la/DO408?a=10554737`
- Instruções sobre ajustar limite do cartão

**Quando usar:** Quando a lead escolhe o Plano Anual.

---

### 3. `fechamento-mensal.txt`
**Descrição:** Mensagem de fechamento para o Plano Mensal.

**Conteúdo:**
- Texto motivacional
- Link: `https://edzz.la/GQRLF?a=10554737`
- Instruções finais

**Quando usar:** Quando a lead escolhe o Plano Mensal.

---

### 4. `pos-compra-life.txt`
**Descrição:** Mensagem de boas-vindas pós-compra aprovada.

**Conteúdo:**
- "AGORA VOCÊ FAZ PARTE DO LIFE!!"
- Links do app (Android/iPhone)
- Grupo de avisos
- Link mágico personalizado (válido por 24h)
- Links para suporte / suporte técnico

**Quando usar:** Após webhook Eduzz confirmar compra aprovada.

**Variáveis dinâmicas:**
- `[LINK PERSONALIZADO]` - deve ser substituído pelo link real do usuário

---

### 5. `recuperacao-50-oferta.txt`
**Descrição:** Primeira mensagem do funil de recuperação com 50% de desconto.

**Conteúdo:**
- Texto acolhedor
- Menção de que chegou até o final mas não concluiu
- Oferta de 50% de desconto só hoje
- Call to action

**Quando usar:** Quando lead chegou até o final da inscrição na plataforma mas não concluiu a compra.

**Sequência:**
1. Este texto (primeiro contato)
2. Se não responder → `02-audio-followup.opus`
3. Se ainda não responder → `03-audio-ultimo-chamado.opus`

---

## 🔄 Fluxo de Uso

### Funil Longo

1. **Após áudio de planos:**
   - Sistema lê `planos-life.json`
   - Envia texto do plano Mensal e Anual
   - Pergunta qual plano faz sentido

2. **Lead escolhe plano:**
   - **Anual:** Sistema envia `fechamento-anual.txt`
   - **Mensal:** Sistema envia `fechamento-mensal.txt`

3. **Compra aprovada:**
   - Webhook Eduzz confirma
   - Sistema envia `pos-compra-life.txt` (com link personalizado)

### Funil de Recuperação 50%

1. **Primeiro contato:**
   - Sistema envia `recuperacao-50-oferta.txt`

2. **Follow-ups:**
   - Áudios (não textos)

---

## 📝 Formato dos Arquivos

- **`.txt`** - Texto simples, uma mensagem por arquivo
- **`.json`** - Estrutura JSON para múltiplas opções (ex: planos)

---

## 🔧 Como Adicionar Novos Templates

1. **Crie o arquivo** nesta pasta
2. **Use nome descritivo:** `{contexto}-{tipo}.txt` ou `.json`
3. **Atualize** o código que referencia esses templates
4. **Documente** neste README quando usar

---

## ✅ Checklist

- [x] `planos-life.json` - Textos dos planos
- [x] `fechamento-anual.txt` - Link plano anual
- [x] `fechamento-mensal.txt` - Link plano mensal
- [x] `pos-compra-life.txt` - Boas-vindas pós-compra
- [x] `recuperacao-50-oferta.txt` - Oferta 50% desconto
- [ ] `bf-oferta.txt` - (Opcional) Texto da oferta BF
- [ ] `bf-followup.txt` - (Opcional) Texto follow-up BF

---

**Última atualização:** 2025-01-XX

