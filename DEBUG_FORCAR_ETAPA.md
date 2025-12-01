# 🔍 Debug: Forçar Etapa

## O que foi melhorado

### 1. **Logs de Debug Adicionados**
- Console.log em cada etapa do processo
- Mostra valores selecionados
- Mostra erros completos

### 2. **Validação Melhorada**
- Verifica se thread existe
- Verifica se funil foi selecionado
- Verifica se etapa foi selecionada
- Mostra mensagens de erro mais claras

### 3. **Feedback Visual**
- Mostra qual funil/etapa está selecionado
- Mostra se há etapas disponíveis
- Botão desabilitado com feedback visual

### 4. **Recarregamento Automático**
- Após salvar, recarrega a lista de threads
- Garante que a UI está sincronizada com o backend

---

## Como debugar

### 1. **Abra o Console do Navegador (F12)**

### 2. **Clique em "Forçar etapa"**
Você deve ver:
```
[FORÇAR ETAPA] Funil selecionado: 1
[FORÇAR ETAPA] Etapa selecionada: 2
```

### 3. **Clique em "Salvar"**
Você deve ver:
```
[FORÇAR ETAPA] Botão Salvar clicado { thread: true, forceStageFunnel: "1", forceStageStage: "2", savingStage: false }
[FORÇAR ETAPA] Iniciando atualização: { threadId: 1, funnelId: "1", stageId: "2" }
[FORÇAR ETAPA] Metadata atual: { ... }
[FORÇAR ETAPA] Metadata novo: { ... }
[FORÇAR ETAPA] Thread atualizada: { ... }
```

### 4. **Se houver erro**
Você verá:
```
[FORÇAR ETAPA] Erro completo: Error: ...
```

---

## Problemas Comuns

### **"Contato não encontrado"**
- **Causa:** Thread ID não está sendo encontrado no array `rows`
- **Solução:** Verifique se o ID do thread está correto no console

### **"Nenhuma etapa disponível"**
- **Causa:** Funil selecionado não tem etapas ou ID não corresponde
- **Solução:** Verifique se o funil tem etapas em `INITIAL_FUNNELS`

### **"Falha ao atualizar etapa"**
- **Causa:** Erro na requisição ou no backend
- **Solução:** 
  1. Veja o erro completo no console
  2. Verifique os logs do backend: `docker-compose logs api | grep PATCH`

### **Valores não aparecem após salvar**
- **Causa:** Estado local não está sendo atualizado
- **Solução:** 
  1. Verifique se a requisição foi bem-sucedida (200 OK)
  2. Recarregue a página
  3. Verifique se os dados estão no banco

---

## Verificar no Backend

```bash
# Ver logs da requisição PATCH
docker-compose logs api | grep "PATCH /threads"

# Ver se os dados foram salvos
docker-compose exec db psql -U postgres -d sway -c "SELECT id, meta FROM threads WHERE id = <thread_id>;"
```

---

## Teste Completo

1. ✅ Abra a página de Contatos
2. ✅ Clique em "Forçar etapa" em um contato
3. ✅ Selecione um funil
4. ✅ Selecione uma etapa
5. ✅ Clique em "Salvar"
6. ✅ Verifique o console para logs
7. ✅ Verifique se a tabela foi atualizada
8. ✅ Recarregue a página e verifique se persiste

