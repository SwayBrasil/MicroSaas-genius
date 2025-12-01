# 🌐 Pasta `public/` – LIFE x Sway



Aqui ficam todos os **assets públicos** usados pela aplicação (frontend + automações):



- áudios dos funis (LIFE)

- imagens de prova social

- templates de texto (mensagens prontas que a IA envia)



## Estrutura Geral



- `audios/`

  - `funil-longo/`

  - `mini-funil-bf/`

  - `recuperacao-50/`

  - `README.md`

- `images/`

  - `prova-social/`

  - `templates/`

  - `README.md`

- `templates/`

  - `planos-life.json`

  - `fechamento-anual.txt`

  - `fechamento-mensal.txt`

  - `pos-compra-life.txt`

  - `recuperacao-50-oferta.txt`

  - `README.md` (opcional)



## Como o sistema usa isso



- O **backend** e/ou a **IA** apenas precisam saber o **caminho do arquivo**.

- As automações podem ser configuradas assim:

  - Funil Longo:

    - Entrada → áudio `funil-longo/01-boas-vindas-qualificacao.opus`

    - Dor → áudio `funil-longo/02-dor-generica.opus` + imagens `images/prova-social/*`

    - Planos → áudio `funil-longo/03-explicacao-planos.opus` + texto `templates/planos-life.json`

    - Fechamento → texto `fechamento-anual.txt` ou `fechamento-mensal.txt`

    - Pós-compra → `pos-compra-life.txt`

  - Mini funil BF:

    - Oferta → `mini-funil-bf/01-oferta-black-friday.opus`

    - Follow-up → `mini-funil-bf/02-followup-sem-resposta.opus`

  - Recuperação 50%:

    - Texto inicial → `recuperacao-50-oferta.txt`

    - Follow-ups de áudio → `recuperacao-50/02-audio-followup.opus` e `recuperacao-50/03-audio-ultimo-chamado.opus`



Assim, o MVP já fica com a "base de conteúdo" pronta, e você só precisa plugar as regras de automação e os webhooks.
