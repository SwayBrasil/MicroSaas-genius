# 🎯 Detecção Automática de Funil/Etapa

## O que foi implementado

### 1. **Serviço de Detecção (`funnel_detector.py`)**
- Detecta automaticamente qual funil o lead deve entrar baseado na primeira mensagem
- Define a etapa inicial automaticamente
- Adiciona tags baseadas no conteúdo da mensagem
- Define source automaticamente

### 2. **Integração no Webhook**
- Quando uma nova thread é criada, detecta automaticamente o funil
- Quando a primeira mensagem chega, atualiza funil/etapa se ainda não tiver
- Salva tudo no `metadata` da thread

### 3. **Atualização Automática de Etapa**
- Quando a IA retorna `next_stage`, atualiza automaticamente o `stage_id`
- Mantém o histórico de progressão

### 4. **Exibição no Chat.tsx**
- Mostra automaticamente:
  - 🎯 Nome do Funil
  - 📍 Nome da Etapa
  - 📦 Produto
  - 🔗 Source
  - 🏷️ Tags (até 2, com "..." se tiver mais)

---

## Como Funciona

### **Detecção de Funil**

#### Funil Longo (LIFE) - ID: 1
**Palavras-chave:**
- "life", "quero saber", "como funciona"
- "emagrecer", "emagrecimento", "perder peso"
- "transformar", "corpo", "barriga"
- "treino", "dieta", "nutrição", "fitness"

**Etapa inicial:** Boas-vindas e Qualificação (ID: 1)

#### Mini Funil Black Friday - ID: 2
**Palavras-chave:**
- "black friday", "bf", "promoção", "promocao", "oferta especial"

**Etapa inicial:** Oferta Black Friday (ID: 1)

#### Funil de Recuperação 50% - ID: 3
**Palavras-chave:**
- "desconto 50", "50%", "recuperação", "recuperacao"
- "não comprei", "não comprou"

**Etapa inicial:** Oferta 50% (ID: 1)

### **Detecção de Tags**

Tags são adicionadas automaticamente baseadas no conteúdo:

- `dor_barriga` - se mencionar "barriga", "abdomen", "pochete", "flacidez"
- `dor_emagrecimento` - se mencionar "emagrecer", "perder peso"
- `dor_ganho_massa` - se mencionar "ganhar massa", "hipertrofia"
- `dor_autoestima` - se mencionar "autoestima", "vergonha", "espelho"
- `dor_composicao` - se mencionar "celulite", "flacidez", "pele"
- `urgente` - se mencionar "urgente", "rápido", "logo", "agora"
- `interessado` - se mencionar "quero", "gostaria", "interessado"

### **Detecção de Source**

- **"Eduzz compra"** - se mencionar "eduzz" e "comprou"
- **"Eduzz abandono"** - se mencionar "eduzz" mas não "comprou"
- **"The Members"** - se mencionar "the members" ou "members"
- **"WhatsApp orgânico"** - padrão (default)

---

## Fluxo Completo

### 1. **Nova Mensagem Chega (Webhook)**
```
Mensagem: "Quero emagrecer e minha barriga me incomoda"
↓
Detecta: Funil Longo (ID: 1), Etapa Boas-vindas (ID: 1)
Tags: ["life", "interessado", "dor_emagrecimento", "dor_barriga"]
Source: "WhatsApp orgânico"
↓
Salva no metadata da thread
```

### 2. **IA Responde**
```
IA retorna: {"response_type": "audio", "audio_id": "audio1_boas_vindas", "next_stage": "2"}
↓
Envia áudio
↓
Atualiza stage_id para "2" (Diagnóstico de Dores)
```

### 3. **Frontend Exibe**
```
Chat.tsx mostra:
🎯 Funil Longo (LIFE)
📍 Diagnóstico de Dores
🔗 WhatsApp orgânico
🏷️ life, interessado, dor_emagrecimento, dor_barriga
```

---

## Onde os Dados Ficam Salvos

### **Banco de Dados**
```json
{
  "funnel_id": "1",
  "stage_id": "2",
  "source": "WhatsApp orgânico",
  "tags": ["life", "interessado", "dor_emagrecimento", "dor_barriga"],
  "next_stage": null
}
```

### **Frontend**
- `thread.funnel_id` - ID do funil
- `thread.stage_id` - ID da etapa
- `thread.source` - Origem
- `thread.tags` - Array de tags
- `thread.metadata` - Objeto completo

---

## Teste

1. **Envie uma mensagem nova no WhatsApp:**
   - "Quero emagrecer"
   - "Black Friday"
   - "Desconto 50%"

2. **Verifique no Chat.tsx:**
   - Deve mostrar funil/etapa automaticamente
   - Deve mostrar source e tags

3. **Verifique no banco:**
   ```sql
   SELECT meta FROM threads WHERE id = <thread_id>;
   ```

---

## Próximos Passos

- [ ] Implementar avanço automático de etapa baseado em condições
- [ ] Adicionar mais palavras-chave para detecção
- [ ] Melhorar detecção de source (webhooks externos)
- [ ] Adicionar detecção de produto baseado na mensagem

