# 🔄 Fluxo: "Forçar Etapa"

## O que acontece quando você clica em "Forçar etapa"

### 1. **Frontend - Abertura do Modal**
- Usuário clica no botão "Forçar etapa" na linha do contato
- Modal abre mostrando:
  - Nome do contato
  - Dropdown para selecionar **Funil**
  - Dropdown para selecionar **Etapa** (habilitado após selecionar funil)

### 2. **Frontend - Seleção**
- Usuário seleciona um **Funil** (ex: "Funil Longo (LIFE)")
- Dropdown de **Etapa** é habilitado
- Usuário seleciona uma **Etapa** (ex: "Boas-vindas e Qualificação")
- Botão "Salvar" fica habilitado

### 3. **Frontend - Ao Clicar em "Salvar"**
```typescript
// Código em Contacts.tsx (linha ~1078)
async function handleForceStage() {
  // 1. Valida se tem thread, funil e etapa selecionados
  if (!thread || !forceStageFunnel || !forceStageStage) return;
  
  // 2. Ativa estado de "salvando"
  setSavingStage(true);
  
  try {
    // 3. Pega o metadata atual (para não perder outros dados)
    const currentMeta = (thread as any).metadata || {};
    
    // 4. Faz requisição PATCH para atualizar a thread
    await updateThread(thread.id, { 
      metadata: {
        ...currentMeta,  // Preserva dados existentes
        funnel_id: forceStageFunnel,  // Novo funil
        stage_id: forceStageStage,    // Nova etapa
      }
    });
    
    // 5. Atualiza o estado local (UI)
    setRows(prev => prev.map(r => {
      if (r.id === thread.id) {
        const updatedMeta = { 
          ...((r as any).metadata || {}), 
          funnel_id: forceStageFunnel, 
          stage_id: forceStageStage 
        };
        return { 
          ...r, 
          metadata: updatedMeta, 
          funnel_id: forceStageFunnel, 
          stage_id: forceStageStage 
        };
      }
      return r;
    }));
    
    // 6. Fecha o modal e limpa os campos
    setShowForceStageModal(null);
    setForceStageFunnel("");
    setForceStageStage("");
  } catch (error) {
    console.error("Erro ao atualizar etapa:", error);
    alert("Falha ao atualizar etapa.");
  } finally {
    setSavingStage(false);
  }
}
```

### 4. **Backend - Recebe a Requisição**
```python
# Código em main.py (linha ~984)
@app.patch("/threads/{thread_id}")
def update_thread_endpoint(thread_id: int, body: ThreadUpdate, ...):
    # 1. Busca a thread no banco
    t = db.query(Thread).filter(Thread.id == thread_id).first()
    
    # 2. Se recebeu metadata, mescla com o existente
    if body.metadata is not None:
        if isinstance(body.metadata, dict) and isinstance(t.meta, dict):
            # Mescla (não sobrescreve tudo)
            t.meta = {**(t.meta or {}), **body.metadata}
        else:
            t.meta = body.metadata
    
    # 3. Salva no banco
    db.add(t)
    db.commit()
    db.refresh(t)
    
    # 4. Retorna a thread atualizada
    return _serialize_thread(t, db)
```

### 5. **Backend - Serialização da Resposta**
```python
# Código em main.py (linha ~853)
def _serialize_thread(t: Thread, db: Session = None) -> dict:
    # Extrai metadata
    meta = getattr(t, "meta", None)
    meta_dict = {}
    if meta:
        if isinstance(meta, dict):
            meta_dict = meta
        elif isinstance(meta, str):
            meta_dict = json.loads(meta)
    
    return {
        "id": t.id,
        # ... outros campos ...
        "metadata": meta_dict,  # Metadata completo
        # Campos achatados (para facilitar acesso no frontend)
        "funnel_id": meta_dict.get("funnel_id") if meta_dict else None,
        "stage_id": meta_dict.get("stage_id") if meta_dict else None,
        "product_id": meta_dict.get("product_id") if meta_dict else None,
        "source": meta_dict.get("source") if meta_dict else None,
        "tags": meta_dict.get("tags") if meta_dict else None,
    }
```

### 6. **Frontend - Atualização da UI**
- A tabela de contatos é atualizada automaticamente
- A coluna "Funil/Etapa" mostra o novo valor
- A coluna "Status de Automação" pode mudar (se o funil foi definido)
- O modal fecha

---

## 📊 Onde os dados são armazenados?

### **No Banco de Dados (PostgreSQL)**
- Tabela: `threads`
- Coluna: `meta` (tipo JSON)
- Exemplo:
```json
{
  "funnel_id": "1",
  "stage_id": "1",
  "product_id": "1",
  "source": "WhatsApp orgânico",
  "tags": ["quente", "interessado"]
}
```

### **No Frontend**
- Estado: `rows` (array de threads)
- Cada thread tem:
  - `metadata` (objeto completo)
  - `funnel_id` (campo achatado, vem do backend)
  - `stage_id` (campo achatado, vem do backend)
  - etc.

---

## ⚠️ Possíveis Problemas

### 1. **"Contato não encontrado"**
- **Causa:** O `thread.id` não está sendo encontrado no array `rows`
- **Solução:** Verificar se o ID está correto (comparação de tipos string vs number)

### 2. **Campos não aparecem após salvar**
- **Causa:** O backend não está retornando os campos achatados
- **Solução:** Verificar se `_serialize_thread()` está retornando `funnel_id` e `stage_id`

### 3. **Erro ao salvar**
- **Causa:** Erro na requisição ou no backend
- **Solução:** Verificar logs do console e do backend

---

## 🔍 Como Debugar

1. **Abra o Console do Navegador (F12)**
2. **Clique em "Forçar etapa"**
3. **Veja os logs:**
   - `[DEBUG] Thread no modal:` - mostra o objeto thread
   - `[DEBUG] Thread ID:` - mostra os IDs
   - `[DEBUG] Funnel ID:` - mostra se encontrou funnel_id

4. **Verifique a Requisição:**
   - Aba Network → Filtre por "threads"
   - Veja a requisição PATCH
   - Verifique o payload enviado
   - Verifique a resposta recebida

5. **Verifique o Backend:**
   - Logs do Docker: `docker-compose logs api`
   - Procure por erros ou warnings

---

## ✅ Resultado Esperado

Após clicar em "Salvar":
1. ✅ Modal fecha
2. ✅ Tabela atualiza mostrando o novo "Funil/Etapa"
3. ✅ Status de automação pode mudar
4. ✅ Dados são salvos no banco
5. ✅ Próxima vez que abrir o modal, mostra os valores corretos

