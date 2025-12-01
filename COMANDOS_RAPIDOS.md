# 🚀 Comandos Rápidos para Testar

## ⚠️ IMPORTANTE: Execute os comandos da RAIZ do projeto

Se você estiver na pasta `infra`, volte para a raiz:
```bash
cd /Users/macos/MicroSaas-Sway
```

## 1️⃣ Iniciar Docker Desktop
- Abra o aplicativo "Docker Desktop" no seu Mac
- Aguarde até o ícone ficar verde

## 2️⃣ Iniciar Serviços

### Opção A - Script automático:
```bash
cd /Users/macos/MicroSaas-Sway
./start-dev.sh
```

### Opção B - Comando manual:
```bash
cd /Users/macos/MicroSaas-Sway
docker compose -f infra/docker-compose.yml up --build
```

## 3️⃣ Acessar
- Frontend: http://localhost:3000
- Login: dev@local.com / 123

## 4️⃣ Testar
1. Vá para "Contatos"
2. Clique em "➕ Adicionar Contato"
3. Preencha telefone: `+5561999999999`
4. (Opcional) Nome e mensagem inicial
5. Clique em "Criar e Abrir Chat"

## Parar os serviços
```bash
docker compose -f infra/docker-compose.yml down
```
