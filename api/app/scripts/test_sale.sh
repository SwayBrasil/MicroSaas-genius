#!/bin/bash

# Script para testar simulação de compra
# Uso: ./test_sale.sh <email> <telefone> [plano]
# Exemplo: ./test_sale.sh teste@exemplo.com +5561999999999 mensal

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

echo "🧪 Simulando compra..."
echo "📧 Email: $EMAIL"
echo "📱 Telefone: $PHONE"
echo "📦 Plano: $PLAN"
echo "💰 Valor: R$ $(echo "scale=2; $VALUE/100" | bc)"
echo ""

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

