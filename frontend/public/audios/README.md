# 🎧 Áudios do LIFE – Organização por Funil



Este diretório contém **todos os áudios usados nos funis da Paloma (LIFE)**, já organizados por fluxo.



## Estrutura



- `funil-longo/` → Funil principal (entrada → diagnóstico → planos → recuperação)

- `mini-funil-bf/` → Mini funil de Black Friday (promoção específica)

- `recuperacao-50/` → Funil de recuperação com 50% de desconto (pós-plataforma)



---



## 1. Funil Longo (`public/audios/funil-longo`)



### `01-boas-vindas-qualificacao.opus`

- **Uso:** primeiro áudio quando a lead chama querendo saber do LIFE.

- **Etapa:** Fase 1 – Lead Frio.

- **Sugestão de texto junto:**

  > Perfeitaaa, me conta qual é seu objetivo hoje? 🔥✨  

  > O que você mais quer transformar no seu corpo agora?



### `02-dor-generica.opus`

- **Uso:** resposta às dores/objetivos que a lead contou (emagrecer, ganhar massa, pochete, flacidez, autoestima, composição corporal).

- **Etapa:** Fase 2 – Aquecimento.

- **Obs.:** No futuro, este áudio pode ser dividido em 5 versões, cada uma focada em uma dor específica.

- **Sugestão de texto junto (após enviar provas sociais):**

  > Me conta aqui gata, o que tá faltando pra tu dar esse passo? 👯‍♀️✨



### `03-explicacao-planos.opus`

- **Uso:** quando a lead aceita ouvir sobre os planos ("Claro, quero saber mais").

- **Etapa:** Fase 3 – Aquecida.

- **Sugestão:** depois do áudio, enviar o conteúdo de `public/templates/planos-life.json` (mensal+anual) e a pergunta:

  > Agora me fala, gata: qual plano faz mais sentido pra você? 💬🔥



### `04-recuperacao-pos-nao-compra.opus`

- **Uso:** recuperação quando a pessoa não finalizou a compra após receber o link.

- **Etapa:** Fase 4 – Quente → Recuperação.

- **Gatilho sugerido:** não houve webhook de compra em X minutos / lead sumiu.

- **Sugestão de texto junto:**

  > Gataaa, vi aqui que você começou o processo mas não concluiu ainda…  

  > Se rolou alguma dúvida ou receio, me conta! Quero te ajudar a não perder essa chance 💖✨



---



## 2. Mini Funil Black Friday (`public/audios/mini-funil-bf`)



### `01-oferta-black-friday.opus`

- **Uso:** primeiro áudio do mini funil de Black Friday, disparado pra leads aquecidas.

- **Sugestão de texto junto:**

  > Gataaaaa, olha issoooo 🔥🔥🔥  

  > Saiu uma condição INSANA da Black Friday, só HOJE!!  

  > Quer saber como funciona pra você aproveitar?



### `02-followup-sem-resposta.opus`

- **Uso:** follow-up automático se ela não responde ao áudio da BF dentro do tempo configurado.

- **Sugestão de texto junto:**

  > Só passando aqui rapidinho porque essa promoção é literalmente a mais forte do ano 🔥  

  > Se ainda fizer sentido pra você, me chama aqui que te explico antes de acabar!



---



## 3. Recuperação 50% (`public/audios/recuperacao-50`)



### `02-audio-followup.opus`

- **Uso:** segundo passo do funil de recuperação 50%. Disparado se ela não responder ao texto de oferta (arquivo `recuperacao-50-oferta.txt`).

- **Sugestão de texto junto:**

  > Te mandei uma condição muito especial pro LIFE e não queria que passasse batido por você, gata. 💖  

  > Me chama aqui se ainda tiver vontade de aproveitar essa oportunidade!



### `03-audio-ultimo-chamado.opus`

- **Uso:** último contato dessa sequência de 50% de desconto, caso ela não responda o áudio anterior.

- **Sugestão de texto junto:**

  > Prometo que é a última vez que apareço aqui sobre essa condição 🙈  

  > Se ainda bater aquela vontade de começar sua transformação com 50% OFF, é agora ou só na próxima… 😅🔥



---



Qualquer áudio novo deve seguir o padrão:



- `NN-descricao-curta.opus`

- Documentado aqui com:

  - Quando usar

  - Em qual etapa do funil

  - Texto sugerido que acompanha
