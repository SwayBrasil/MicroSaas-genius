# 🧪 TESTES DO FUNIL - CASOS DE USO

## 📋 Tabela de Testes

| # | Mensagem de Entrada | Fase Esperada | Resposta Exata Esperada | Status |
|---|---------------------|---------------|-------------------------|--------|
| 1 | "Ooi Paloma, Preciso fazer algo por mim mesma! 🔥 Quero saber como funciona o Life e como me tornarei uma grande gostosa... 🩷✨" | **FASE 1** | `[Áudio enviado: audio1_boas_vindas]`<br><br>Entendo totalmente, gata. Às vezes, a alimentação faz toda a diferença, né? Me conta aqui: o que você acha que está pegando na sua dieta? Me conta um pouco mais sobre como está sua relação com a comida! ✨<br><br>Sei como é difícil manter a determinação, gata! Aqui no LIFE você não vai ficar sozinha. Temos uma comunidade super ativa que vai te apoiar. 💖<br><br>Faz assim: que tal dar uma chance pra gente te ajudar? Vou te mostrar como funciona? ✨ | ⚠️ FALHOU |
| 2 | "Oi Paloma" | **FASE 1** | `[Áudio enviado: audio1_boas_vindas]`<br><br>Entendo totalmente, gata. Às vezes, a alimentação faz toda a diferença, né? Me conta aqui: o que você acha que está pegando na sua dieta? Me conta um pouco mais sobre como está sua relação com a comida! ✨<br><br>Sei como é difícil manter a determinação, gata! Aqui no LIFE você não vai ficar sozinha. Temos uma comunidade super ativa que vai te apoiar. 💖<br><br>Faz assim: que tal dar uma chance pra gente te ajudar? Vou te mostrar como funciona? ✨ | ⏳ PENDENTE |
| 3 | "Eae" | **FASE 1** | `[Áudio enviado: audio1_boas_vindas]`<br><br>Entendo totalmente, gata. Às vezes, a alimentação faz toda a diferença, né? Me conta aqui: o que você acha que está pegando na sua dieta? Me conta um pouco mais sobre como está sua relação com a comida! ✨<br><br>Sei como é difícil manter a determinação, gata! Aqui no LIFE você não vai ficar sozinha. Temos uma comunidade super ativa que vai te apoiar. 💖<br><br>Faz assim: que tal dar uma chance pra gente te ajudar? Vou te mostrar como funciona? ✨ | ⏳ PENDENTE |
| 4 | "Quero saber como funciona o Life" | **FASE 1** | `[Áudio enviado: audio1_boas_vindas]`<br><br>Entendo totalmente, gata. Às vezes, a alimentação faz toda a diferença, né? Me conta aqui: o que você acha que está pegando na sua dieta? Me conta um pouco mais sobre como está sua relação com a comida! ✨<br><br>Sei como é difícil manter a determinação, gata! Aqui no LIFE você não vai ficar sozinha. Temos uma comunidade super ativa que vai te apoiar. 💖<br><br>Faz assim: que tal dar uma chance pra gente te ajudar? Vou te mostrar como funciona? ✨ | ⏳ PENDENTE |
| 5 | "Quero saber como funciona o Life. Quanto custa?" | **FASE 3** | `Amo essa atitude! Vou te mandar um áudio explicando os planos agora 💪🔥`<br><br>`[Áudio enviado: audio3_explicacao_planos]`<br><br>✅ Plano Mensal – R$69,90/mês<br>• Acesso à base do LIFE: treinos, planos alimentares, aulas sobre disciplina e motivação.<br>• Pode cancelar quando quiser.<br><br>🔥Plano Anual – R$598,80 (ou 12x de R$49,90)<br>• Acesso COMPLETO a tudo no LIFE: treinos, planos alimentares, aulas extras com médicas, nutricionistas e psicólogas.<br>• Inclui o módulo exclusivo do Shape Slim.<br>• Pode ser parcelado em até 12x sem comprometer o limite do cartão.<br><br>Agora me fala, gata: qual plano faz mais sentido pra você? 💬🔥 | ⏳ PENDENTE |
| 6 | "Quero saber dos planos e preços" | **FASE 3** | `Amo essa atitude! Vou te mandar um áudio explicando os planos agora 💪🔥`<br><br>`[Áudio enviado: audio3_explicacao_planos]`<br><br>✅ Plano Mensal – R$69,90/mês<br>• Acesso à base do LIFE: treinos, planos alimentares, aulas sobre disciplina e motivação.<br>• Pode cancelar quando quiser.<br><br>🔥Plano Anual – R$598,80 (ou 12x de R$49,90)<br>• Acesso COMPLETO a tudo no LIFE: treinos, planos alimentares, aulas extras com médicas, nutricionistas e psicólogas.<br>• Inclui o módulo exclusivo do Shape Slim.<br>• Pode ser parcelado em até 12x sem comprometer o limite do cartão.<br><br>Agora me fala, gata: qual plano faz mais sentido pra você? 💬🔥 | ⏳ PENDENTE |
| 7 | "Quero emagrecer" (após áudio 1) | **FASE 2** | `[Áudio enviado: audio2_dor_generica]`<br><br>`[Imagem enviada: img_resultado_01]`<br>`[Imagem enviada: img_resultado_02]`<br>`[Imagem enviada: img_resultado_03]`<br>`[Imagem enviada: img_resultado_04]`<br>`[Imagem enviada: img_resultado_05]`<br>`[Imagem enviada: img_resultado_06]`<br>`[Imagem enviada: img_resultado_07]`<br>`[Imagem enviada: img_resultado_08]`<br><br>Me conta aqui, gata, o que tá faltando pra tu dar esse passo? 👯‍♀️✨ | ⏳ PENDENTE |
| 8 | "Minha barriga incomoda" (após áudio 1) | **FASE 2** | `[Áudio enviado: audio2_dor_generica]`<br><br>`[Imagem enviada: img_resultado_01]`<br>`[Imagem enviada: img_resultado_02]`<br>`[Imagem enviada: img_resultado_03]`<br>`[Imagem enviada: img_resultado_04]`<br>`[Imagem enviada: img_resultado_05]`<br>`[Imagem enviada: img_resultado_06]`<br>`[Imagem enviada: img_resultado_07]`<br>`[Imagem enviada: img_resultado_08]`<br><br>Me conta aqui, gata, o que tá faltando pra tu dar esse passo? 👯‍♀️✨ | ⏳ PENDENTE |
| 9 | "Tô sem tempo" (após fase 2) | **FASE 3** | Quebra objeção + "Perfeitaaaa, posso te explicar melhor sobre os planos?" | ⏳ PENDENTE |
| 10 | "Sim" (após fase 3) | **FASE 4** | `Amo essa atitude! Vou te mandar um áudio explicando os planos agora 💪🔥`<br><br>`[Áudio enviado: audio3_explicacao_planos]`<br><br>✅ Plano Mensal – R$69,90/mês<br>• Acesso à base do LIFE: treinos, planos alimentares, aulas sobre disciplina e motivação.<br>• Pode cancelar quando quiser.<br><br>🔥Plano Anual – R$598,80 (ou 12x de R$49,90)<br>• Acesso COMPLETO a tudo no LIFE: treinos, planos alimentares, aulas extras com médicas, nutricionistas e psicólogas.<br>• Inclui o módulo exclusivo do Shape Slim.<br>• Pode ser parcelado em até 12x sem comprometer o limite do cartão.<br><br>Agora me fala, gata: qual plano faz mais sentido pra você? 💬🔥 | ⏳ PENDENTE |
| 11 | "Quero o anual" (após fase 4) | **FASE 5** | `*Amoo!🔥 Bora garantir sua transformação agoraaaa!!*`<br><br>Aqui está o link pra você finalizar:<br><br>➡️ https://edzz.la/DO408?a=10554737<br><br>_💳 Antes de comprar, ajusta o limite do cartão pra R$50 só uma vez. O sistema cobra só a parcela mensal._<br><br>Assim que finalizar, me avisa que já te envio todos os acessos... Fico te esperando aqui!! | ⏳ PENDENTE |
| 12 | "Quero o mensal" (após fase 4) | **FASE 5** | `*🔥 Bora garantir sua transformação agoraaaa!!*`<br><br>Aqui tá o link do mensal pra você finalizar:<br><br>➡️ https://edzz.la/GQRLF?a=10554737<br><br>Assim que finalizar, me avisa que já te envio todos os acessos... Fico te esperando aqui!! | ⏳ PENDENTE |

---

## 🔍 Checklist de Validação

Para cada teste, verificar:

- [ ] **Áudio enviado?** (quando obrigatório)
- [ ] **Texto exato?** (sem reescrever)
- [ ] **Ordem correta?** (áudio → texto 1 → texto 2)
- [ ] **Fase correta?** (detecção de gatilho)
- [ ] **Formatação?** (linhas em branco entre blocos)

---

## 🐛 Casos de Erro Conhecidos

### ❌ Erro #1: IA não enviou áudio na Fase 1
**Caso:** Teste #1
**Problema:** IA respondeu texto sem enviar `[Áudio enviado: audio1_boas_vindas]`
**Correção:** Adicionada regra imutável no prompt

### ❌ Erro #2: IA reescreveu texto da Fase 1
**Caso:** Teste #1
**Problema:** IA mudou "alimentação faz toda a diferença" para "dar esse passo pra cuidar de si"
**Correção:** Template fixo adicionado com regras absolutas

---

## 📝 Como Usar Este Documento

1. **Testes Manuais:** Use a tabela acima para testar manualmente no WhatsApp
2. **Testes Automatizados:** Use os casos como base para unit tests
3. **Validação:** Marque ✅ quando passar, ❌ quando falhar
4. **Registro:** Anote observações em cada teste

---

## 🎯 Próximos Testes a Adicionar

- [ ] Testes de objeções (tempo, dinheiro, disciplina)
- [ ] Testes de follow-ups
- [ ] Testes de carrinho abandonado
- [ ] Testes do Mini Funil BF
- [ ] Testes de edge cases (mensagens vazias, emojis, etc.)

