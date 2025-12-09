# Como Sincronizar Produtos da Eduzz

## Opção 1: Via API (Recomendado - Mais Rápido)

### Usando cURL:

```bash
curl -X POST "http://localhost:8000/billing/products/eduzz/sync-all" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

### Usando o navegador (Swagger UI):

1. Acesse: http://localhost:8000/docs
2. Faça login primeiro (clique em "Authorize" e insira suas credenciais)
3. Procure pelo endpoint: `POST /billing/products/eduzz/sync-all`
4. Clique em "Try it out" → "Execute"
5. Verá a resposta com todos os produtos sincronizados

### Usando Postman/Insomnia:

- **Método**: POST
- **URL**: `http://localhost:8000/billing/products/eduzz/sync-all`
- **Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer SEU_TOKEN_JWT`
- **Body**: (vazio)

---

## Opção 2: Via Frontend (Interface Visual)

1. Acesse: http://localhost:3000
2. Faça login
3. Vá para a página de **Produtos** (menu lateral)
4. Adicione um botão "Sincronizar Produtos Eduzz" (pode ser implementado)

---

## Opção 3: Via Script Python (Para Desenvolvedores)

```bash
# Dentro do container da API
docker exec -it infra-api-1 python -m app.scripts.sync_eduzz_products
```

Ou diretamente:

```bash
cd /Users/macos/MicroSaas-genius
python -m api.app.scripts.sync_eduzz_products
```

---

## Opção 4: Adicionar Produtos Individualmente

### Via API:

```bash
curl -X POST "http://localhost:8000/billing/products/eduzz" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -d '{
    "product_id": "2457307",
    "title": "ACESSO MENSAL - LIFE 2025",
    "status": "active"
  }'
```

### Adicionar Múltiplos de Uma Vez:

```bash
curl -X POST "http://localhost:8000/billing/products/eduzz/bulk" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer SEU_TOKEN_JWT" \
  -d '[
    {
      "product_id": "2457307",
      "title": "ACESSO MENSAL - LIFE 2025",
      "status": "active"
    },
    {
      "product_id": "2562423",
      "title": "LIFE ACESSO ANUAL - 2 ANOS",
      "status": "active"
    }
  ]'
```

---

## Como Obter o Token JWT

### Opção A: Via Frontend
1. Acesse http://localhost:3000
2. Faça login
3. Abra o DevTools (F12)
4. Vá em Application/Storage → Local Storage
5. Procure por `token` ou `auth_token`

### Opção B: Via API de Login

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@local.com",
    "password": "123"
  }'
```

A resposta terá o token no campo `access_token`.

---

## Verificar Produtos Sincronizados

### Listar Todos os Produtos:

```bash
curl -X GET "http://localhost:8000/billing/products" \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

### Listar Apenas Produtos da Eduzz:

```bash
curl -X GET "http://localhost:8000/billing/products?source=eduzz" \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

---

## Resposta Esperada

Ao sincronizar, você receberá algo como:

```json
{
  "products": [
    {
      "id": 1,
      "external_product_id": "2457307",
      "title": "ACESSO MENSAL - LIFE 2025",
      "type": null,
      "status": "active",
      "source": "eduzz"
    },
    ...
  ],
  "summary": {
    "created": 15,
    "updated": 0,
    "total": 15
  }
}
```

---

## Produtos que Serão Sincronizados

1. 2382728 - ACESSO MENSAL - LIFE MÉTODO PLM - 0404
2. 2382997 - ACESSO MENSAL - LIFE MÉTODO PLM - 1102
3. 2352153 - ACESSO MENSAL - LIFE MÉTODO PLM 01
4. 2455207 - CARTÃO DE VISITAS TECNOLÓGICO.
5. 2109729 - DESAFIO 28 DIAS PALOMA MORAES
6. 2180340 - DESAFIO 28 DIAS PALOMA MORAES - DEZEMBRO 2023
7. 2108559 - DESAFIO 28 DIAS PALOMA MORAES - OFERTA EXCLUSIVA
8. 2184785 - Desafio Completo de 28 Dias Com Paloma Moraes - Edição Dezembro 2023
9. 2562423 - LIFE ACESSO ANUAL - 2 ANOS
10. 2562393 - LIFE ACESSO MENSAL
11. 2571885 - LIFE VITALÍCIO - 2025
12. 2681898 - LIFE VITALÍCIO - 2025x
13. 2455378 - MENTORIA EXCLUSIVA
14. 2459386 - MENTORIA EXCLUSIVA + 9 MESES
15. 2124224 - OFERTA RELÂMPAGO - DESAFIO 28 DIAS PALOMA MORAES
16. 2457307 - ACESSO MENSAL - LIFE 2025

---

## Troubleshooting

### Erro 401 (Não autenticado):
- Verifique se o token JWT está correto
- Faça login novamente

### Erro 500 (Erro interno):
- Verifique os logs: `docker compose -f infra/docker-compose.yml logs api`
- Verifique se o banco de dados está rodando

### Produtos não aparecem:
- Verifique se a sincronização foi bem-sucedida (veja o `summary`)
- Tente listar produtos: `GET /billing/products?source=eduzz`


