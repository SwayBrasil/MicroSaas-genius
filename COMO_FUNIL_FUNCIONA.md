# 🎯 Como o Sistema de Funis Funciona Atualmente

## 📊 Situação Atual

### ✅ O que JÁ está funcionando:

1. **Armazenamento do Funil/Etapa:**
   - Os campos `funnel_id` e `stage_id` são salvos no campo `meta` (JSON) da thread
   - Podem ser salvos manualmente via tela de Contatos > Ações > Forçar Etapa
   - Podem ser atualizados automaticamente via `next_stage` na resposta da IA

2. **Detecção Automática Inicial:**
   - Quando uma nova mensagem chega via webhook, o sistema detecta qual funil usar baseado na mensagem
   - Arquivo: `api/app/services/funnel_detector.py`
   - Detecta keywords como "life", "black friday", "50%", etc.

3. **Atualização de Etapa:**
   - A IA pode retornar `next_stage` na resposta JSON
   - O `response_processor.py` atualiza o `stage_id` automaticamente quando recebe `next_stage`

4. **Visualização no Frontend:**
   - Tela de Kanban mostra os funis com suas etapas
   - Contatos aparecem na etapa correta baseado no `stage_id`
   - É possível mover contatos entre etapas manualmente

### ❌ O que NÃO está funcionando (PROBLEMA):

**A IA não recebe informações sobre o funil/etapa atual nas instruções!**

Atualmente:
- A IA só recebe: histórico de mensagens + mensagem atual
- A IA NÃO recebe: `funnel_id`, `stage_id`, informações sobre qual etapa está

Isso significa:
- A IA não sabe em qual etapa do funil o contato está
- A IA não sabe quais áudios/templates já foram enviados
- A IA não consegue tomar decisões baseadas no contexto do funil
- A IA precisa "adivinhar" qual áudio enviar baseado apenas no histórico de mensagens

## 🔧 Como Funciona Atualmente (Fluxo)

```
1. Mensagem chega via WhatsApp
   ↓
2. Webhook detecta funil inicial (funnel_detector.py)
   - Salva funnel_id e stage_id no meta da thread
   ↓
3. Sistema chama run_llm()
   - PASSA: histórico de mensagens + mensagem atual
   - NÃO PASSA: funnel_id, stage_id, etapa atual
   ↓
4. IA decide qual áudio enviar baseado apenas no histórico
   - Precisa "adivinhar" qual etapa está
   - Retorna JSON com audio_id e next_stage
   ↓
5. response_processor.py processa a resposta
   - Se next_stage existe, atualiza stage_id no meta
   - Envia áudio/template via WhatsApp
```

## 🚨 Problema Principal

A IA está "cega" sobre o contexto do funil. Ela precisa:
- Ler todo o histórico para tentar descobrir qual etapa está
- Não tem acesso às configurações do funil (condições, ações, etc.)
- Não sabe quais etapas existem no funil atual

## 💡 Solução Necessária

Para a IA saber onde está no funil, precisamos:

1. **Passar informações do funil nas instruções do sistema:**
   - Adicionar `funnel_id` e `stage_id` atual da thread
   - Adicionar informações sobre a etapa atual (nome, fase, áudio, etc.)
   - Adicionar informações sobre próximas etapas possíveis

2. **Modificar `run_llm()` para receber contexto do funil:**
   ```python
   async def run_llm(
       message: str,
       thread_history: Optional[List[Dict[str, str]]] = None,
       takeover: bool = False,
       thread_id: Optional[int] = None,  # NOVO
       db_session: Optional[Session] = None,  # NOVO
   ) -> Optional[str]:
   ```

3. **Adicionar contexto do funil nas instruções do sistema:**
   ```python
   # Buscar thread e funil atual
   if thread_id and db_session:
       thread = db_session.get(Thread, thread_id)
       funnel_id = thread.meta.get("funnel_id") if thread.meta else None
       stage_id = thread.meta.get("stage_id") if thread.meta else None
       
       # Buscar informações do funil
       if funnel_id:
           funnel_info = get_funnel_info(funnel_id)
           current_stage = get_stage_info(funnel_id, stage_id)
           
           # Adicionar ao system prompt
           system_content += f"""
   
   ## 📍 CONTEXTO DO FUNIL ATUAL
   
   Você está no funil: {funnel_info.name}
   Etapa atual: {current_stage.name} (Etapa {current_stage.order})
   Fase: {current_stage.phase}
   
   Áudio desta etapa: {current_stage.audio_id}
   Próximas etapas possíveis: {next_stages}
   """
   ```

4. **Carregar definições dos funis no backend:**
   - Criar `api/app/services/funnel_service.py`
   - Carregar `INITIAL_FUNNELS` do arquivo ou banco de dados
   - Fornecer funções para buscar funil/etapa atual

## 📝 Próximos Passos Sugeridos

1. ✅ Criar serviço de funis no backend
2. ✅ Modificar `run_llm()` para receber `thread_id` e buscar contexto
3. ✅ Adicionar contexto do funil no system prompt
4. ✅ Testar com diferentes funis e etapas
5. ✅ Documentar no `agent_instructions.txt` como usar o contexto do funil

## 🔍 Arquivos Relevantes

- `api/app/services/llm_service.py` - Chama a IA (precisa ser modificado)
- `api/app/main.py` - Endpoint que chama run_llm (precisa passar thread_id)
- `api/app/services/funnel_detector.py` - Detecta funil inicial
- `api/app/services/response_processor.py` - Processa resposta da IA
- `api/app/agent_instructions.txt` - Instruções para a IA
- `frontend/src/data/funnels.ts` - Definições dos funis (frontend)



