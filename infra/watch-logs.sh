#!/bin/bash
# Script para ver logs relevantes (sem logs de thread)

cd "$(dirname "$0")"

docker-compose logs -f --tail=100 api 2>&1 | \
  grep --line-buffered -v -E "(thread|Thread|THREAD|WEBHOOK.*thread|Processing LLM for thread|history length|Message.*created|broadcast)" | \
  grep --line-buffered -E "(LLM_SERVICE|RESPONSE_PROCESSOR|TWILIO|SERVE_AUDIO|JSON|audio|template|ÁUDIO)" --color=always

