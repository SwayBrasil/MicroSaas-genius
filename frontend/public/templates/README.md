# 📝 Templates de Mensagens do LIFE

Esta pasta contém todos os **templates de texto** usados nos funis de automação do LIFE.

## Arquivos

### `planos-life.json`
Template JSON com a descrição dos planos (Mensal e Anual).
- **Uso:** Enviado após o áudio de explicação dos planos (`03-explicacao-planos.opus`)
- **Formato:** JSON com campos `texto` (mensagem formatada) e `pergunta_final`
- **Code name:** `life_funil_longo_planos`

### `fechamento-anual.txt`
Mensagem de fechamento para o Plano Anual com link de compra.
- **Uso:** Enviado quando a lead escolhe o plano anual
- **Link:** `https://edzz.la/DO408?a=10554737`
- **Code name:** `life_funil_longo_plano_anual`

### `fechamento-mensal.txt`
Mensagem de fechamento para o Plano Mensal com link de compra.
- **Uso:** Enviado quando a lead escolhe o plano mensal
- **Link:** `https://edzz.la/GQRLF?a=10554737`
- **Code name:** `life_funil_longo_plano_mensal`

### `pos-compra-life.txt`
Mensagem de boas-vindas pós-compra com links de acesso.
- **Uso:** Enviado após webhook de compra confirmada (Eduzz)
- **Placeholders:** `[NOME]` e `[LINK PERSONALIZADO]` devem ser substituídos dinamicamente
- **Code name:** `life_pos_compra`

### `recuperacao-50-oferta.txt`
Oferta de 50% de desconto para leads que não concluíram a compra.
- **Uso:** Primeira mensagem do funil de recuperação pós-plataforma
- **Code name:** `life_recuperacao_50_01_texto_oferta_50`

---

## Como usar no código

O backend carrega os templates através de `template_loader.py`:

```python
from app.services.template_loader import get_template_by_code

# Carregar template
template_text = get_template_by_code("life_funil_longo_planos")
```

Os templates são buscados primeiro em `public/templates/` e depois em `public/images/templates/` (compatibilidade).



