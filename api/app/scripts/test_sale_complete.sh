#!/bin/bash

# Script completo para testar compra: cria thread + simula compra
# Uso: ./test_sale_complete.sh <email> <telefone> [plano]
# Exemplo: ./test_sale_complete.sh teste@exemplo.com +5561999999999 mensal

EMAIL=${1:-"teste@exemplo.com"}
PHONE=${2:-"+5561999999999"}
PLAN=${3:-"mensal"}  # mensal ou anual

# Define valores baseado no plano
if [ "$PLAN" == "anual" ]; then
    PRODUCT_ID="2562423"
    VALUE=59880
else
    PRODUCT_ID="2457307"
    VALUE=6990
fi

echo "🧪 Teste completo de compra"
echo "📧 Email: $EMAIL"
echo "📱 Telefone: $PHONE"
echo "📦 Plano: $PLAN"
echo ""

# Primeiro, simula uma mensagem para criar a thread (opcional)
echo "1️⃣ Criando thread (se não existir)..."
echo ""

# Agora simula a compra (a thread será criada automaticamente se não existir)
echo "2️⃣ Simulando compra..."
curl -X POST "http://localhost:8000/webhook/test-sale" \
  -H "Content-Type: application/json" \
  -d "{
    \"buyer_email\": \"$EMAIL\",
    \"buyer_name\": \"Cliente Teste\",
    \"buyer_phone\": \"$PHONE\",
    \"product_id\": \"$PRODUCT_ID\",
    \"value\": $VALUE,
    \"plan_type\": \"$PLAN\"
  }" | jq '.'

echo ""
echo "✅ Teste concluído!"
echo ""
echo "💡 Dica: Se você forneceu um telefone válido, uma thread foi criada automaticamente"
echo "   e a mensagem pós-compra deve ter sido enviada via WhatsApp!"

