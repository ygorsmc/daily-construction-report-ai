#!/bin/bash
echo "🛑 Encerrando n8n e liberando a porta 5678..."

# Tenta encerrar o processo na porta 5678
PID=$(lsof -t -i:5678)

if [ -z "$PID" ]; then
    echo "✅ Nenhum processo encontrado na porta 5678."
else
    kill -9 $PID
    echo "✅ n8n (PID $PID) encerrado com sucesso."
fi
