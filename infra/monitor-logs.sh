#!/bin/bash
# Script para monitorar logs da API em tempo real
# Uso: ./monitor-logs.sh

cd "$(dirname "$0")"
docker-compose logs -f api 2>&1 | grep -E "(JSON|audio|RESPONSE|URL|ERROR|Exception|Traceback|TWILIO)" --color=always

