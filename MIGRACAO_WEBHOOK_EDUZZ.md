# ⚠️ Migração do Webhook Eduzz - Developer Hub

## Aviso Importante

**O webhook atual da Eduzz será descontinuado em 30/04/2026.**

A Eduzz está migrando todas as integrações para a **Developer Hub**, que oferece:
- ✅ Maior estabilidade
- ✅ Redisparo em massa de eventos com falha
- ✅ Canal exclusivo para desenvolvedores

👉 **Recomendação**: Migrar o quanto antes para evitar impactos.

🔗 [Saiba mais sobre o novo webhook e como migrar](https://developer.eduzz.com)

---

## Webhooks Atuais Configurados

### 1. TheMembers
- **URL**: `https://api.themembers.com.br/webhooks/4073/checkouts/eduzz`
- **Status**: Ativo
- **Produtos**: Todos
- **Função**: Cria usuários e assinaturas na The Members

### 2. N8N (venda)
- **URL**: `https://hooks-n.nevoaai.com/webhook/life-plm`
- **Status**: Ativo
- **Produtos**: 2382703, 2382996, 2352149, +18
- **Função**: Automações de venda

---

## Produtos Identificados

### ACESSO MENSAL - LIFE 2025
- **Product ID**: `2457307`
- **Tipo**: Mensal
- **Valor**: R$ 69,90

### LIFE ACESSO ANUAL - 2 ANOS
- **Product ID**: `2562423`
- **Tipo**: Anual
- **Valor**: R$ 598,80 (ou 12x de R$ 49,90)

---

## Status de Fatura no Webhook

O webhook da Eduzz envia diferentes status de fatura:

- **"Paga"**: Fatura paga e confirmada
- **"Aberta"**: Fatura criada mas ainda não paga
- **"Em Dia"**: Assinatura em dia (mensalidade recorrente)

**Ação atual**: O sistema processa apenas eventos `sale.approved`. Outros status são ignorados.

---

## Próximos Passos para Migração

1. **Criar conta na Developer Hub da Eduzz**
2. **Configurar novo webhook** com a URL do nosso sistema
3. **Testar eventos** (sale.approved, cart.abandonment, etc.)
4. **Atualizar código** se necessário (formato pode mudar)
5. **Manter webhook antigo ativo** durante período de transição
6. **Desativar webhook antigo** após confirmação de funcionamento

---

## URL do Webhook Atual

Nossa URL atual do webhook:
```
https://swaybrasil.com/webhook/eduzz
```

Ou em desenvolvimento:
```
https://terrier-eternal-distinctly.ngrok-free.app/webhook/eduzz
```

---

## Checklist de Migração

- [ ] Criar conta na Developer Hub
- [ ] Configurar novo webhook na Developer Hub
- [ ] Testar eventos de venda (sale.approved)
- [ ] Testar eventos de abandono (cart.abandonment)
- [ ] Verificar formato do payload (pode ser diferente)
- [ ] Atualizar código se necessário
- [ ] Manter ambos webhooks ativos por período de teste
- [ ] Desativar webhook antigo após confirmação
- [ ] Documentar mudanças

---

## Referências

- [Developer Hub Eduzz](https://developer.eduzz.com)
- [Documentação de Webhooks](https://developer.eduzz.com/docs/webhooks)


